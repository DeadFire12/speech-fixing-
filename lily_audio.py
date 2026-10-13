"""Local audio bridge for the merged Lily + MARK-LIV build.

This module connects MARK-LIV's UI control surface to Lily's existing local
voice stack without introducing a cloud API key. Speech recognition uses the
SpeechRecognition/pyaudiowpatch path Lily already had; wake-word support is
optional and uses the bundled local openwakeword adapter when installed.

Input modes (derived from the saved flags, wake word is NEVER mandatory):
    wake           wake word starts a voice turn
    push_to_talk   a hotkey starts a voice turn
    manual         voice only when the user clicks WAKE/VOICE; typing always works
    disabled       voice input switched off in settings (typing only)

Hardening (audit): per-thread stop events (a slow-to-exit capture thread can no
longer resume after a restart and duplicate the microphone loop), the wake loop uses
the SAME device selection as command listening, retries with backoff and then
degrades with a clear message, wake mode auto-starts at launch when enabled, and
a repeated detection inside the cooldown window is ignored.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

import audio_input
import lily_config
import lily_log

_alog = lily_log.get_logger("audio")


def _log(cb, message: str) -> None:
    try:
        text = str(message)
        if text.startswith("ERR"):
            _alog.error(text)
        else:
            _alog.info(text)
    except Exception:
        pass
    try:
        if cb:
            cb(str(message))
    except Exception:
        pass


class LocalAudioBridge:
    """Wire MARK-LIV microphone controls to Lily's local voice implementation."""

    WAKE_RETRIES = 3
    BACKOFF_SCALE = 1.0      # tests shrink this so retries are quick

    def __init__(self, submit: Callable[[str], None], log: Callable[[str], None] | None = None,
                 set_state: Callable[[str], None] | None = None,
                 pyaudio_module=None, detector_factory=None, listen_fn=None):
        self._submit = submit
        self._log = log
        self._set_state = set_state
        self._listen_lock = threading.Lock()
        self._listen_busy = False

        self._ptt = None
        self._ptt_enabled = False
        self._ptt_event_lock = threading.Lock()
        self._active_ptt_event = None
        self._ptt_scope = "off"

        self._wake_detector = None
        self._wake_enabled = False
        self._awake = True
        self._wake_failed = False
        self._wake_capture_stop = threading.Event()
        self._wake_capture_thread = None
        self._capture_threads: List[threading.Thread] = []
        self._last_wake = 0.0
        self._timers: List[threading.Timer] = []

        # test seams (None in production)
        self._pyaudio_module = pyaudio_module
        self._detector_factory = detector_factory
        self._listen_fn = listen_fn

        try:
            from memory.config_manager import get_wake_word_enabled, get_push_to_talk_enabled
            self._wake_enabled = bool(get_wake_word_enabled())
            self._ptt_enabled = bool(get_push_to_talk_enabled())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------
    @property
    def ptt_scope(self) -> str:
        """Actual hotkey scope: global, window, or off."""
        return self._ptt_scope

    @property
    def input_mode(self) -> str:
        if not lily_config.get_bool("voice_input_enabled", True):
            return "disabled"
        if self._wake_enabled:
            return "wake"
        if self._ptt_enabled:
            return "push_to_talk"
        return "manual"

    def alive_capture_threads(self) -> int:
        self._capture_threads = [t for t in self._capture_threads if t.is_alive()]
        return len(self._capture_threads)

    # ------------------------------------------------------------------
    # Push-to-talk
    # ------------------------------------------------------------------
    def configure_ptt(self, enabled: bool):
        """Enable/disable the global or windowed Ctrl+Space push-to-talk watcher."""
        from memory.config_manager import save_push_to_talk_enabled
        if not enabled:
            self._release_active_ptt()
        self._ptt_enabled = bool(enabled)
        try:
            from core.hotkey import PushToTalk
            if self._ptt is not None:
                self._ptt.stop()
                self._ptt = None
            if self._ptt_enabled:
                self._ptt = PushToTalk(self._on_ptt_held)
                scope = self._ptt.start()
                self._ptt_scope = scope
                save_push_to_talk_enabled(True)
                _log(self._log, f"SYS: Push-to-talk enabled ({scope} scope).")
                return scope
            self._ptt_scope = "off"
            save_push_to_talk_enabled(False)
            _log(self._log, "SYS: Push-to-talk disabled.")
            return "off"
        except Exception as e:
            self._release_active_ptt()
            if self._ptt_enabled:
                # Keep the feature enabled for the window-scoped Qt fallback if
                # the global watcher cannot be created on this machine.
                try:
                    if self._ptt is not None:
                        self._ptt_scope = self._ptt.scope
                    else:
                        self._ptt_scope = "window"
                except Exception:
                    self._ptt_scope = "window"
                _log(self._log, f"SYS: Global push-to-talk watcher unavailable — {e}; using window scope.")
                return "window"
            self._ptt_scope = "off"
            _log(self._log, f"ERR: Push-to-talk unavailable — {e}. Text mode and manual voice still work.")
            return "off"

    def ptt_hold(self, held: bool) -> None:
        """Receive windowed fallback key events from the Qt UI."""
        try:
            if self._ptt is not None:
                self._ptt.set_held(bool(held))
            else:
                self._on_ptt_held(bool(held))
        except Exception:
            self._on_ptt_held(bool(held))

    def _release_active_ptt(self) -> None:
        with self._ptt_event_lock:
            event = self._active_ptt_event
        if event is not None:
            event.set()

    def _clear_active_ptt(self, event) -> None:
        if event is None:
            return
        with self._ptt_event_lock:
            if self._active_ptt_event is event:
                self._active_ptt_event = None

    def _on_ptt_held(self, held: bool) -> None:
        if not self._ptt_enabled:
            return
        if not held:
            self._release_active_ptt()
            return
        with self._ptt_event_lock:
            if self._active_ptt_event is not None and not self._active_ptt_event.is_set():
                return
            stop_event = threading.Event()
            self._active_ptt_event = stop_event
        self.listen_once(reason="push-to-talk", stop_event=stop_event)

    # ------------------------------------------------------------------
    # One-shot local voice input
    # ------------------------------------------------------------------
    def listen_once(self, reason: str = "voice", stop_event=None) -> None:
        if not lily_config.get_bool("voice_input_enabled", True):
            _log(self._log, "SYS: Voice input is disabled in the settings. Text mode is available.")
            if stop_event is not None:
                stop_event.set()
                self._clear_active_ptt(stop_event)
            return
        if self._listen_busy:
            _log(self._log, "SYS: Already listening.")
            if stop_event is not None:
                stop_event.set()
                self._clear_active_ptt(stop_event)
            return
        t = threading.Thread(target=self._listen_worker, args=(reason, stop_event),
                             daemon=True, name="lily-voice-input")
        t.start()

    def _listen_worker(self, reason: str, stop_event=None) -> None:
        if not self._listen_lock.acquire(False):
            if stop_event is not None:
                stop_event.set()
                self._clear_active_ptt(stop_event)
            return
        self._listen_busy = True
        wake_was_enabled = self._wake_enabled and not self._wake_failed
        try:
            if wake_was_enabled:
                self._stop_wake_capture()
            _log(self._log, f"SYS: Listening ({reason})…")
            if self._set_state:
                self._set_state("LISTENING")
            if stop_event is not None:
                from voice_manager import listen_push_to_talk
                text = listen_push_to_talk(stop_event)
            elif self._listen_fn is not None:
                text = self._listen_fn()
            else:
                from voice_manager import listen
                text = listen()
            if text:
                _log(self._log, "You (voice): " + str(text))
                self._submit(str(text))
            else:
                detail = ""
                try:
                    import voice_manager
                    detail = getattr(voice_manager, "last_error", "") or ""
                except Exception:
                    pass
                suffix = (" (%s)" % detail) if detail else ""
                _log(self._log, "SYS: I didn't get a usable voice command%s." % suffix)
        except Exception as e:
            _log(self._log, f"ERR: Voice input failed — {e}. Text mode remains available.")
        finally:
            if stop_event is not None:
                stop_event.set()
                self._clear_active_ptt(stop_event)
            self._listen_busy = False
            self._listen_lock.release()
            if wake_was_enabled and self._wake_enabled:
                self._start_wake_capture()

    # ------------------------------------------------------------------
    # Local wake word
    # ------------------------------------------------------------------
    def wake_get_state(self) -> dict:
        ready = False
        try:
            from core.wake_word import is_ready
            ready = bool(self._wake_detector and self._wake_detector.ready) or bool(is_ready())
        except Exception:
            pass
        return {"enabled": bool(self._wake_enabled),
                "awake": bool(self._awake),
                "ready": ready,
                "mode": self.input_mode,
                "failed": bool(self._wake_failed)}

    def start_if_configured(self) -> str:
        """Start saved voice controls instead of merely displaying their saved state.

        The previous startup path restored the PTT flag but never created the
        Ctrl+Space watcher. The button could therefore look enabled while its
        hotkey was not actually listening after a restart.
        """
        ptt_result = "off"
        if self._ptt_enabled and self._ptt is None and lily_config.get_bool("voice_input_enabled", True):
            ptt_result = self.configure_ptt(True)
        if not self._wake_enabled:
            return "ptt-enabled" if ptt_result in ("global", "window") else "off"
        result = self.configure_wake(True)
        if result != "enabled":
            self._wake_enabled = False   # do not claim to be listening when we are not
            _log(self._log, "SYS: Wake word unavailable (%s). Voice input via manual wake and text mode "
                            "remain available." % result)
        return result

    def configure_wake(self, enabled: bool) -> str:
        from memory.config_manager import save_wake_word_enabled
        if not enabled:
            self._wake_enabled = False
            self._awake = True
            self._wake_failed = False
            save_wake_word_enabled(False)
            self._stop_wake_capture()
            try:
                if self._wake_detector:
                    self._wake_detector.stop()
            except Exception:
                pass
            self._wake_detector = None
            _log(self._log, "SYS: Wake word disabled.")
            if self._set_state:
                self._set_state("LISTENING")
            return "disabled"

        try:
            from core.wake_word import WakeWordDetector, is_ready
            if self._detector_factory is None and not is_ready():
                return "not-ready"
            self._wake_enabled = True
            self._wake_failed = False
            self._awake = False
            save_wake_word_enabled(True)
            if self._wake_detector is None:
                factory = self._detector_factory or WakeWordDetector
                self._wake_detector = factory(
                    on_detect=self._wake_detected,
                    logger=lambda m: _log(self._log, "SYS: " + m),
                )
            if not self._wake_detector.start():
                self._wake_enabled = False
                save_wake_word_enabled(False)
                return "error"
            self._start_wake_capture()
            _log(self._log, "SYS: Wake word active \u2014 say 'Hey Jarvis'.")
            if self._set_state:
                self._set_state("SLEEPING")
            return "enabled"
        except Exception as e:
            _log(self._log, f"ERR: Wake word unavailable \u2014 {e}. Voice input and text mode remain available.")
            return "error"

    def manual_wake(self) -> None:
        if self._wake_enabled:
            self._awake = not self._awake
            state = "LISTENING" if self._awake else "SLEEPING"
            _log(self._log, "SYS: Manually awake." if self._awake else "SYS: Manually asleep.")
            if self._set_state:
                self._set_state(state)
            if self._awake:
                self.listen_once(reason="manual wake")
        else:
            # With wake-word mode off there is no gated sleep state; a manual
            # wake simply starts one local voice turn.
            self._awake = True
            self.listen_once(reason="manual voice")

    def _wake_detected(self) -> None:
        now = time.monotonic()
        cooldown = lily_config.get_number("wake_cooldown_seconds", 2.0)
        if now - self._last_wake < cooldown:
            return                       # same utterance / repeated trigger
        self._last_wake = now
        self._awake = True
        _log(self._log, "SYS: Wake word detected.")
        if self._set_state:
            self._set_state("LISTENING")
        # Give the hotword detector a moment to release queued audio, then
        # capture the user's next sentence with Lily's normal one-shot listener.
        timer = threading.Timer(0.20, lambda: self.listen_once(reason="wake word"))
        timer.daemon = True
        self._timers = [t for t in self._timers if t.is_alive()] + [timer]
        timer.start()

    # -- capture thread management --------------------------------------
    def _start_wake_capture(self) -> None:
        t = self._wake_capture_thread
        if t is not None and t.is_alive():
            if not self._wake_capture_stop.is_set():
                return                   # already capturing
            t.join(timeout=1.0)          # a stopping thread: let it finish before starting another
        stop_event = threading.Event()   # each capture thread owns its own stop event
        self._wake_capture_stop = stop_event
        self._wake_capture_thread = threading.Thread(
            target=self._wake_capture_loop, args=(stop_event,), daemon=True, name="lily-wake-mic")
        self._capture_threads.append(self._wake_capture_thread)
        self._wake_capture_thread.start()

    def _stop_wake_capture(self) -> None:
        self._wake_capture_stop.set()
        t = self._wake_capture_thread
        self._wake_capture_thread = None
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=1.5)

    def _wake_capture_loop(self, stop_event: threading.Event) -> None:
        """Feed 16 kHz mono PCM chunks into openwakeword; retry, then degrade gracefully."""
        attempts = 0
        while not stop_event.is_set() and self._wake_enabled:
            try:
                self._wake_session(stop_event)
                attempts = 0
            except Exception as e:
                attempts += 1
                _log(self._log, f"SYS: Wake microphone problem ({attempts}/{self.WAKE_RETRIES}) \u2014 {e}")
                if attempts >= self.WAKE_RETRIES:
                    self._wake_failed = True
                    _log(self._log, "SYS: Wake word unavailable. Voice input via manual wake and text mode "
                                    "remain available.")
                    if self._set_state:
                        self._set_state("LISTENING")
                    return
                stop_event.wait(min(2 ** attempts, 8) * self.BACKOFF_SCALE)

    def _wake_session(self, stop_event: threading.Event) -> None:
        pa = None
        stream = None
        try:
            pyaudio = self._pyaudio_module
            if pyaudio is None:
                try:
                    import pyaudiowpatch as pyaudio
                except Exception:
                    import pyaudio
            import numpy as np
            pa = pyaudio.PyAudio()
            wanted = ""
            try:
                from memory.config_manager import get_input_device
                wanted = get_input_device() or ""
            except Exception:
                pass
            index, _reason = audio_input.resolve_pyaudio_index(
                pa, wanted, lily_config.get("mic_name_hints") or [],
                preferred_index=lily_config.get("mic_device_index"))
            kwargs = dict(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1280)
            if index is not None:
                kwargs["input_device_index"] = index
            # 80 ms at 16 kHz is a useful chunk size for openwakeword and is
            # small enough to keep detection responsive on the i5-7200U.
            stream = pa.open(**kwargs)
            while not stop_event.is_set() and self._wake_enabled:
                data = stream.read(1280, exception_on_overflow=False)
                detector = self._wake_detector
                if detector is not None:
                    detector.feed(np.frombuffer(data, dtype=np.int16))
        finally:
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            try:
                if pa is not None:
                    pa.terminate()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def on_voice_change(self) -> None:
        _log(self._log, "SYS: Voice preference changed. Lily uses the local speech engine in this build.")

    def on_audio_device_change(self) -> None:
        _log(self._log, "SYS: Audio device preference changed; the next voice turn will use the configured microphone when available.")

    def shutdown(self) -> None:
        self._release_active_ptt()
        self._stop_wake_capture()
        for timer in self._timers:
            try:
                timer.cancel()
            except Exception:
                pass
        try:
            if self._wake_detector:
                self._wake_detector.stop()
        except Exception:
            pass
        try:
            if self._ptt:
                self._ptt.stop()
        except Exception:
            pass
        self._ptt = None
