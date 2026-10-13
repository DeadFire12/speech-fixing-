# Lily • MARK-LIV Local Windows 7 Build

This folder is the merged build produced from the two supplied archives:

- `Lily.zip`
- `Mark-LIV-main.zip`

The working application is **local-first**. Lily's existing llama.cpp + Qwen GGUF conversation engine remains the conversational core; the Mark-LIV HUD, avatar, actions, plugin framework, dashboard, camera layer, document tools, browser tools, reminders, game utilities, and supporting modules are integrated around it.

## No API key

The active configuration contains **no cloud API key**. Mark-LIV's old Gemini-shaped interfaces are kept as a compatibility surface and redirected to the local Qwen engine. The package does not require a Gemini/OpenAI API key to start.

`config/api_keys.json` is retained only because several supplied Mark-LIV modules use that filename as their settings store. In this merged build it contains local settings only.

## Target machine

Prepared around the supplied Lily environment:

- Windows 7 SP1 64-bit
- Python 3.8.10
- Intel Core i5-7200U, 2 cores / 4 threads
- AVX2/FMA/F16C-capable llama.cpp build
- Qwen2 0.5B Instruct, Q4_K-M GGUF
- llama.cpp default thread count: **3**
- llama.cpp context: **2048**

The model and executable paths are stored in `config/local_settings.json` and can be changed there or with the `LILY_LLAMA` / `LILY_MODEL` environment variables.

## Main files

- `Lily.py` — main launcher. Starts the Mark-LIV-inspired HUD by default.
- `Lily.py --console` — runs Lily's text brain without the GUI.
- `Lily.py --dashboard` — starts the HUD plus the Mark-LIV remote dashboard.
- `main.py` — compatibility alias that calls `Lily.py`.
- `ui.py` — the large Mark-LIV HUD adapted from PyQt6 to PyQt5.
- `core/avatar.py` + `core/face_model.obj` — holographic face/avatar system.
- `lily_runtime.py` — Lily's original conversation/memory/tool flow, made importable so the GUI can call the same brain.
- `lily_action_hub.py` — unified Lily + Mark-LIV action/plugin bridge.
- `lily_audio.py` — local voice/PTT/wake-word bridge for the MARK-LIV control surface.
- `dashboard/server.py` — remote dashboard/phone control server.
- `verify_build.py` — offline integrity checker for the target laptop.

## Merged capability layers

The final runtime keeps Lily's deterministic tool system and memory/goal/learning systems alongside the supplied Mark-LIV action framework.

At build time the merged bridge discovers:

- **23 Lily deterministic tools**
- **16 Mark-LIV actions** from `actions/*.py`
- **1 active example plugin** in the unified Mark-LIV plugin registry

The Mark-LIV helper modules that are not tool declarations (for example `background_monitor.py`, `system_monitor.py`, and `screen_processor.py`) are still included in the project and remain available to the modules that use them.

## Compatibility work

The following changes were made because the supplied laptop is Windows 7 / Python 3.8 rather than the newer environment targeted by the current Mark-LIV release:

1. Mark-LIV's PyQt6 UI and avatar code were ported to PyQt5 while keeping the large HUD structure and the supplied face mesh.
2. Gemini-shaped calls used by supplied Mark-LIV actions are routed through `core/gemini.py` to local llama.cpp/Qwen instead of requiring a cloud key.
3. The launcher and GUI are connected to Lily's existing runtime instead of starting a second assistant brain.
4. Mark-LIV actions and plugins are discovered through a unified bridge, with Lily tool names reserved so duplicate names do not silently replace one another.
5. The remote dashboard is connected to the Lily command path. Clicking the HUD remote control can start the server and generate the login key.
6. MARK-LIV push-to-talk and optional wake-word controls are connected to Lily's local voice stack through `lily_audio.py`; the configured microphone name is honored, with the known-good Realtek fallback retained.
7. Python 3.8 compatibility helpers were added where newer path/typing conveniences would otherwise be runtime problems.
8. Lily's local llama.cpp call uses the tested **3-thread** setting rather than the slower higher-thread behavior observed on the laptop.

## Important local limitation

The supplied Qwen2 0.5B model is a **text-only** model. The Mark-LIV project contains image/camera processing code, and those files are still present and wired into the merged structure, but the local Qwen shim cannot actually inspect image pixels. When a Mark-LIV vision action sends image data to the local shim, the shim explicitly tells the model that visual details are unavailable rather than pretending that it saw the image.

## Optional dependencies

The project includes the supplied modules for browser automation, camera capture, screenshots, YouTube helpers, document processing, dashboard serving, etc. Some of those features need extra packages or external programs. The main assistant should remain able to start when an optional feature is unavailable; the action loader reports missing capability instead of aborting the whole project.

Install the packages listed in `requirements-win7.txt` that you actually need, plus a Windows-7-compatible **PyQt5 5.15.x** build for the graphical HUD.

## First run on the laptop

1. Extract this ZIP.
2. Open the extracted folder in PowerShell.
3. Run `py verify_build.py` first.
4. Check `config/local_settings.json` and confirm the two llama.cpp/Qwen paths point to the executable and GGUF that already work on the laptop.
5. Run `py Lily.py` for the HUD, or `py Lily.py --console` for the console.

The supplied original projects are preserved under `original_sources/` for audit/comparison, and the two exact input ZIPs are also preserved under `reference_archives/`. Machine-specific `.venv` contents, Python cache files, screenshots, and transient logs are intentionally not installed as active runtime source.

For the detailed build/test record, see `BUILD_REPORT.md`. For exact Windows 7 setup steps, see `INSTALL-WIN7.md`.
