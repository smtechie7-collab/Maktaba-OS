# MAKTABA-OS: V3.0 Technical Blueprint (Refined)

## 1. Project Overview
Production-grade Islamic Digital Publishing Engine designed for high-quality Arabic/Urdu/Multi-lingual typesetting and audio processing.

## 2. Core Architecture: Modular Monolith
The system follows a strict **Separation of Concerns (SoC)** approach.

### A. Data Layer (`src/data`)
- **Engine**: SQLite with JSON1 extension support.
- **Storage Strategy**: Hybrid relational + JSON for flexible text blocks.
- **Key Tables**:
  - `Books`: Metadata (Title, Author, ISBN, Language).
  - `Chapters`: Hierarchy and ordering.
  - `Content_Blocks`: The actual text (Arabic/Urdu/Translations) stored in JSON format for easy versioning.
- **Rules**: Never delete raw data. Use `version` and `is_active` flags for edits.

### B. Layout & PDF Engine (`src/layout`)
- **Engine**: WeasyPrint (3.0+).
- **Dependencies**: Cairo, Pango, GObject (Must be correctly configured for Windows).
- **Capabilities**:
  - Full RTL support (Arabic/Urdu ligatures and shaping).
  - 300 DPI CMYK output for professional printing.
  - Bleed, margins, and crop marks via CSS Paged Media.
  - Custom font embedding (Amiri, Jameel Noori Nastaliq, etc.).

### C. Audio Pipeline (`src/audio`)
- **Engine**: Pydub + FFmpeg.
- **Processing**:
  - Normalization to -16 LUFS (EBU R128 standard).
  - Automated crossfades and silence trimming.
  - Dynamic merging based on book chapter structure.

### D. GUI Dashboard (`src/ui`) - *Future Sprint*
- **Framework**: PyQt6.
- **Theme**: Modern Dark Mode.
- **Features**: Data management, real-time preview, and batch export controls.

---

## 3. Current Sprint Focus: Headless Engine
**Objective**: Build the bridge between SQLite and WeasyPrint.

1.  **Data Ingestion**: CLI script to populate the database with JSON-structured text.
2.  **HTML Templating**: Jinja2 templates for Arabic/Urdu layouts.
3.  **PDF Generation**: Python wrapper for WeasyPrint with Pango-level text shaping.

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
