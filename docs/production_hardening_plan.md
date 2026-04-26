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

## Phase A: Core Authoring Workflow
Status: first slice implemented

- Book list now uses database helper APIs instead of raw dashboard queries.
- Books can be edited and deleted from the UI.
- Chapters/elements can be edited, deleted, and moved up/down.
- The app now tracks an active target chapter.
- New content blocks save into the active chapter instead of silently going to the last chapter.
- Chapter tree shows active chapter marker and active block counts.
- Blocks can be selected from the tree, edited, moved up/down, duplicated, and soft-deleted.
- Content blocks now have `sequence_number` through schema migration `003_add_block_sequence`.
- Added database tests for book update/delete, chapter update/delete/reorder, and block duplicate/delete/reorder.
- Added library search/filter.
- Added empty-state labels for library and book structure.
- Action buttons are now disabled when their required selection is missing.
- Tree refresh now preserves the active chapter and selected block where possible.

Remaining Phase A work:

- Move book/chapter/block list loading and mutations to reusable background workers.
- Add richer book metadata fields such as publisher, category, notes, and created/updated labels.
- Add safer validation messages before saves/imports.

## Phase UX: Modern Interaction Layer
Status: first slice implemented

- Reworked the global app stylesheet into a cleaner modern desktop authoring surface.
- Added a top command/context bar above the editor.
- Added active context display for book, chapter, and selected block.
- Added command input for fast actions such as book, chapter, save, PDF, import, and search.
- Added keyboard shortcuts:
  - `Ctrl+N`: new book
  - `Ctrl+Shift+N`: new chapter
  - `Ctrl+S`: save block
  - `Ctrl+F`: focus library search
  - `Ctrl+K`: focus command input
  - `Ctrl+P`: export PDF
  - `Ctrl+I`: bulk import
  - `Esc`: clear editor/edit mode

Remaining Phase UX work:

- Replace text-heavy controls with compact icon/tool buttons where PyQt icon support is available.
- Add a proper command palette with fuzzy matching and visible action results.
- Add split preview modes: selected chapter, full book, and print preview.
- Add status/progress surfaces for async saves/imports/exports.
- Clean component-level inline styles in editor/audio/properties panels.
