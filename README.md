# Maktaba-OS 📚
**Production-grade Islamic Digital Publishing Engine**

Maktaba-OS is a high-quality typesetting and audio processing engine designed for multi-lingual Islamic literature (Arabic, Urdu, Gujarati, English, etc.). It follows a modular architecture to convert structured data from SQLite into professional-grade PDFs and processed audio.

## 🚀 Features
- **Hybrid Data Layer**: SQLite + JSON for flexible and versioned content storage.
- **Professional Typesetting**: WeasyPrint with Pango for perfect Arabic/Urdu RTL support and ligatures.
- **High-Quality PDF**: 300 DPI CMYK output with bleed and margins for professional printing.
- **Audio Pipeline**: Automated volume normalization (-16 LUFS) and crossfades using FFmpeg.
- **Modern Dashboard**: (Upcoming) PyQt6-based management interface.

## 🏛 Project Governance
This project is governed by the [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md). All contributors (including AI agents) must adhere to the core commandments:
1. **Preserve Data Sacredness**: Never delete raw data; always version.
2. **RTL First**: Arabic/Urdu support is the foundation.
3. **Surgical Precision**: Minimal, non-destructive code edits.

## 🛠 Tech Stack
- **Language**: Python 3.9+
- **Database**: SQLite
- **Layout**: WeasyPrint (Cairo/Pango)
- **Audio**: Pydub + FFmpeg
- **UI**: PyQt6

## 📂 Structure
- `src/data`: Database schemas and ingestion logic.
- `src/layout`: HTML/CSS templates and PDF generation wrapper.
- `src/audio`: Audio processing scripts.
- `assets/`: Fonts and static resources.

## 🚦 Getting Started
1. **System Dependencies (Windows)**:
   WeasyPrint requires the GTK+ runtime for Cairo and Pango. 
   - Download the latest GTK3 installer from [Gtk-for-Windows](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases).
   - Add the `bin` folder to your System PATH.

2. **FFmpeg (For Audio)**:
   Audio processing requires FFmpeg.
   - Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) or via `choco install ffmpeg`.
   - Ensure `ffmpeg` and `ffprobe` are in your System PATH.
   
3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
 4. **Run the CLI Tool**:
   Maktaba-OS comes with a master CLI to manage your publishing tasks.
   
   - **List Books**:
     ```bash
     python main.py list
     ```
   - **Export PDF**:
     ```bash
     python main.py export-pdf --id 1 --output output/my_book.pdf
     ```
   - **Process Audio**:
     ```bash
     python main.py process-audio --input file1.mp3 file2.mp3 --output output/final.mp3
     ```

## 📜 License
MIT License - See [LICENSE](LICENSE) for details.
