# Lily + MARK-LIV — Windows 7 setup

This build is designed around the supplied Lily environment: Windows 7 SP1 64-bit, Python 3.8.x, the working local llama.cpp executable, and the Qwen2 0.5B Q4_K-M GGUF model.

## 1. Extract

Extract the main ZIP to a normal folder, for example:

any folder you like, for example `C:\Lily` (Lily no longer depends on a specific user name or location)

Do not run the copy inside the ZIP preview.

## 2. Check the local model paths

Open:

`config\local_settings.json`

The supplied values point to the llama.cpp/Qwen paths that were already working on the laptop. They can also be overridden with:

- `LILY_LLAMA`
- `LILY_MODEL`
- `LILY_THREADS`
- `LILY_CONTEXT`
- `LILY_TIMEOUT`
- `LILY_MAX_TOKENS`

The tested CPU setting is **3 llama.cpp threads**.

## 3. Install the Python packages you actually need

Open PowerShell in the extracted folder and run:

`py -3.8 -m pip install -r requirements-win7.txt`

The graphical HUD needs a Windows-7-compatible **PyQt5 5.15.x** installation. A PyQt package is not bundled into this ZIP because Python GUI wheels are platform-specific.

### 3b. Optional extras - install only what you want

Everything below is optional. Lily starts and works without any of it (text mode, no wake word, no dashboard); each stack has its own file so one problem package cannot block the others. Install them one at a time and note any that fail:

| You want | Command | If you skip it |
|---|---|---|
| Wake word ("Hey Jarvis") | `py -3.8 -m pip install -r requirements-optional.txt` | Wake word is unavailable; push-to-talk, the microphone button and typing still work |
| Microphone/speaker pickers in the HUD | `py -3.8 -m pip install -r requirements-audio-devices.txt` (installs `sounddevice`) | The pickers are empty; Lily uses the saved microphone or the Windows default. Voice, speech and the wake word do not need it |
| Remote dashboard (`py Lily.py --dashboard`, the HUD's remote-control button) | `py -3.8 -m pip install -r requirements-dashboard.txt` | Lily logs how to install it and carries on |
| Fully offline voice input | `py -3.8 -m pip install vosk`, download a Vosk model, set `vosk_model_path` in `config\local_settings.json` | Voice input uses Google's online service |

Windows 7 notes (reasoned from package metadata, **not tested on Windows 7** - check each with `py Lily.py --selftest --quick`):

* The dashboard file deliberately pins **FastAPI below 0.111 together with Pydantic below 2**. A plain `pip install fastapi` pulls Pydantic 2, whose Rust-built core may not load on Windows 7. It also lists `websockets` (the dashboard needs a WebSocket library and plain `uvicorn` has none) and `cryptography` below 43.
* Do not let pip upgrade `onnxruntime` past 1.10.0 (newer builds dropped Windows 7); the wake-word file pins it.
* If a package fails to install, copy the pip error to me. Nothing else in Lily depends on the optional stacks.


The original Lily archive is also preserved at:

`reference_archives\Lily-original.zip`

and the original MARK-LIV archive is at:

`reference_archives\Mark-LIV-original.zip`

## 4. Verify before first run

Run:

`py verify_build.py`

You should see a `RESULT: PASS` from the offline checker. The checker validates source parsing, local-mode configuration, secret-pattern safety, Mark-LIV action discovery, plugin discovery, and the merged imports.

## 5. Start Lily

Graphical HUD:

`py Lily.py`

Console fallback:

`py Lily.py --console`

HUD + remote dashboard:

`py Lily.py --dashboard`

## 6. Local voice and wake word

Lily's existing speech output remains the default voice path. Push-to-talk is connected to MARK-LIV's UI controls. The local wake-word adapter is optional; its download button is kept in the HUD, and the feature stays disabled unless its dependency/model is available.

## 7. No cloud API key

The active merged build does not require a Gemini or OpenAI API key. MARK-LIV Gemini-shaped compatibility calls are redirected into Lily's local llama.cpp/Qwen engine.

Some optional original MARK-LIV accessories can still use the internet for their own purpose (for example web search or browser automation), but they do not require a cloud LLM API key for the merged local conversation engine.

## 8. What cannot be pre-verified here

The build was assembled and statically/smoke tested in a Linux build environment, not on the physical Windows 7 laptop. In particular, the exact PyQt5 GUI rendering and Windows audio-device behavior still need the real Windows machine. The project therefore includes the offline `verify_build.py` checker and retains the exact original archives for recovery/comparison.
