# Maktaba-OS Production Hardening Plan

## Phase 0: Repo Hygiene
Status: started

- Treat the project root as the source of truth.
- Keep `New folder/` out of active development until it is intentionally removed or archived.
- Ignore generated DB, WAL sidecars, logs, output, caches, and packaged artifacts.

## Phase 1: Central Runtime Paths and Config
Status: implemented

- `src/core/paths.py` owns app root, user data, DB, logs, output, templates, and bundled binary paths.
- `src/core/config.py` exposes one app config used by CLI and GUI.
- Runtime overrides are available through `MAKTABA_DATA_DIR`, `MAKTABA_DB_PATH`, `MAKTABA_LOG_DIR`, and `MAKTABA_OUTPUT_DIR`.

## Phase 2: Database Safety
Status: implemented

- SQLite connections enable WAL, foreign keys, busy timeout, and `synchronous=NORMAL`.
- Schema changes are tracked in `schema_migrations`.
- The old ad-hoc `ALTER TABLE ... except OperationalError` flow is replaced by versioned migrations.

## Phase 3: UI Responsiveness
Status: first pass implemented

- Live preview updates are debounced.
- Preview DB reads and Jinja rendering now run in a background worker.
- Remaining work: move `load_books`, `handle_selection_change`, saves, and bulk import to reusable DB workers.

## Phase 4: Crash Handling and Dependency Errors
Status: first pass implemented

- Global exception handler logs uncaught errors and shows a user-facing dialog in GUI mode.
- WeasyPrint failures now raise a clear PDF export error.
- FFmpeg discovery checks bundled `bin/` first, then system PATH.

## Phase 5: Packaging
Status: scaffolded

- `packaging/maktaba_os.spec` includes templates and QSS assets.
- Bundled binaries can be placed in `bin/` before building.
- Remaining work: test packaged app on a clean Windows machine and tune hidden imports as needed.

## Phase 6: UI Style Cleanup
Status: first pass implemented

- Main dashboard QSS moved to `src/ui/styles/app.qss`.
- Dialog QSS moved to `src/ui/styles/dialogs.qss`.
- Remaining work: extract component-level inline styles from editor/audio/properties panels.

## Phase 7: Release Gates
Status: started

- Added DB migration/WAL tests.
- Remaining work: install/configure Python test runner, add smoke tests for CLI, preview rendering, missing dependency behavior, and packaged startup.
