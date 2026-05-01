[OBSOLETE]
This file has been deprecated. 
Please refer to PROJECT_CONSTITUTION.md, BLUEPRINT.md, and ENGINE_RULES.md for the new system architecture.

Phase V: Extensibility & Scale
Objective: Future-proofing the suite.

[ ] Plugin System: Expose an API for users to drop .py scripts into a plugins/ folder to create custom Word/PDF parsers for the "Smart Paste" feature.

[ ] Cloud Sync: Implement AES-256 encrypted SQLite sync to cloud buckets for seamless multi-device authoring.

4. Production Standards & Rules
UI Constraints: NO QDockWidget for primary tools. Use QStackedWidget for mode switching. NO permanent toolbars if the tools are only used <10% of the time.

Environment Management: Use venv and a strict requirements.txt.

Logging: Implement structured logging (via logging module) to track rendering issues and FFmpeg subprocesses.

Data Integrity: Catch SQLite concurrency issues (database is locked) by utilizing the DbWorker queue system for all writes.

Testing: Visually verify CSS variable injections in Chromium before testing WeasyPrint PDF outputs.

5. Directory Structure
Plaintext
Maktaba-OS/
├── src/
│   ├── data/          # SQLite Managers & Background Workers
│   ├── layout/        # WeasyPrint, Jinja Templates, CSS
│   ├── audio/         # FFmpeg processor & Pydub routing
│   ├── ui/            
│   │   ├── dashboard.py       # Main shell & Mode Switcher
│   │   ├── modes/             # AuthorMode, SyncMode, PublishMode
│   │   ├── components/        # CommandPalette, VisualInspector, FloatingToolbar
│   │   └── dialogs/           # Contextual popups
│   └── utils/         # Helpers (Tajweed Regex, Loggers)
├── assets/            # Fonts, Themes, Images
├── project_rules.md   # AI Context file
├── blueprint_v5.0.md  # This technical roadmap
└── requirements.txt   # Dependencies
6. Development Strategy (Agentic Flow)
Context Initialization: The AI must read project_rules.md and blueprint_v5.0.md before generating code.

Progressive Generation: Build the UI one Mode at a time (e.g., "Build the AuthorMode UI, ensuring horizontal splitters are eliminated").

Strict UX Compliance: If the AI attempts to add a permanent button for a secondary action, reject it and enforce routing through the CommandPalette.

Error Handling: When dealing with PyQt6 WebEngine or WeasyPrint/Pango errors, paste the exact stack trace for the AI to debug dependency chains.