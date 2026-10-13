"""Single-microphone level test.

Usage:
    python test_device1.py            test the microphone chosen in Lily, else the system default
    python test_device1.py 1          test input device number 1 (the numbers are listed first)
    python test_device1.py usb        test the first input device whose name contains "usb"

No device number is built into this script: Windows renumbers audio devices whenever something is
plugged in or removed, so a fixed number that worked yesterday can be a different device today.
Importing this file does nothing; the test only runs when you execute it.
"""
from __future__ import annotations

import sys
import time

import audio_input
import lily_config


def choose_device(arg, devices, configured="", hints=()):
    """Pick an input device. `devices` is a list of (index, name).

    Returns (index_or_None, why). None means "use the system default device".
        arg      "" -> configured device, hints, then the system default
                 "3" -> device number 3 (must exist in `devices`)
                 "usb" -> first device whose name contains the text
    """
    arg = str(arg or "").strip()
    known = dict((i, n) for i, n in devices)
    if arg.isdigit():
        number = int(arg)
        if number in known:
            return number, "chosen on the command line"
        return None, "device %d does not exist; using the system default instead" % number
    names = [n for _i, n in devices]
    wanted = arg or configured
    pos, reason = audio_input.resolve_input_index(names, wanted, [] if arg else hints)
    if pos is not None:
        return devices[pos][0], ("chosen by name on the command line" if arg else "%s device from Lily's settings" % reason)
    if arg:
        return None, "no device name contains %r; using the system default instead" % arg
    return None, "system default input device"


def _rms(data):
    try:
        import audioop
        return audioop.rms(data, 2)
    except Exception:                      # audioop is gone in newer Pythons
        import array
        samples = array.array("h", data)
        return int((sum(s * s for s in samples) / max(1, len(samples))) ** 0.5)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        try:
            import pyaudiowpatch as pyaudio
        except ImportError:
            import pyaudio
    except ImportError:
        print("pyaudiowpatch (or pyaudio) is not installed, so there is nothing to test.")
        return 1

    pa = pyaudio.PyAudio()
    try:
        devices = audio_input.pyaudio_input_devices(pa)
        print("INPUT DEVICES")
        print("=============")
        for index, name in devices:
            info = pa.get_device_info_by_index(index)
            print("  %2d  %s  (%s channel(s), %s Hz)" % (index, name, info.get("maxInputChannels"),
                                                         int(info.get("defaultSampleRate", 0))))
        configured = ""
        try:
            from memory.config_manager import get_input_device
            configured = get_input_device() or ""
        except Exception:
            pass
        index, why = choose_device(" ".join(argv), devices, configured, lily_config.get("mic_name_hints") or [])
        if index is None:
            try:
                info = pa.get_default_input_device_info()
                index = info["index"]
            except Exception:
                print("\nNo input device is available.")
                return 1
        info = pa.get_device_info_by_index(index)
        print("\nTesting device %s: %s  [%s]" % (index, info["name"], why))
        rate = int(info["defaultSampleRate"])
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate, input=True,
                         input_device_index=index, frames_per_buffer=1024)
        print("Speak for 3 seconds...")
        loudest = 0
        end = time.time() + 3
        while time.time() < end:
            loudest = max(loudest, _rms(stream.read(1024, exception_on_overflow=False)))
        stream.stop_stream()
        stream.close()
        print("Highest level: %d - %s" % (loudest, "NO AUDIO" if loudest == 0 else
                                          ("very quiet" if loudest < 500 else "audio detected")))
        return 0
    except Exception as exc:
        print("Could not test the device: %s: %s" % (type(exc).__name__, exc))
        return 1
    finally:
        pa.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
