# Lily 1.1.2 TTS / Qt5 Compatibility Patch — Build Report

## What changed
- `voice_manager.py`: on Windows, the real `pyttsx3` module uses a serialized, one-utterance helper subprocess instead of reusing SAPI/COM in the long-lived Lily process. Speech text is sent via stdin, uses `shell=False`, enforces a timeout, and can be cancelled. Fake TTS modules in unit tests keep the existing in-process backend.
- `tts_helper.py`: one-shot SAPI speech process; initializes COM on its own main thread; accepts only rate/volume arguments; receives speech text on stdin; does not log or print speech text.
- `ui.py` and `core/qt_compat.py`: support Qt6 `position()` and Qt5 `pos()` / `localPos()` event APIs. This addresses the observed PyQt5 `QMouseEvent.position` exceptions.
- `lily_gui.py`: logs that the TTS backend returned success instead of claiming that audio necessarily reached the speakers. The duplicate-display fix is retained.
- `lily_version.py`: bump to 1.1.2.
- New mocked regression tests for repeated helper requests, failure, timeout, disabled TTS, and Qt mouse-event compatibility.

## Actual tests run in this review environment
- `python -m py_compile` on changed Python modules: PASS.
- `python tools/check_py38.py`: PASS, no problems found.
- `tests.test_17_tts_subprocess`: 5 tests PASS.
- `tests.test_18_qt5_event_compat`: 4 tests PASS.
- Existing `tests.test_06_voice`: 24 tests PASS.
- Existing `tests.test_16_gui_display`: 4 tests PASS.
- Existing `tests.test_09_integration`: 17 tests PASS in this Linux environment (the Windows-only process-listing skip was not needed here).
- Existing `tests.test_10_compat`: 7 tests PASS.
- Existing `tests.test_11_logging_version_status`: 54 tests PASS.
- Existing `tests.test_12_launch_safety`: 41 tests PASS.
- Existing `tests.test_14_dependencies_and_diagnostics`: 29 tests PASS.

The combined test command was terminated while running the existing `tests.test_13_memory_clear_gate` suite because that module took too long in this environment; this is not recorded as a pass or as a failure. Some focused tests above were run before that timeout and completed successfully.

## Not verified here
- Audible repeated speech through real Windows 7 SAPI/COM.
- Real PyQt5 GUI behavior on Windows 7.
- The hue-wheel drag test on the target machine.
- Full suite completion after the new patch on actual Windows 7/Python 3.8.

The new tests mock process creation; they establish the subprocess contract, not audible playback. Please run the manual Windows steps in `docs/WINDOWS7_TEST_PROCEDURE.md`.
