# Changelog

All notable changes to the Gemini-Hermes AI Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2026-09-18
 
### Added
- **Sub-Agent Fleet Sizing & Concurrency Rules**: Codified optimal swarm fleet sizing boundaries (2 to 6 targeted specialists, e.g. Frontend Architect, Backend Developer, QA/Tester, Deep Researcher) into persistent memory (`MEMORY.md`), user preferences (`USER.md`), and the `manager_delegation` procedural skill (`SKILL.md`).
- **Resource & Token Protection**: Prevents proxy model token rate-limiting, host CPU/RAM exhaustion, and coordination signal dilution during complex parallel multi-agent orchestrations.

## [1.3.0] - 2026-09-18

### Added
- **Executive Manager Pattern & Context Hygiene**: Formalized Engineering Manager cognitive architecture where high-context tasks (large file reading, deep documentation exploration, verbose build logs) are proactively offloaded to worker sub-agents (`research` or `self`). The primary context stays compact, pristine, and high-quality, maximizing long-term conversational memory.
- **`manager_delegation` Skill**: Modular procedure for offloading high-context exploration, heavy file builds, and log analysis to worker sub-agents with dense executive synthesis.
- **Project State Indexing**: Persistent project state bookmarks in `data/projects/projects.json` via `ProjectManager`, injected directly into the cognitive system prompt to prevent context loss across sessions.
- **Telegram Project Management Commands**:
  - `/projects`: List all indexed projects, tech stacks, and active tasks.
  - `/project <id>`: Inspect detailed state, notes, and task progress of a project.
  - `/project_add <name> <path> [desc]`: Bookmark a new project into persistent state.
  - `/project_task <id> <task>`: Attach a milestone or task to an indexed project.
- **Expanded Skills Catalog**: Registered 4 new procedural skills:
  - `multi_step_researcher`: Systematic technical web research and documentation triangulation.
  - `auto_debugger`: Error isolation, stack trace parsing, and surgical patch verification.
  - `api_tester`: REST/HTTP contract validation, curl testing, and schema validation.
  - `system_monitor`: System resources, memory/disk checks, and daemon health audit.
- **Process Lifecycle Detection in Restart**: `restart_bot.sh` now monitors and waits for active `agy` execution to conclude and deliver Telegram messages before gracefully reloading daemon processes.

## [1.2.0] - 2026-09-18

### Added
- **`/btw` Side-Conversation & Task Queue**: Dual-mode interactive steering and telemetry querying while a background task is running.
  - *Side-Quest / Telemetry Mode*: Immediate answers to live status questions (`/btw where are you now?`) without disturbing or canceling the active task.
  - *Steering & Task Queueing Mode*: Queues follow-up tasks and directives (`/btw remember to use Tailwind`) into a FIFO execution pipeline.
  - *Autonomous Chaining*: Automatically dequeues and executes pending tasks upon completion of the primary task.
- **`/queue` Command**: View live active operation state and all pending queued `/btw` instructions.
- **`/cancel` Command**: Safely abort running background tasks and clear all pending queue items.
- **Real-Time Status Push ("Bomb Chat")**: Live tool action messages (`🔨 Currently, <action>...`) pushed directly to Telegram throttled at 1.2s.
- **Streaming Markdown Hardening**: Automatic balancing for unclosed italic underscores and bold markers during real-time streaming preview.
- **Extended Forwarder Ceilings**: Inactivity timeout expanded to 300s (5 minutes) with active reset, and total ceiling increased to 900s (15 minutes).
- **Contextual Timeout Diagnostics**: Error messages report the exact last active tool step and recovery actions.
- **`task_scheduler` Skill**: Procedural skill for scheduling one-shot timers and recurring cron operations.

### Fixed
- Fixed Telegram API `400 Bad Request: unsupported parse_mode` by omitting `parse_mode` when `None`.
- Fixed streaming entity parsing errors caused by unclosed markdown formatting across chunk boundaries.

## [1.1.0] - 2026-09-17

### Added
- Initial proxy integration with Google Antigravity (`agy-cli`) execution engine.
- Persistent long-term memory store (`MEMORY.md` and `USER.md`).
- Modular procedural skills architecture with auto-discovery.
- Telegram gateway bot with media ingestion (images, PDFs, documents).
- Multi-agent orchestration directives and executive worker delegation model.
