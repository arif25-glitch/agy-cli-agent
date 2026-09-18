# Changelog

All notable changes to the Gemini-Hermes AI Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.7] - 2026-09-18

### Added
- **Modular Multi-Domain Memory Architecture**: Refactored `MemoryStore` into four distinct storage domains: `MEMORY.md` (operational standards), `USER.md` (user preferences and communication rules), `BACKLOG.md` (active task queue and operational inquiries), and `REFERENCES.md` (external spreadsheets, documentation, and links).
- **Telegram Gateway Memory Commands**: Added `/task_add <task>` to append items directly to `BACKLOG.md` and `/ref_add <title> | <url>` to record documentation and sheets in `REFERENCES.md`.
- **Domain-Specific Prompt Context Injection**: Updated `render_memory_context` to inject structured XML tags (`<persistent_memory>`, `<user_profile>`, `<active_backlog>`, `<external_references>`) to optimize context hygiene and retrieval accuracy.
- **Updated Memory Keeper Procedure**: Upgraded `memory_keeper` skill to v1.1.0 documenting best practices for multi-domain persistent memory.

## [1.3.6] - 2026-09-18

### Changed
- **Decommissioned Subagent Delegation Across Engine**: Switched agent execution paradigm strictly to Direct Solo Execution mode.
- **System Prompt & Persona Optimization**: Removed `Executive Manager Pattern & Context Hygiene (Worker Offloading)` and `Subagent Orchestration` sections from `HERMES_BASE_INSTRUCTIONS`, establishing explicit prohibition against invoking subagents.
- **Skills Catalog Streamlined**: Completely removed `manager_delegation` procedural skill from builtin and runtime skill registries. Refactored `multi_step_researcher` and `system_monitor` skills to operate exclusively under direct single-agent execution.
- **Memory & Rules Pruned**: Updated persistent memory (`MEMORY.md`) and user operational rules (`USER.md`) to decommission worker swarm directives and enforce hands-on execution.
- **Gateway & Telemetry Simplification**: Removed asynchronous subagent follow-through loops and worker-specific status pulses from `TelegramBot` and `stream_parser`.

## [1.3.5] - 2026-09-18

### Fixed
- **Subagent Delegation Timeouts & Stalls**: Added explicit `--print-timeout` flag to `AgyForwarder` (defaulting to 900s), eliminating the silent 5-minute CLI print-timeout drop during subagent execution.
- **Active Subagent Follow-Through Loop**: Added automated detection of asynchronous subagent dispatch states in `TelegramBot`. Instead of prematurely terminating turns and abandoning conversations, the bot maintains active follow-through, awaiting and delivering worker syntheses directly to Telegram.
- **Periodic Tool & Subagent Progress Heartbeat**: Added `tool_heartbeat` in `TelegramBot` that emits progress pulses every 15-20s during prolonged tool runs (e.g. subagents or heavy compilations), ensuring Telegram never goes dark.
- **Subagent Velocity & Prompt Scoping**: Updated `manager_delegation` skill and `HERMES_BASE_INSTRUCTIONS` with strict 2-4 minute velocity boundaries (max 5-15 steps per worker) to prevent overloaded 100-step worker executions.

## [1.3.4] - 2026-09-18

### Added
- **Worker Subagent Telemetry Transparency**: Enhanced `stream_parser` to extract worker role and specialist context from `invoke_subagent` calls (e.g. `🔨 Currently, worker (Next.js Frontend Engineer) - Scaffold Next.js project...`).
- **Telemetry Disambiguation**: Clarified live execution updates so users immediately distinguish between primary manager orchestration and background subagent worker tasks.
- **Typing Indicator State Synchronization**: Paused the Telegram `typing...` action when tools/worker subagents are executing, ensuring the typing indicator only displays when the agent is actively synthesizing response text.
- **Bot Restart Script Integrity**: Fixed directory paths in `restart_bot.sh` to resolve to the active working root `/home/arif/agy-hermes`.

## [1.3.3] - 2026-09-18

### Changed
- **Sanitized Production Release Distribution**: Reset `data/projects/projects.json` to an empty state `{}` on `main` and refactored `ProjectManager._ensure_file()` to initialize empty project states for clean installs, isolating personal scratch project bookmarks to development branches (`feature/agy-arif`).
- **Lean Persistent Memory Architecture**: Pruned `MEMORY.md` and `USER.md` by stripping redundant system directives and converting operational standards, timeout parameters, and user preferences into dense, high-signal 1-line directives.
- **Generic User Starter Templates**: Provided clean generic starter templates on `main` for public deployers.

## [1.3.2] - 2026-09-18

### Added
- **Automated Login Token Session Detection & Interactive Prompt**: Added `token_manager` module that verifies the presence and integrity of Antigravity CLI (`agy`) OAuth sessions (`antigravity-oauth-token`). If no active session is found, prompts the user to paste their JSON token, specify an existing token file path, or launch Google OAuth login directly.
- **Cross-Account Session Auto-Import**: Detects readable token sessions from standard system locations (e.g. `/root/.gemini/antigravity-cli/antigravity-oauth-token`) and automatically imports them for non-root users with `0600` permissions.
- **Robust Forwarder Health Checks**: Hardened `AgyForwarder.check_health()` by binding standard input to `/dev/null` and adding process-kill timeout handling to prevent blocking on unauthenticated CLI prompts.
- **Virtual Environment Auto-Detection**: `run.sh` automatically checks for and activates `$SCRIPT_DIR/.venv/bin/python3` when available.

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
