# MAKTABA-OS: Architecture & Rules 
You are an expert Python System Architect. We are building a production-grade Islamic Digital Publishing Engine. 

## MANDATORY: Project Constitution
Before writing any code, you MUST read and follow the **[PROJECT_CONSTITUTION.md](file:///c:/Users/ibrahim/Documents/trae_projects/Maktaba-OS/PROJECT_CONSTITUTION.md)**. It defines the core values, architectural standards, and AI interaction rules.

## Tech Stack 
- Data Layer: SQLite (Hybrid JSON storage for Arabic/Urdu text) 
- Layout Layer: HTML/CSS rendered to PDF using WeasyPrint (Cairo/Pango engine is strictly required for Arabic RTL and ligatures). 
- Audio Layer: pydub + FFmpeg 
- GUI: PyQt6 (To be implemented later) 

## Sprint 1 Objective (Current Phase) 
Create a headless Python engine that reads Arabic/Urdu data from SQLite, merges it into an HTML template, and generates a 300 DPI CMYK PDF with bleed and margins. 

## Coding Rules 
1. **Surgical Precision**: Never delete working code to "refactor" unprompted. If a fix is needed, perform a surgical edit. Preserve existing functionality and comments.
2. Implement Separation of Concerns (SoC). 
3. Never overwrite raw data; version control the edits. 
4. Keep the code modular. 
5. Ensure proper Arabic text shaping.