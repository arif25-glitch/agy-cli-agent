# 🪐 Gemini-Hermes AI Agent

**Gemini-Hermes** is an autonomous, persistent, and self-improving AI agent colleague inspired by **Nous Research's Hermes Agent**, powered by **Google Antigravity CLI (`agy`)** as its proxy model execution engine, and connected via a **Telegram Gateway**.

---

## 🏛️ Architecture Overview

Gemini-Hermes follows the body-brain architecture:

```mermaid
flowchart TD
    User([Telegram User]) <-->|Messages & Commands| TG[Telegram Gateway\n(Long Polling / httpx)]
    
    subgraph Gemini-Hermes Engine
        TG --> Router[Message Router & Whitelist Auth]
        Router --> PromptEngine[Prompt & Persona Engine]
        
        subgraph Persistent State
            MemStore[(Memory Layer\nMEMORY.md & USER.md)]
            Skills[(Skills Catalog\nagentskills.io Standard)]
            Sessions[(SessionDB\nTurn Metrics & History)]
        end
        
        MemStore --> PromptEngine
        Skills --> PromptEngine
        Sessions --> PromptEngine
        
        PromptEngine --> Forwarder[Antigravity CLI Proxy Forwarder\n(AgyForwarder)]
    end
    
    Forwarder <-->|Stream NDJSON / Turn IO| AGY[Antigravity CLI\n(agy -p ... --output-format stream-json)]
    AGY <--> LLM[Google Gemini 3.8 Flash / Pro Engine]
    
    Forwarder -->|Real-Time Token Deltas & Progress| TG
```

---

## ✨ Inherited Hermes Capabilities

Gemini-Hermes inherits all defining features of Nous Research's Hermes Agent:

1. **Persistent Memory System (`MEMORY.md` & `USER.md`)**:
   - **Continuous Memory Across Restarts**: Retains facts, project knowledge, decisions, and system configurations.
   - **User Profile Tracking**: Stores user preferences, style requirements, and identity information in `USER.md`.
   - **Dynamic Context Injection**: Pertinent memories are automatically injected into the agent's context during conversation.
   - **Commands**: `/memory`, `/memory_add <text>`, `/memory_reset`.

2. **Self-Improving Skills Loop (`agentskills.io` Standard)**:
   - **Modular Reusable Procedures**: Skills are stored as YAML frontmatter + Markdown in `data/skills/<name>/SKILL.md`.
   - **Autonomous Skill Discovery**: Gemini-Hermes can formulate, validate, and persist new skills dynamically when solving novel tasks (`skill_creator`).
   - **Commands**: `/skills`, `/skill <name>`.

3. **Cognitive Depth & Scratchpad Reasoning**:
   - Incorporates structured `<thinking>` scratchpad reasoning tags for goal formulation, skill selection, and step-by-step planning before generating final responses.
   - Expandable and beautifully formatted in Telegram messages.

4. **Antigravity CLI (`agy`) Proxy Model Engine**:
   - Acts as a local API forwarder to Google Antigravity.
   - Native streaming via NDJSON output (`--output-format stream-json`).
   - Session continuity across turns using `--conversation <conversation_id>`.
   - Autonomous tool permissions (`--dangerously-skip-permissions`).
   - Tunable reasoning effort (`--effort low|medium|high`).

5. **Telegram Gateway**:
   - Live streaming updates: updates message tokens live while typing.
   - Whitelist authorization: strictly restricts access to specified Telegram `ALLOWED_USER_IDS` to ensure server safety.
   - Long messages automatically split cleanly across Telegram's 4096 character boundaries.

---

## 🚀 Quick Start Guide

### Step 1: Create your Telegram Bot & Get User ID
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, choose a name and username (e.g. `my_hermes_bot`).
3. BotFather will provide an API HTTP Token: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`.
4. To find your personal Telegram numeric User ID:
   - Message [@userinfobot](https://t.me/userinfobot) on Telegram and it will reply with your `Id: 12345678`.

### Step 2: Configure Gemini-Hermes

Run the interactive setup wizard:
```bash
cd /gemini-hermes
./run.sh setup
```
Or edit `/gemini-hermes/.env` directly:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_ALLOWED_USERS=12345678
AGY_BIN=/root/.local/bin/agy
REASONING_EFFORT=medium
STREAM_UPDATES=true
STREAM_EDIT_INTERVAL=1.2
```

### Step 3: Test System Diagnostics

Run the diagnostic tool to verify all components:
```bash
./run.sh test
```

### Step 4: Launch Gemini-Hermes

**In foreground (interactive):**
```bash
./run.sh start
```

**Or in background (daemon mode):**
```bash
./run.sh background
```
- View live logs: `./run.sh logs`
- Check daemon status: `./run.sh status`
- Stop daemon: `./run.sh stop`

---

## 📱 Telegram Slash Commands

| Command | Description |
|---|---|
| `/start` | Welcome greeting, agent status, and quick instructions |
| `/help` | Complete help manual of features and commands |
| `/new` or `/reset` | Clear the current conversation thread and start a fresh session |
| `/status` | View engine health, active conversation ID, turns, and token counts |
| `/memory` | Inspect `MEMORY.md` (long-term memory) and `USER.md` (user profile) |
| `/memory_add <text>` | Manually append a persistent note or fact to memory |
| `/memory_reset` | Reset persistent memory to default initial state |
| `/skills` | List all installed and learned procedural skills |
| `/skill <name>` | View full instructions and metadata for a specific skill |
| `/exec <command>` | Run a shell command directly on the host (authorized user only) |

---

## 📂 Project Structure

```
/gemini-hermes/
├── README.md                  # Complete documentation
├── requirements.txt           # Python dependencies (httpx, pydantic, pyyaml)
├── run.sh                     # Start / stop / setup / background manager
├── .env.example               # Configuration template
├── .env                       # Active environment configuration
├── gemini_hermes/
│   ├── config.py              # Settings loader & path resolution
│   ├── cli.py                 # CLI interface for setup, test, and execution
│   ├── brain/
│   │   ├── agy_forwarder.py   # Subprocess proxy forwarder to agy CLI
│   │   └── stream_parser.py   # NDJSON event stream parser
│   ├── memory/
│   │   ├── store.py           # MEMORY.md, USER.md, and session store
│   │   └── templates.py       # Default memory templates
│   ├── skills/
│   │   ├── manager.py         # Skill loader adhering to agentskills.io standard
│   │   └── builtin/           # Bootstrap skills (skill_creator, memory_keeper, etc.)
│   ├── persona/
│   │   └── system_prompt.py   # Hermes cognitive depth persona & scratchpad prompt
│   └── gateway/
│       ├── telegram_bot.py    # Telegram Bot service (long polling, streaming edits)
│       └── formatter.py       # Telegram Markdown formatting & message chunker
└── data/
    ├── memory/                # MEMORY.md & USER.md storage
    ├── sessions/              # Chat sessions & conversation ID mapping
    └── skills/                # User-created and autonomously learned skills
```
