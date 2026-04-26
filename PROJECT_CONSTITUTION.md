# MAKTABA-OS: The Master Constitution (Next-Gen)

## 1. Mission & Vision
**Maktaba-OS** is not just a tool; it is the definitive global standard for Islamic Desktop Publishing (DTP). Our mission is to bridge ancient, sacred texts with hyper-modern, immersive technology. We are building an ecosystem that handles pixel-perfect multilingual typesetting (Arabic/Urdu/Gujarati), live 3D WYSIWYG authoring, and intelligent audio processing with the precision of a multi-million dollar publishing house.

## 2. Core Commandments (Non-Negotiable)
1.  **The Sacredness of Data**: Raw data is immortal. Never use destructive `DELETE` on content blocks. Every edit must be versioned, trackable, and safe.
2.  **Immersive UX is King**: The software must feel like magic. No cluttered databases, no raw code views for the end-user. Interactions must be fluid, contextual, and distraction-free (e.g., 3D Book Illusions, Breathing Grids).
3.  **RTL Excellence**: Right-to-Left (Arabic/Urdu) support is our foundation, not an afterthought. Layouts must perfectly handle complex Nastaliq ligatures, Kashidas, and Harakat positioning.
4.  **The Dual-Engine Mandate**: The UI uses Chromium (WebEngine) for highly interactive, real-time 3D WYSIWYG previews. The Export layer uses WeasyPrint/Pango for CMYK, press-ready PDF perfection. They must remain perfectly synced.
5.  **Local-First, Cloud-Ready**: Extreme local performance (SQLite, FFmpeg) with architectures designed to easily sync to the cloud in the future.

## 3. Architectural Standards
### A. Data Integrity (The "Source of Truth")
-   **Storage**: Advanced Hybrid Relational + JSON. Relational tables for rigid indexing/metadata; JSON for highly flexible, multi-language content blocks.
-   **Soft Deletes**: Strict adherence to `is_active=0` flags.
-   **Versioning**: Each content block must have a `version_id`.

### B. Layout, Typography & UI
-   **Studio Rendering**: PyQt6 mixed with QWebEngineView. The UI must utilize modern desktop patterns (cards, stacks, smooth transitions, click-to-edit bridges).
-   **Print Rendering**: WeasyPrint (Cairo/Pango stack). Must output 300 DPI, CMYK, with bleed, gutter, and crop marks.
-   **Fonts**: Only high-quality, open-source fonts (Amiri, Jameel Noori Nastaliq, etc.) must be used.

### C. Audio Pipeline
-   **Quality**: EBU R128 standards for loudness normalization (-16 LUFS).
-   **Generative Elements**: Automated QR Code generation linking to processed audio splits.

## 4. Coding Patterns & Style
-   **Naming**: Descriptive over concise (e.g., `generate_book_pdf` instead of `gen_pdf`).
-   **Type Hinting**: All Python functions must have type hints.
-   **Logging**: Professional structured logging. Silent failures are strictly forbidden.
-   **Graceful Degradation**: If WebEngine fails, fallback to TextBrowser. If Pango fails, alert gracefully.

## 5. UI/UX Philosophy
-   **Modernity**: Dark mode by default.
-   **The 'Blank Canvas' Cure**: Users must never feel lost. Auto-generate Chapter 1, use empty-state guides, and ensure "Click to Edit" is always visible.
-   **Context-Aware Interfaces**: Tools and buttons should only appear when relevant. Menus should adapt to the active language (Breathing Flex-Grid concept).
-   **Responsiveness**: 0% GUI Freezes. ALL database fetches and file I/O must run on QThread workers.

## 6. AI Interaction Rules (For Future Agents)
-   **Context Awareness**: Always ingest this Constitution, `blueprint_v3.0.md`, and the hardening plan before proposing architecture.
-   **Surgical Editing (CRITICAL)**: NEVER delete working code to "refactor" unprompted. Use diffs to modify ONLY the required lines. Preserve existing logic, comments, and user-facing messages.
-   **No Laziness**: If a feature requires 10 new files, CSS changes, JS bridges, and DB migrations to feel "Pro", DO IT. Do not take shortcuts.
-   **Validation**: Every feature must have a corresponding test in the `tests/` directory.

---
*This is the unbreakable law of Maktaba-OS. We are building a legacy, not a script.*
