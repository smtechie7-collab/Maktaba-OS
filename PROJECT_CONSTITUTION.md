MAKTABA-OS CONSTITUTION (FOUNDATION LAYER)

This is non-negotiable.
Every future line of code must obey this.

📜 1. SYSTEM CONSTITUTION (CORE LAWS)
⚖️ LAW 1 — DOCUMENT IS THE SINGLE SOURCE OF TRUTH

Everything revolves around a structured document model, NOT database tables.

Database = storage layer only
Editor = manipulation layer
Export = rendering layer

❗ If logic enters DB → system will collapse later

⚖️ LAW 2 — STRICT SCHEMA ONLY (NO FREE JSON)

Your current:

{ "ar": "...", "ur": "...", "en": "..." }

This is forbidden going forward.

Instead:

{
  "type": "interlinear_block",
  "content": [
    {
      "type": "word_bundle",
      "l1": "...",
      "l2": "...",
      "l3": "..."
    }
  ]
}

👉 Why:

Enables AI editing safely
Enables interlinear sync
Enables rendering engines
⚖️ LAW 3 — UI IS A CLIENT, NOT THE SYSTEM

Your PyQt UI:

must NOT contain logic
must NOT manipulate DB directly

It only:

sends commands
receives state
⚖️ LAW 4 — EVERYTHING IS A MODULE

No direct coupling like:

UI → DB
Audio → DB

Instead:

UI → Application Layer → Core Engine → Modules
⚖️ LAW 5 — AI IS A LAYER, NOT A FEATURE

Agent system must NOT:

directly edit DB
directly edit UI

Instead:

AI → Document Model → validated → applied
⚖️ LAW 6 — INTERLINEAR IS FIRST-CLASS CITIZEN

Not optional.

Your system must treat:

Arabic / Urdu / Gujarati / English
as linked structures, not strings.
⚖️ LAW 7 — OFFLINE-FIRST IS MANDATORY

Already aligned with your report:

local DB ✔
no cloud dependency ✔

We preserve this.

🧭 2. SYSTEM BLUEPRINT (HIGH-LEVEL ARCHITECTURE)

Here is your actual architecture:

┌──────────────────────────────┐
│        UI Layer              │
│  (PyQt + Future Web UI)      │
└────────────┬─────────────────┘
             ↓
┌──────────────────────────────┐
│     Application Layer        │
│  (Commands / Controllers)    │
└────────────┬─────────────────┘
             ↓
┌──────────────────────────────┐
│      CORE ENGINE             │
│  (Document + Schema)         │
└───────┬───────────┬──────────┘
        ↓           ↓
 ┌────────────┐  ┌──────────────┐
 │ AI Layer   │  │ Audio Engine │
 └────────────┘  └──────────────┘
        ↓
 ┌──────────────────────────────┐
 │   Rendering Layer            │
 │ (PDF / EPUB / Future Web)    │
 └────────────┬─────────────────┘
             ↓
┌──────────────────────────────┐
│        Storage Layer         │
│      (SQLite current)        │
└──────────────────────────────┘
🧱 3. CORE PILLARS (Development Order)

This is your execution order — do not break this:

🧩 PILLAR 1 — DOCUMENT ENGINE
schema
node system
validation
🧩 PILLAR 2 — EDITOR CORE
structured editing
block manipulation
🧩 PILLAR 3 — INTERLINEAR SYSTEM
word bundles
sync logic
🧩 PILLAR 4 — COLLABORATION (CRDT later)
🧩 PILLAR 5 — AI AGENTS
🧩 PILLAR 6 — EXPORT PIPELINE (already partially done)
🗂️ 4. PERFECT PROJECT STRUCTURE (YOU MUST ADOPT)

Refactor your repo into this:

maktaba-os/
│
├── apps/
│   ├── desktop/        # PyQt app
│   └── web/            # Future React app
│
├── core/
│   ├── document/       # 🔥 MOST IMPORTANT
│   ├── schema/
│   ├── commands/
│   ├── engine/
│   └── validation/
│
├── modules/
│   ├── editor/
│   ├── interlinear/
│   ├── ai/
│   ├── audio/
│   └── export/
│
├── infrastructure/
│   ├── database/
│   ├── logging/
│   └── config/
│
├── assets/
│   ├── templates/
│   └── fonts/
│
├── tests/
│
└── README.md
📘 5. README (FOUNDATION VERSION)

Here is your official base README:

Writing
Maktaba-OS
Vision

Maktaba-OS is a next-generation publishing operating system designed to unify writing, formatting, multilingual interlinear text processing, AI-assisted generation, and global distribution into a single cohesive platform.

Core Principles
Schema-first document architecture
Interlinear multilingual support as a native feature
Offline-first system design
Modular and extensible architecture
AI as an augmentation layer, not a replacement
Architecture

The system is built as a hybrid desktop-web application:

Desktop: PyQt (primary execution environment)
Web: React (future scalability layer)
Core Modules
Document Engine
Interlinear Engine
AI Agent System
Audio Processing Engine
Export Engine (PDF / EPUB)
Development Rules
No feature bypasses the document schema
No direct UI-to-database interaction
All transformations pass through the core engine
Maintain strict modular boundaries
Status

Foundation phase — Core architecture under construction.

🧾 6. ENGINEERING RULES (FOR YOU / FUTURE TEAM)
🔒 DO:
Build schema first
Validate every data mutation
Keep modules isolated
❌ DO NOT:
Add random JSON fields
Let UI mutate DB directly
Mix logic into export layer