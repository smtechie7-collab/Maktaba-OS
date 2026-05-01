# Maktaba-OS V5.0 "Zen Studio"

Maktaba-OS is a desktop publishing and audio synchronization suite for complex multilingual Islamic literature, including Arabic, Urdu, Gujarati, and English workflows.

The current V5 architecture is organized around a strict document model, a SQLite-backed persistence layer, and a PyQt6 desktop shell with three isolated work modes:

- Write: multilingual authoring and chapter editing.
- Sync: interlinear and audio synchronization workflows.
- Publish: layout preview and export workflows.

## Project Governance

Developers and agents working in this repository should read:

- `PROJECT_CONSTITUTION.md`
- `BLUEPRINT.md`
- `SYSTEM_DESIGN.md`
- `MODULE_CONTRACTS.md`
- `ENGINE_RULES.md`

Core rules that matter during implementation:

- Keep the document model as the source of truth.
- Route user-facing mutations through commands.
- Preserve offline-first behavior.
- Avoid deleting user content destructively.
- Keep UI modes isolated.

## Current Status

The active migration has moved the project from the old `src/` tree into:

- `apps/desktop/`
- `core/`
- `infrastructure/`
- `modules/`
- `tests/`

The test suite currently passes and covers the database layer, command system, basic audio processor configuration, and migrated layout data assumptions.

```bash
pytest -q
```

## Running The CLI

```bash
python -m apps.desktop.main list
python -m apps.desktop.main create-book --title "My Book"
python -m apps.desktop.main gui
```

If you want project-local data while developing:

```bash
set MAKTABA_DATA_DIR=.tmp_data
python -m apps.desktop.main list
```

## Dependencies

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

Some future export and audio features may require system tools such as GTK/Cairo/Pango and FFmpeg.
