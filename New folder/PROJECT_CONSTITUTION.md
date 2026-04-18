# MAKTABA-OS: Project Constitution

## 1. Mission & Vision
**Maktaba-OS** is a production-grade Islamic Digital Publishing Engine. Its purpose is to handle high-quality multilingual (Arabic, Urdu, Gujarati, etc.) typesetting and audio processing with the precision of a professional publishing house.

## 2. Core Commandments (Non-Negotiable)
1.  **Preserve the Sacredness of Data**: Raw data is never deleted or directly overwritten. Every edit must be versioned.
2.  **RTL First**: Right-to-Left (Arabic/Urdu) support is not a feature; it is the foundation. Layouts must handle ligatures and complex shaping correctly.
3.  **Modular Monolith**: Code must be separated into clear modules (`src/data`, `src/layout`, `src/audio`, etc.). Modules should interact through well-defined interfaces.
4.  **Local-First, Performance-Always**: The engine should run efficiently on local machines (SQLite, local FFmpeg, WeasyPrint).

## 3. Architectural Standards
### A. Data Integrity (The "Source of Truth")
-   **Storage**: Hybrid Relational + JSON. Use relational tables for indexing/metadata and JSON for content blocks to allow schema flexibility.
-   **Soft Deletes**: Use `is_active` or `deleted_at` flags. Never use `DELETE` on content.
-   **Versioning**: Each content block must have a `version_id`.

### B. Layout & Typography
-   **Rendering**: WeasyPrint is the standard. Avoid headless Chrome unless strictly necessary.
-   **Fonts**: Only high-quality, open-source fonts (Amiri, Jameel Noori Nastaliq, etc.) must be used.
-   **Print Quality**: Always target 300 DPI, CMYK color space, with bleed and crop marks.

### C. Audio Pipeline
-   **Quality**: Use EBU R128 standards for loudness normalization (-16 LUFS).
-   **Consistency**: Automated crossfades between chapters are mandatory.

## 4. Coding Patterns & Style
-   **Naming**: Descriptive over concise (e.g., `generate_book_pdf` instead of `gen_pdf`).
-   **Type Hinting**: All Python functions must have type hints.
-   **Logging**: Use structured logging. Every module must log its entry and exit points for debugging.
-   **Error Handling**: Never "pass" silently. Catch specific exceptions (e.g., `sqlite3.Error`, `WeasyPrintError`).

## 5. UI/UX Philosophy
-   **Modernity**: Dark mode by default.
-   **Simplicity**: A dashboard that hides complexity but allows power-user control.
-   **Responsiveness**: The GUI (PyQt6) must be fluid and handle large datasets without freezing (use threading for heavy tasks).

## 6. AI Interaction Rules (For Future Agents)
-   **Context**: Before writing code, read `PROJECT_CONSTITUTION.md` and `blueprint_v3.0.md`.
-   **Surgical Editing (CRITICAL)**: NEVER do full file rewrites just to fix a small bug or "refactor" unprompted. If you need to fix line 45, ONLY edit line 45. Preserve all surrounding code, comments, and working logic. Do not damage existing functional code.
-   **Incrementalism**: Generate code module-by-module. Do not attempt to build the entire app in one go.
-   **Validation**: Every feature must have a corresponding test in the `tests/` directory.
-   **Consistency**: If you find a pattern in `src/data`, replicate that style in `src/layout`.

---
*This document is the "Constitution" of Maktaba-OS. Any deviation requires a documented reason and a version update.*
