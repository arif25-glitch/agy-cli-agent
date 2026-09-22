# 🪐 Gemini-Hermes AI Agent `v1.5.0`

**Gemini-Hermes** is an autonomous, persistent, and self-improving AI agent colleague combining **Nous Research's Hermes Agent** cognitive architecture with **Google Antigravity CLI (`agy`)** as its proxy model execution engine, accessible anywhere via a **Telegram Gateway**.

> **Release v1.5.0 Highlights:**
> - **Tiered Quality Memory Architecture**: Structured separation between fast in-prompt working context ("Hot Memory") and permanent on-disk archives ("Warm Memory" in `data/memory/archive/BACKLOG_ARCHIVE.md`), preventing attention dilution while retaining 100% of historical milestones.
> - **Dynamic Hot Backlog Capping**: In-prompt working context automatically preserves 100% of active tasks `[ ]` while dynamically capping resolved items `[x]` to the 4–5 most recent entries with off-prompt archival pointers.
> - **Telegram `/compact` Command**: One-touch memory compaction and pruning command reporting live telemetry (archived tasks, hot memory tokens, total disk persistence).
> - **Mid-Flight Steering (`/steer`)**: Immediate course-correction command that cleanly halts active turns, captures progress context, and restarts execution along new parameters without race conditions.
> - **Zero Status Spam (In-Place Status Editing)**: In-place dynamic editing of status messages across intermediate tool executions (`🔨 *Currently:* <action>`), eliminating notification clutter.
> - **Rigorous Dual Verification Suite**: Automated positive and negative test coverage across memory tiering, steering, and gateway dispatch (39 passing unit/integration tests).

---

## 🏛️ Architecture Overview

Gemini-Hermes follows a Direct Autonomous Orchestrator body-brain design:

```mermaid
flowchart TD
    User([Telegram User]) <-->|Messages, Media, /btw & /steer| TG[Telegram Gateway\n(Long Polling / httpx / Formatter)]
    
    subgraph Gemini-Hermes Core [Gemini-Hermes Execution Engine]
        TG --> Router[Message Router & Concurrency Guard]
        Router --> Queue[Task Queue & /btw Dispatcher]
        Queue --> PromptEngine[Prompt & Persona Engine]
        
        subgraph Persistent State Layer
            MemStore[(Hot Working Memory\nMEMORY.md, USER.md,\nBACKLOG.md, REFERENCES.md)]
            Archive[(Warm Memory Archive\ndata/memory/archive/)]
            ProjStore[(Project State Index\ndata/projects/projects.json)]
            Skills[(Skills Catalog\n9 Modular Procedures)]
            Sessions[(SessionDB\nTurn Metrics & History)]
        end
        
        MemStore --> PromptEngine
        Archive -.->|On-Demand Retrieval| PromptEngine
        ProjStore --> PromptEngine
        Skills --> PromptEngine
        Sessions --> PromptEngine
        
        PromptEngine --> Forwarder[Antigravity Proxy Forwarder\n(300s Inactivity Reset / 900s Ceiling)]
    end
    
    Forwarder <-->|Stream NDJSON / Turn IO| AGY[Antigravity CLI\n(agy -p ... --output-format stream-json)]
    AGY <--> LLM[Google Gemini 3.8 Flash / Pro Engine]
    
    Forwarder -->|Real-Time Tool Actions & Status| TG
```

---


## ✨ Core Features & Hermes Capabilities

### 1. Direct Solo Execution & Context Hygiene
- **Direct Solo Execution**: Gemini-Hermes acts as a direct, hands-on engineer executing inspections, builds, tests, and file modifications directly in the session.
- **Subagent Prohibition**: Eliminates sub-agent spawning and delegation loops, preventing worker timeouts and context desynchronization.
- **Pristine Primary Context**: Guards the conversation against noise and token bloat with compact, high-signal reasoning traces.

### 2. Project State Indexing (Zero Context Loss)
- **Persistent Project Bookmarks**: Tracks active and completed projects in `data/projects/projects.json`.
- **Context Injection**: Project state, paths, tech stacks, and open milestones are automatically surfaced in the cognitive system prompt.
- **Commands**:
  - `/projects` — List all active and archived projects.
  - `/project <id>` — View detailed task status, stack, and notes.
  - `/project_add <name> <path>` — Bookmark a new project into persistent state.
  - `/project_task <id> <task>` — Attach a task to a project.

### 3. Side-Conversation & Task Queue (`/btw`)
- **Side-Quest / Live Telemetry**: Ask progress or status questions while a background task is running (e.g. `/btw where are you now?` or `/btw what are you working on?`). The bot replies instantly with live telemetry without interrupting the primary task.
- **Steering & Task Queueing**: Send steering directives or follow-up tasks (e.g. `/btw remember to check sources`, `/btw after this, write a summary`). It queues the instruction into an automated FIFO queue.
- **Autonomous Chaining**: Automatically dequeues and executes the queued task immediately once the active operation concludes.
- **Commands**: `/btw <query>`, `/queue`, `/cancel`.

### 4. Mid-Flight Course Correction (`/steer`)
- **Immediate Task Interception**: Cleanly halts an ongoing turn mid-flight when directives change, preventing wasted model execution or unwanted file modifications.
- **Context-Preserving Transition**: Captures prior task objectives, current action progress, and synthesizes an authoritative `[USER STEERING DIRECTIVE]` resuming seamlessly within the same conversation session without race conditions.
- **Idle Direct Execution**: When idle, `/steer <instruction>` immediately executes the directive as a top-priority command.
- **Commands**: `/steer <instruction>`.

### 5. Automatic Chat Queueing ("Zero Message Drop")
- **Multi-Message Conversational Flow**: Send multiple follow-up chats, clarifications, or thoughts naturally on Telegram while the agent is actively executing—no slash commands required.
- **Auto-Enqueue Engine**: Incoming plain text messages and media attachments (photos, documents) sent mid-flight are automatically placed into the sequential FIFO execution queue with instant position confirmation (`#1 in queue`, `#2 in queue`).
- **Capacity Protection**: Built-in capacity guard (`max_queue_size = 10`) protects host memory against spam or runaway queues with polite queue-full warnings.
- **Fault & Crash Resilience**: If an active task encounters an error or is redirected via `/steer`, the sequential queue is preserved and safely drained upon completion.
- **Commands**:
  - `/queue` — View active task status and all pending queued messages.
  - `/cancel` — Instantly abort active execution and flush the task queue.

### 6. Asynchronous Task Monitoring (`task_watcher`)
- **Zero Premature Exits**: Strictly prevents abandoning running builds or operations with premature "running in background" responses.
- **Active Verification**: Follows background tasks through completion via process monitoring and artifact validation.

### 7. Zero Status Spam (In-Place Message Editing)
- **Fluid Telegram UI**: Intermediate tool steps dynamically mutate the current message bubble rather than creating duplicate bubbles in Telegram.
- **Resilient Fallback**: Gracefully falls back to new messages if Telegram API edit limits or deletions occur.

### 8. Tiered Quality Memory & Context Hygiene (`/compact`)
- **Hot Working Context (In-Prompt)**: Dynamic hot memory keeps prompt tokens lean (~2k tokens) by capping resolved milestones to the 4–5 most recent items while retaining 100% of active tasks `[ ]`.
- **Warm Permanent Archive (On-Disk)**: Older completed tasks and multiline verification logs are moved to `data/memory/archive/BACKLOG_ARCHIVE.md`, preserving deep historical records off-prompt for on-demand tool inspection.
- **Dynamic Archival Indicators**: If older tasks are archived, prompt context displays a clean pointer (e.g. `- *(+N older completed tasks archived in data/memory/archive/BACKLOG_ARCHIVE.md)*`).
- **Commands**:
  - `/compact` — One-touch archival pass that trims resolved tasks from hot context and outputs real-time memory metrics.
  - `/memory` — Inspect all modular memory files and current token footprint.
  - `/memory_add <text>`, `/task_add <task>`, `/ref_add <title> | <url>`, `/memory_reset`.

### 9. Deliberate Cadence & Rigorous Dual Verification

- **Slow is Smooth, Smooth is Fast**: Rejects rushed, unverified code changes that create debugging debt.
- **Dual Verification**: Every feature or procedure must pass both positive (happy path) and negative (error boundary and fallback) testing.
- **5-Phase Skill Creation Pipeline**:
  1. **Phase 1: Goal & Boundary Definition** — Scope precise problem, input parameters, expected outputs, and trigger conditions.
  2. **Phase 2: Procedure & Edge-Case Architecture** — Map sequential workflow, isolate failure modes, and specify fallback paths.
  3. **Phase 3: Incremental Draft & Review** — Draft specification in digestible sections conforming to the `agentskills.io` standard.
  4. **Phase 4: Positive & Negative Stress Testing** — Simulate and verify happy-path and error recovery behaviors.
  5. **Phase 5: Catalog Registration & Packaging** — Commit to the active skill catalog only after rigorous verification.

---

## 🛠️ Modular Skills Catalog (9 Active Procedures)

Gemini-Hermes features 9 modular procedures conforming to the `agentskills.io` standard:

| Skill | Category | Description |
|---|---|---|
| `task_watcher` | Background / Verification | Monitoring and actively verifying asynchronous and long-running tasks until confirmed completion. |
| `multi_step_researcher` | Research / Synthesis | Systematic multi-step technical web research, official docs triangulation, and dense synthesis. |
| `auto_debugger` | Debugging / Diagnostics | Error log parsing, stack trace isolation, root cause hypothesis testing, and surgical patching. |
| `api_tester` | API / Validation | Probing REST/HTTP endpoints, contract mapping, curl execution, and JSON schema validation. |
| `system_monitor` | System / DevOps | Host resource auditing (CPU, RAM, disk space), daemon process checks, and cron health alerting. |
| `task_scheduler` | Scheduling / Cron | Procedure for managing delayed tasks, one-shot reminders, and recurring cron operations. |
| `memory_keeper` | Memory / Context | Best practices for managing persistent modular memory (`MEMORY.md`, `USER.md`, `BACKLOG.md`, `REFERENCES.md`). |
| `shell_execution` | Shell / Linux | Safe and effective execution of host shell commands with exit code and error handling. |
| `skill_creator` | Meta / Self-Improvement | Autonomous formulation, validation, and saving of new reusable skills into the knowledge base. |

---

## 📱 Telegram Command Reference

| Command | Description |
|---|---|
| `/start` | Welcome greeting, agent status, and quick instructions |
| `/help` | Complete reference manual of features and commands |
| `/new` or `/reset` | Clear conversation thread, purge task queues, and begin fresh session |
| `/status` | View engine health, active conversation ID, turns, token counts, and indexed projects |
| `/btw <msg>` | Query live telemetry, ask side trivia, or queue follow-up directives while an operation runs |
| `/steer <instruction>` | Immediately course-correct or redirect the agent mid-flight (or apply focused direction if idle) |
| `/queue` | View active background task status and pending `/btw` queued items |
| `/cancel` | Safely abort ongoing background tasks and clear pending queues |
| `/projects` | List all bookmarked projects, status, and repository paths |
| `/project <id>` | Inspect detailed architectural state, notes, and task progress |
| `/project_add <name> <path>` | Bookmark a new project into persistent state |
| `/project_task <id> <task>` | Attach a new task or milestone to an indexed project |
| `/memory` | Inspect modular memory domains (`MEMORY.md`, `USER.md`, `BACKLOG.md`, `REFERENCES.md`) |
| `/compact` | Archive older completed tasks to `data/memory/archive/` and keep working context sharp |
| `/memory_add <text>` | Manually save a permanent operational fact or rule to `MEMORY.md` |
| `/task_add <task>` | Append an active task or inquiry directly to `BACKLOG.md` |
| `/ref_add <title> \| <url>` | Save an external spreadsheet, documentation, or resource link to `REFERENCES.md` |
| `/memory_reset` | Reset persistent memory to default initial state |
| `/skills` | List all modular procedural skills currently installed |
| `/skill <name>` | Display the exact instructions and metadata of a specific skill |
| `/exec <command>` | Run an authorized shell command directly on the host machine |

---

## 🚀 Quick Start Guide

### Step 1: Configure Environment

Run the setup wizard:
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

### Step 2: Test Diagnostics

Run the comprehensive test suite to verify connectivity:
```bash
./run.sh test
```

### Step 3: Run Gemini-Hermes

**Daemon Mode (Recommended):**
```bash
./run.sh background
```
- Live logs: `./run.sh logs`
- Status: `./run.sh status`
- Stop: `./run.sh stop`
- Safe Restart: `bash /gemini-hermes/restart_bot.sh`

**Interactive Foreground Mode:**
```bash
./run.sh start
```

---

## 📂 Project Directory Structure

```
/gemini-hermes/
├── README.md                      # Comprehensive project documentation
├── CHANGELOG.md                   # Semantic version history and release logs
├── requirements.txt               # Python dependencies
├── run.sh                         # CLI service management script
├── restart_bot.sh                 # Graceful lifecycle-aware daemon reloader
├── .env.example                   # Environment configuration template
├── gemini_hermes/
│   ├── __init__.py                # Package version definition (v1.4.1)

│   ├── config.py                  # Settings loader & path constants
│   ├── cli.py                     # CLI commands (start, setup, test, status)
│   ├── brain/
│   │   ├── agy_forwarder.py       # Proxy forwarder to Antigravity CLI
│   │   └── stream_parser.py       # NDJSON stream and tool event parser
│   ├── projects/
│   │   ├── __init__.py
│   │   └── manager.py             # Project state indexing & task tracking
│   ├── memory/
│   │   ├── store.py               # Memory persistence and session manager
│   │   └── templates.py           # Default memory blueprints
│   ├── skills/
│   │   ├── manager.py             # Modular skill discovery and parser
│   │   └── builtin/               # 8 Built-in procedural skills
│   ├── persona/
│   │   └── system_prompt.py       # Cognitive depth & prompt builder
│   └── gateway/
│       ├── telegram_bot.py        # Gateway bot (polling, queues, /btw, status push)
│       └── formatter.py           # Telegram Markdown formatting & sanitizers
└── data/
    ├── memory/                    # MEMORY.md, USER.md, BACKLOG.md, REFERENCES.md
    ├── projects/                  # projects.json (bookmarked projects)
    ├── sessions/                  # sessions.json (chat threads & metrics)
    ├── media/                     # Ingested Telegram photos and documents
    └── skills/                    # Custom and learned skills catalog
```
