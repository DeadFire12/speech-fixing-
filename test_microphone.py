from __future__ import annotations
import sys

import pyaudiowpatch as pyaudio

sys.modules["pyaudio"] = pyaudio

import speech_recognition as sr


recognizer = sr.Recognizer()

microphones = sr.Microphone.list_microphone_names()

print("Available microphones:")

for index, name in enumerate(microphones):
    print(index, ":", name)


import audio_input
import lily_config

# Usage: python test_microphone.py [device number or part of its name]
# Default: the microphone chosen in Lily, else the system default (no hard-coded device).
arg = " ".join(sys.argv[1:]).strip()
if arg.isdigit():
    mic_index, why = int(arg), "chosen on the command line"
else:
    wanted = arg
    if not wanted:
        try:
            from memory.config_manager import get_input_device
            wanted = get_input_device() or ""
        except Exception:
            wanted = ""
    mic_index, why = audio_input.resolve_input_index(microphones, wanted, lily_config.get("mic_name_hints") or [])

print()
print("Selected microphone:", mic_index if mic_index is not None else "system default", "(%s)" % why)


try:

    with sr.Microphone(**({'device_index': mic_index} if mic_index is not None else {})) as source:

        print()
        print("Lily is listening...")
        print("Say: Hello Lily")

        recognizer.adjust_for_ambient_noise(
            source,
            duration=1
        )

        audio = recognizer.listen(
            source,
            timeout=5,
            phrase_time_limit=10
        )

    print()
    print("Audio captured!")
    print("Lily is sending the audio for recognition...")

    text = recognizer.recognize_google(audio)

    print()
    print("Lily heard:", text)

except Exception as e:

    print()
    print("ERROR TYPE:", type(e).__name__)
    print("ERROR:", repr(e))


input()