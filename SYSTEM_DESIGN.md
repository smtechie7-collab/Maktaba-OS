# System Design

## Architecture Type
Hybrid Desktop + Web

## Core Engine
- Language: Python (initial)
- Data Structure: Strict ProseMirror-esque Node Hierarchy
- Collaboration: Yjs (YATA algorithm) CRDT integration for real-time multiplayer

## UI Layer
- Desktop: PyQt6 (Thick Client)
- Embedded Rendering: QWebEngineView (for HTML5 Offscreen Canvas & ProseMirror UI)

## Storage
- SQLite (current)
- Future: Sync layer (optional)

## Modules
- Editor Module
- Interlinear Module
- AI Module
- Audio Module
- Export Module
- Canvas / Interactive Module

## Communication Pattern
UI → Command → Core Engine → Modules → Storage

## Agentic AI Workflow & BYOK Architecture
**Security / Proxy Layer:**
- Intercepts all AI requests for PII Masking and routing.
- Tracks wholesale token usage for user's personal API keys.

**Multi-Agent Orchestration (GroupChat):**
1. **Requirements Agent:** Gathers genre, target demographic, and style.
2. **Planning Agent:** Web scraping (Firecrawl) and chapter-by-chapter outlining.
3. **Drafting Agents:** Parallel processing of chapter writing.
4. **Review Agent:** Reflection pattern; autonomous critiquing and revision routing.
5. **Formatting Agent:** Applies structural styling and LaTeX processing.