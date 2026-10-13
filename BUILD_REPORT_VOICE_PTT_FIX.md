# Lily v1.1.3 — Voice Input / Push-to-Talk Patch Report

## Scope

This patch targets two symptoms reported on the Windows 7 laptop:

1. Voice capture sometimes reaches recognition without usable words, apparently
   before the user has time to speak.
2. Ctrl+Space push-to-talk did not behave reliably in the original HUD.

## Changes

- Reworked `mic_level_test.py` to discard the startup transient and measure quiet
  and spoken phases separately (mean, median, 90th percentile, peak, and ratio).
  This avoids treating one peak RMS value as proof that speech was captured.
- Added `mic_device_index`, an optional local override for duplicate Windows
  Realtek endpoints. It should only be set to a raw input index confirmed by the
  updated level test; leaving it unset preserves automatic selection.
- Added a press-and-hold recording path for Ctrl+Space: audio is captured while
  the chord is held, then transcribed when released. It skips microphone ambient
  calibration after key-down so calibration does not intentionally consume the
  opening words.
- Replaced the window-only QShortcut/timer approximation with actual Qt key-down
  and key-up tracking, including release when the app/window loses focus.
- Restored the saved Ctrl+Space watcher at launch, instead of only restoring the
  saved enabled flag.
- Added more specific voice-input failure logging and `tests/test_19_ptt_hold_capture.py`.
- Retained the v1.1.2 TTS repeat-speech and Qt5 mouse-event fixes in files that
  this patch replaces.

## Verification performed in this build environment

- Python compilation check for changed modules: passed.
- `tools/check_py38.py`: passed, no Python 3.8 compatibility issues reported.
- Targeted suite covering voice, wake-word logic, integration, duplicate GUI output,
  TTS subprocess, Qt event compatibility, and new PTT tests: **74 passed**.

A full test discovery run did not finish within the 180-second limit at a long
conversation identity test, and a separate broader run timed out while executing
a memory-gate test. These are timeouts, not a complete result for those suites;
this report does not claim the full suite passed.

## Not verified here

This build environment cannot exercise the user's real Windows 7 microphone,
PyQt5 GUI, keyboard polling, Google speech service, or SAPI hardware path. The
prior user's old microphone test reported the same maximum value in silence and
speech, but a maximum alone cannot establish that the input is stuck; the new
quiet-versus-speaking measurements are needed. Likewise, PTT fixes the capture
semantics, but voice recognition still depends on selecting a real microphone
endpoint that responds to speech. Live verification is required on the target PC.
