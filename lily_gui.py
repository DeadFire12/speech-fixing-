
from __future__ import annotations
import asyncio, threading
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from ui import JarvisUI
from lily_action_hub import LilyActionHub, simple_route
import lily_runtime
import voice_manager
from voice_manager import speak
from core import local_engine
import lily_dispatch
import lily_log
import lily_status
import lily_version
from dashboard.server import DashboardServer
from lily_audio import LocalAudioBridge

class LilyGUI:
    def __init__(self):
        self.app=QApplication.instance() or QApplication([])
        face=str(Path(__file__).resolve().parent/'core'/'face_model.obj')
        self.ui=JarvisUI(face)
        self.hub=LilyActionHub()
        self._busy=False
        self._busy_lock=threading.Lock()
        self.dashboard=None
        self._dashboard_loop=None
        self._dashboard_thread=None
        self.ui.on_text_command=self.submit
        self.audio=LocalAudioBridge(lambda t: self.submit(t, origin="voice"), self.ui.write_log, self.ui.set_state)
        self.ui.on_push_to_talk=self.audio.configure_ptt
        self.ui.ptt_hold=self.audio.ptt_hold
        self.ui.wake_get_state=self.audio.wake_get_state
        self.ui.on_wake_toggle=self.audio.configure_wake
        self.ui.on_wake_manual=self.audio.manual_wake
        self.ui.on_voice_change=self.audio.on_voice_change
        self.ui.on_audio_device_change=self.audio.on_audio_device_change
        self.ui.on_interrupt=self.interrupt
        self.ui.on_remote_clicked=self.remote_control
        self.ui.get_plugins=self.hub.plugin_ui
        self.ui.get_plugin_settings=self.hub.plugin_settings
        self.ui.set_state("LISTENING")
        self.ui.write_log("SYS: Lily local engine connected to Mark-LIV HUD.")
        self.ui.write_log("SYS: " + lily_version.version_string())
        if local_engine.available():
            self.ui.write_log("SYS: Local AI engine found - no API key or internet needed for chat.")
        else:
            self.ui.write_log("SYS: Local AI model not found - tools still work, chat is limited. "
                              "Check config/local_settings.json (run the self-test for details).")
        tts = voice_manager.tts_status()
        self.ui.write_log("SYS: Speech output: " + ("ready." if tts["available"] else "unavailable (%s). Text mode is fine." % tts["reason"]))
        self.ui.write_log("SYS: Voice input mode: %s." % self.audio.input_mode)
        self.ui.write_log("SYS: Mark-LIV actions and plugins discovered: %d" % len(self.hub.action_ui()))
        try:
            lily_status.set_component_counts(len(self.hub.lily_tools.tools), len(self.hub.actions.names()),
                                             len(self.hub.plugin_ui()))
        except Exception:
            pass
        # Restore actual microphone watchers from their saved flags in the background.
        # In particular, a saved PTT flag must start the Ctrl+Space watcher, not
        # merely make the button look enabled after a restart.
        threading.Thread(target=self._start_audio_controls, name="lily-wake-start", daemon=True).start()

    def _start_audio_controls(self):
        self.audio.start_if_configured()
        try:
            # Signal is thread-safe and lets the UI install the window-scope
            # fallback only if the global Windows key poller was unavailable.
            fallback = bool(self.audio._ptt_enabled and self.audio.ptt_scope == "window")
            self.ui._win._ptt_fallback_sig.emit(fallback)
        except Exception:
            pass

    def _ensure_dashboard(self):
        if self.dashboard is not None:
            return self.dashboard
        import dashboard.server as _dashboard_module
        if not getattr(_dashboard_module, "_DEPS_OK", False):
            self.ui.write_log("SYS: The remote dashboard is optional and its packages are not installed. "
                              "To enable it run: py -m pip install -r requirements-dashboard.txt")
            return None
        try:
            self.dashboard = DashboardServer()
            self.dashboard.set_command_callback(lambda t: self.submit(t, origin="remote"))
            self.dashboard.set_connect_callback(lambda: self.ui.write_log("SYS: Remote device connected."))

            def _serve():
                loop = asyncio.new_event_loop()
                self._dashboard_loop = loop
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.dashboard.serve())
                finally:
                    loop.close()

            self._dashboard_thread = threading.Thread(target=_serve, name="lily-dashboard", daemon=True)
            self._dashboard_thread.start()
            self.ui.write_log("SYS: Remote dashboard service starting on port 8000.")
            return self.dashboard
        except Exception as e:
            self.ui.write_log("ERR: Dashboard could not start: %s" % e)
            self.dashboard = None
            return None

    def start_dashboard(self):
        return self._ensure_dashboard()

    def remote_control(self):
        server=self._ensure_dashboard()
        if server is None:
            return None
        try:
            key=server.new_key()
            url=server.get_url()
            auto=url + "/auto-login?key=" + key
            manual=server.get_manual_url()
            return (url, key, auto, manual)
        except Exception as e:
            self.ui.write_log("ERR: Could not create remote key: %s" % e)
            return None

    def _dashboard_broadcast(self, message):
        if self.dashboard is None or self._dashboard_loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.dashboard.broadcast(message), self._dashboard_loop)
        except Exception:
            pass

    def interrupt(self):
        stopped = local_engine.interrupt()
        voice_manager.stop_speaking()
        self.ui.write_log("SYS: Interrupt - stopped the AI engine." if stopped else "SYS: Interrupt - nothing was running.")

    def submit(self, text, origin="local"):
        with self._busy_lock:
            if self._busy:
                self.ui.write_log("SYS: I'm still working on your last request - please try again in a moment.")
                return
            self._busy = True
        self._dashboard_broadcast({"type": "user", "text": str(text)})
        threading.Thread(target=self._worker, args=(str(text), origin), daemon=True).start()

    def _worker(self, text, origin="local"):
        self.ui.set_state("THINKING")
        try:
            outcome = lily_dispatch.dispatch(text, self.hub, origin=origin)
            answer = outcome["answer"]
            # Runtime prints ``Lily: ...`` into captured stdout for console use.
            # The GUI renders the structured answer below, so do not render that
            # same final response a second time. Keep any earlier tool/status output.
            captured = lily_dispatch.output_without_answer(outcome.get("output", ""), answer)
            for line in captured.splitlines():
                self.ui.write_log(line)
            self.ui.write_log("Lily: " + answer)
            self._dashboard_broadcast({"type": "assistant", "text": answer})
            try:
                if self.ui._win._assistant_name and answer and not answer.startswith("I hit an internal error"):
                    self.ui.start_speaking()
                    # Log only success/failure and length, never the user's or Lily's text.
                    lily_log.get_logger("gui").info("TTS requested for assistant reply (%d characters)", len(answer))
                    spoken = speak(answer)
                    if spoken:
                        lily_log.get_logger("gui").info("TTS backend returned success for assistant reply (%d characters)", len(answer))
                    else:
                        status = voice_manager.tts_status()
                        reason = status.get("reason") or "the TTS worker returned False"
                        lily_log.get_logger("gui").warning("TTS did not complete for assistant reply: %s", reason)
                        self.ui.write_log("SYS: Speech output did not complete: %s" % reason)
            except Exception as voice_error:
                lily_log.get_logger("gui").exception("TTS call failed")
                self.ui.write_log("SYS: Voice output skipped: %s" % voice_error)
            finally:
                self.ui.stop_speaking()
        except Exception as e:
            lily_log.get_logger("gui").exception("message handling failed")
            self.ui.write_log("ERR: %s: %s" % (type(e).__name__, e))
        finally:
            self.ui.set_state("LISTENING")
            with self._busy_lock:
                self._busy = False

    def run(self):
        self.ui._win.show()
        try:
            return self.app.exec_()
        finally:
            for cleanup in (self.audio.shutdown, voice_manager.shutdown, local_engine.shutdown):
                try:
                    cleanup()
                except Exception:
                    pass

def run_gui(start_dashboard=False):
    gui=LilyGUI()
    if start_dashboard:
        gui.start_dashboard()
    return gui.run()
