# Build and verification report

## Source archives

Two user-supplied archives were merged:

- `Lily.zip`
- `Mark-LIV-main.zip`

The exact input archives are preserved unchanged under `reference_archives/`.
The exact original source snapshots are preserved under `original_sources/`.

## Source coverage

The merged audit snapshots contain every portable non-cache source/data file from the Lily archive after intentionally excluding the machine's `.venv`, transient screenshots, `main.log`, and bytecode caches. The original archive itself is still preserved in full.

- Lily portable source snapshot: **62 files, exact byte match**
- MARK-LIV source snapshot: **58 files, exact byte match**

## Active merged capability discovery

The unified runtime currently discovers:

- Lily deterministic tools: **23**
- MARK-LIV action modules: **16**
- MARK-LIV example plugin: **1**

The MARK-LIV action registry has no name collisions with Lily's 23 deterministic tools.

## Compatibility work

The active launcher uses Lily's local `llama.cpp + Qwen2 0.5B` engine as the conversational core. The large MARK-LIV HUD and avatar were adapted from PyQt6 imports/API spellings to PyQt5 for the supplied Windows 7/Python 3.8 environment. The MARK-LIV action and plugin registries remain active, and dashboard commands are routed into Lily's command path.

The cloud Gemini-shaped module surface remains as a compatibility layer only. It calls the local Qwen engine and does not read or require a Gemini/OpenAI API key.

MARK-LIV push-to-talk and optional wake-word controls were connected to `lily_audio.py`, while Lily's known-good voice input/output path remains available.

## Checks performed

- Python compile check over active merged Python files: **PASS** (91 Python files)
- Offline build checker: **PASS**
- Mark-LIV action discovery: **16 active**
- Plugin discovery: **1 active**
- Unified Lily tool discovery: **23 active**
- Local engine smoke test with an isolated fake llama executable: **PASS**
- Local Gemini-shaped compatibility call with fake local engine: **PASS**
- MARK-LIV `file_processor` local-model smoke path: **PASS**
- PyQt5 UI/avatar/lily_gui import-shape test using an isolated stub because PyQt5 is unavailable in the build environment: **PASS**
- `Lily.py --console` launch smoke with an isolated fake local llama executable: **PASS**
- Scan for common API-key patterns in active runtime: **PASS**
- Exact input-source archive coverage: **PASS**

## Important limitation

A real Windows 7 GUI/audio session cannot be executed inside this Linux build environment. That means the physical laptop still needs the correct PyQt5 build and its Windows audio/camera devices need to be exercised there. This is why the package does not claim that every hardware-specific path was live-tested.
