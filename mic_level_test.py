"""Compare microphone input level while quiet and while speaking.

Usage:
    py -3.8 mic_level_test.py        use Lily's configured/default microphone
    py -3.8 mic_level_test.py 5      test a raw PyAudio input-device index
    py -3.8 mic_level_test.py 9      compare another Windows host-API entry
    py -3.8 mic_level_test.py usb    test the first device whose name contains 'usb'

The old test printed only the highest RMS sample. A brief stream-start transient
could dominate that value, making silence and speech look identical. This test
ignores start-up noise and compares average/median levels over separate phases.
"""
from __future__ import print_function
import audioop
import statistics
import sys
import time

import pyaudiowpatch as pyaudio
import audio_input
import lily_config


def _choose(pa):
    arg = " ".join(sys.argv[1:]).strip()
    if arg.isdigit():
        return int(arg), "chosen on the command line"
    wanted = arg
    preferred = lily_config.get("mic_device_index")
    if not wanted:
        try:
            from memory.config_manager import get_input_device
            wanted = get_input_device() or ""
        except Exception:
            wanted = ""
    index, reason = audio_input.resolve_pyaudio_index(
        pa, wanted, lily_config.get("mic_name_hints") or [],
        preferred_index=preferred if not arg else None)
    if index is None:
        try:
            index = int(pa.get_default_input_device_info()["index"])
            reason = "system default input device"
        except Exception:
            index, reason = None, "no input device available"
    return index, reason


def _drain(stream, seconds, chunk_size):
    """Keep the blocking input stream moving while throwing away transition audio."""
    end = time.monotonic() + max(0.0, seconds)
    while time.monotonic() < end:
        stream.read(chunk_size, exception_on_overflow=False)


def _measure(stream, seconds, chunk_size, sample_width=2, ignore_first=0.25):
    start = time.monotonic()
    levels = []
    while time.monotonic() - start < seconds:
        data = stream.read(chunk_size, exception_on_overflow=False)
        elapsed = time.monotonic() - start
        level = audioop.rms(data, sample_width)
        if elapsed >= ignore_first:
            levels.append(float(level))
    if not levels:
        return {"mean": 0.0, "median": 0.0, "p90": 0.0, "peak": 0.0, "samples": 0}
    ordered = sorted(levels)
    p90 = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.90))]
    return {
        "mean": sum(levels) / float(len(levels)),
        "median": float(statistics.median(levels)),
        "p90": float(p90),
        "peak": float(max(levels)),
        "samples": len(levels),
    }


def _show_stats(label, stats):
    print("%s RMS: mean=%.1f | median=%.1f | p90=%.1f | peak=%.1f | blocks=%d" % (
        label, stats["mean"], stats["median"], stats["p90"], stats["peak"], stats["samples"]))


def main():
    pa = pyaudio.PyAudio()
    try:
        print("INPUT DEVICES")
        print("=============")
        for i, name in audio_input.pyaudio_input_devices(pa):
            try:
                info = pa.get_device_info_by_index(i)
                print("INDEX: %s | NAME: %s | CHANNELS: %s | RATE: %s | HOST API: %s" % (
                    i, name, info.get("maxInputChannels", 0), info.get("defaultSampleRate"), info.get("hostApi")))
            except Exception:
                print("INDEX: %s | NAME: %s" % (i, name))

        mic_index, why = _choose(pa)
        print("\n================================")
        print("TESTING MICROPHONE: %s - %s" % (mic_index, why))
        print("================================")
        if mic_index is None:
            print("No input device found.")
            return 1

        info = pa.get_device_info_by_index(mic_index)
        max_channels = int(info.get("maxInputChannels", 0) or 0)
        if max_channels < 1:
            print("ERROR: this index is not an input-capable device.")
            return 1
        rate = int(float(info.get("defaultSampleRate", 44100) or 44100))
        # Match SpeechRecognition's usual mono input path as closely as possible.
        stream = None
        try:
            stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate,
                             input=True, input_device_index=mic_index, frames_per_buffer=1024)
        except Exception as first_error:
            if max_channels < 2:
                raise
            print("Mono capture failed (%s); retrying with 2 channels." % first_error)
            stream = pa.open(format=pyaudio.paInt16, channels=2, rate=rate,
                             input=True, input_device_index=mic_index, frames_per_buffer=1024)

        try:
            print("Name: %s" % info.get("name", "unknown"))
            print("Sample rate: %s Hz" % rate)
            print("\nOpening microphone; discarding the first second of start-up audio...")
            _drain(stream, 1.0, 1024)
            print("\nPHASE 1/2: Keep completely quiet for 4 seconds.")
            quiet = _measure(stream, 4.0, 1024)
            _show_stats("QUIET", quiet)
            print("\nPHASE 2/2: SPEAK NOW — repeat 'HELLO LILY' for 5 seconds.")
            print("(Only the levels change here; no speech-recognition service is used.)")
            speech = _measure(stream, 5.0, 1024)
            _show_stats("SPEAKING", speech)
            delta = speech["mean"] - quiet["mean"]
            ratio = speech["mean"] / max(1.0, quiet["mean"])
            print("\nMEAN-LEVEL CHANGE: %+0.1f | SPEAKING/QUIET RATIO: %.2fx" % (delta, ratio))
            if quiet["mean"] > 8000 and ratio < 1.25:
                result = "INPUT LEVEL IS VERY LOUD AND BARELY CHANGES; possible stuck/incorrect audio endpoint."
            elif ratio >= 1.50 and delta >= 80:
                result = "VOICE LEVEL CHANGE DETECTED; this endpoint appears to respond to speech."
            elif quiet["mean"] < 35 and speech["mean"] < 60:
                result = "VERY LITTLE SIGNAL; check Windows Recording Devices, mute, and microphone gain."
            elif ratio < 1.25:
                result = "NO CLEAR SPEECH-LEVEL CHANGE; compare another input index (for example 1, 5, or 9)."
            else:
                result = "SOME LEVEL CHANGE, BUT INCONCLUSIVE; compare another input index if recognition still fails."
            print("RESULT: " + result)
            print("\nCompare aliases with: py -3.8 mic_level_test.py 1   (then 5, then 9 if listed).")
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        return 0
    except Exception as exc:
        print("\nERROR: %s: %r" % (type(exc).__name__, exc))
        return 1
    finally:
        try:
            pa.terminate()
        except Exception:
            pass
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    raise SystemExit(main())
