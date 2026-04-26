# MAKTABA-OS: V4.0 "Pro Studio" Blueprint (1-Year Master Plan)

## 1. Project Overview
Maktaba-OS is a world-class, professional-grade Islamic Desktop Publishing (DTP) suite. It bridges the gap between structured database management and high-end visual typesetting, designed specifically for Arabic, Urdu, and complex multilingual literature.

## 2. Core Architecture: The Dual-Engine Monolith
The system operates on a highly advanced, decoupled architecture to ensure WYSIWYG UI speed and perfect print quality.

### A. Data Layer (`src/data`)
- **Engine**: SQLite with JSON1 extension support.
- **Storage Strategy**: Hybrid relational + JSON for flexible text blocks.
- **Key Tables**:
  - `Books`: Metadata (Title, Author, ISBN, Language).
  - `Chapters`: Hierarchy and ordering.
  - `Content_Blocks`: The actual text (Arabic/Urdu/Translations) stored in JSON format for easy versioning.
- **Rules**: Never delete raw data. Use `version` and `is_active` flags for edits.

### B. The Dual Presentation Layer (`src/layout` & `src/ui`)
- **The Studio Engine (UI)**: PyQt6 combined with Chromium (`QWebEngineView`). Uses a custom Python-JS bridge (`pybridge`) to allow users to click directly on 3D rendered HTML pages and live-edit the underlying database blocks.
- **The Print Engine (Export)**: WeasyPrint with strict Pango/Cairo dependencies. Completely ignores UI elements (shadows, JS, 3D effects) via `@media print` CSS, focusing purely on CMYK colors, bleed, crop marks, and flawless RTL typesetting.

### C. Audio Pipeline (`src/audio`)
- **Engine**: Pydub + FFmpeg.
- **Processing**:
  - Normalization to -16 LUFS (EBU R128 standard).
  - Automated crossfades and silence trimming.
  - QR Code generation dynamically linked to the audio track.

---

## 3. The 1-Year Next-Level Roadmap
This roadmap dictates our long-term growth from a great tool to an industry standard.

### Phase I: The Immersive Studio (Current Phase)
- [x] Library vs Studio Stack paradigm.
- [x] Breathing UI (Dynamic Flex-Grid Editors).
- [x] Python-JS Bridge for 3D Book Click-to-Edit.
- [ ] Deep WebGL/CSS3D integration for realistic page flipping (Turn.js).

### Phase II: Advanced DTP Controls
- [ ] Visual Property Inspector: Drag sliders for margin, leading, and kerning that update live.
- [ ] Footnote Engine: Automated layout of footnotes at the bottom of printed pages without breaking WYSIWYG.
- [ ] Custom Template Builder: Let users create their own book themes via GUI.

### Phase III: The Audio-Visual Sync
- [ ] Waveform UI: View and trim FFmpeg audio directly inside the PyQt dashboard.
- [ ] Word-Level Sync: Highlight Arabic words in the PDF/UI as the audio plays (karaoke style).

### Phase IV: Extensibility & Scale
- [ ] Plugin System: Allow Python scripts to be loaded dynamically for custom imports.
- [ ] Cloud Sync: AES-256 encrypted SQLite sync to an S3 bucket for multi-device authoring.

---

## 4. Production Standards & Rules
1.  **Environment Management**: Use `venv` and a strict `requirements.txt`.
2.  **Logging**: Implement structured logging (via `logging` module) to track rendering issues.
3.  **Error Handling**: Specifically catch Pango rendering errors and SQLite concurrency issues.
4.  **Testing**:
    - `pytest` for data integrity checks.
    - Visual regression testing for PDF output (compare hashes or pixel diffs).
5.  **Modular Imports**: Use absolute imports from `src`.

---

## 5. Directory Structure
```text
Maktaba-OS/
├── src/
│   ├── data/          # Database schemas & ingestion scripts
│   ├── layout/        # HTML templates, CSS, & PDF generator
│   ├── audio/         # FFmpeg processing logic
│   ├── ui/            # PyQt6 interface (Future)
│   └── utils/         # Helpers (Logging, Text Shaping, etc.)
├── tests/             # Unit & Integration tests
├── assets/            # Fonts, Images, Sample Data
├── project_rules.md   # AI Context file
├── blueprint_v3.0.md  # This technical roadmap
└── requirements.txt   # Dependencies
```

---

## 6. Development Strategy (Agentic Flow)
1.  **Context**: Always feed `project_rules.md` and `blueprint_v3.0.md` to the AI.
2.  **Modular Generation**: Focus on one folder at a time (e.g., "Build the `src/data` module first").
3.  **Feedback Loop**: Copy terminal errors directly into the AI to fix dependencies (especially Pango/Cairo setup).
4.  **Integration**: Use the AI to write "Glue Code" only after individual modules are verified.
