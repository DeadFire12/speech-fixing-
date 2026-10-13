#!/usr/bin/env python
"""One-shot pyttsx3/SAPI helper for Lily's Windows 7 build.

The spoken text arrives on stdin (never a command-line argument), and no speech text is
printed or logged. A fresh process gives each utterance an independent COM/SAPI lifecycle.
"""
from __future__ import print_function

import argparse
import sys
import traceback


def _initialize_com():
    for module_name in ("pythoncom", "comtypes"):
        try:
            module = __import__(module_name)
            initialize = getattr(module, "CoInitialize", None)
            if initialize:
                initialize()
                return module
        except Exception:
            continue
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lily one-shot speech helper")
    parser.add_argument("--rate", type=int, default=175)
    parser.add_argument("--volume", type=float, default=1.0)
    args = parser.parse_args(argv)
    text = sys.stdin.read()
    if not text.strip():
        print("No speech text was provided.", file=sys.stderr)
        return 2

    com_module = None
    engine = None
    try:
        com_module = _initialize_com()
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", max(80, min(350, int(args.rate))))
        engine.setProperty("volume", max(0.0, min(1.0, float(args.volume))))
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        engine = None
        return 0
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass
        if com_module is not None:
            uninitialize = getattr(com_module, "CoUninitialize", None)
            if uninitialize:
                try:
                    uninitialize()
                except Exception:
                    pass


if __name__ == "__main__":
    sys.exit(main())
