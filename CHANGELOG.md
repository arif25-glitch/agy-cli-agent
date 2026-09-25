# Changelog

All notable changes to the Gemini-Hermes AI Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.3] - 2026-09-25

### Added
- **Autonomous Memory Pruner & Archival (`gemini_hermes/jev/memory_pruner.py`, `gemini_hermes/memory/archiver.py`)**:
  * Added autonomous memory pruning retaining the most recent active tasks and memory notes while cleanly archiving completed tasks to `data/memory/archive/BACKLOG_ARCHIVE.md`.
  * Integrated Jev-accelerated semantic pruning with robust zero-dependency deterministic fallback.
- **JIT Dynamic Skill Selector (`gemini_hermes/jev/skill_selector.py`)**:
  * Implemented dynamic intent-to-skill matching that injects only relevant procedural skills per turn rather than the monolithic catalog, drastically reducing input token overhead.
- **Context Bridge & Relative Growth Session Rotation (`gemini_hermes/memory/session_store.py`, `gemini_hermes/gateway/runner.py`)**:
  * Implemented relative token growth and turn-based context rotation to prevent token explosion.
  * Maintained seamless agent continuity across rotations using an automated `<context_bridge>` summary.
- **Differential Follow-Up Prompt Architecture (`gemini_hermes/persona/system_prompt.py`)**:
  * Optimized multi-turn conversations using lean differential prompts on follow-up turns (`turn > 0`) while maintaining strict base instructions on session initialization (`turn 0`).
- **Comprehensive Dual Verification Test Suite**:
  * Added dedicated test suites: `tests/test_autonomous_memory_pruning.py`, `tests/test_relative_growth_rotation.py`, and `tests/test_token_efficiency.py`, expanding the full test suite to 150 passing unit tests.

## [1.7.2] - 2026-09-25

### Added
- **Session Token Reset & Lifetime Tracking on `/new` and `/reset`**:
  * **Session-Scoped vs Lifetime Metrics (`SessionStore`)**: Separated `session_input_tokens` and `session_output_tokens` from aggregate `total_input_tokens`, `total_output_tokens`, and `lifetime_turns`.
  * **Reset Command Synchronization (`handle_reset`)**: Resetting conversational state via `/new` or `/reset` now clears the active session token counter (`0 in / 0 out`, `0 turns`) while preserving historical lifetime token aggregations across all sessions.
  * **Instant Telemetry Broadcasting**: `handle_reset` immediately emits idle telemetry with 0 active session tokens, ensuring `./run.sh monitor` refreshes the dashboard immediately.
  * **Telegram `/status` Command Enhancement**: Displays both *Session Tokens* and *Lifetime Tokens* breakdown in status output.
  * **Automated Dual Verification**: Added unit tests in `tests/test_cli_monitor.py` and `tests/test_gemini_hermes.py` validating session token isolation, reset synchronization, and lifetime persistence.

## [1.7.1] - 2026-09-25

### Added
- **Session & Global Token Usage Tracking in Terminal UI Dashboard (`./run.sh monitor`)**:
  * **Session & Lifetime Aggregate Calculations (`SessionStore` & `MemoryStore`)**: Added `get_total_token_usage()` and `get_session_token_usage(chat_id)` to calculate authoritative input, output, total tokens, session counts, and turn metrics directly from Antigravity engine stream receipts.
  * **Live Telemetry Exporter Integration (`TelemetryExporter` & `ExecutionRunner`)**: Exported real-time session and global token snapshots to atomic `telemetry.json` at turn initialization and turn completion.
  * **Dedicated Token Usage UI Panel (`CliMonitor`)**: Added rich `build_token_usage_panel` to `./run.sh monitor` dashboard displaying:
    - **Active Session**: Chat ID, Input / Output tokens, Session Total tokens, and Turn count.
    - **Global Lifetime**: Tracked active sessions count, Total turns, Global Input / Output tokens, and Lifetime Total token usage.
    - **Smart Metric Formatting**: Human-readable thousands (`1.5k`) and millions (`216.29M`) suffixes with fallback disk inspection when offline or idle.
  * **Automated Dual Verification Test Suite**: Added positive and negative test cases in `tests/test_cli_monitor.py` covering token formatting, empty/populated session aggregations, offline fallback, and full dashboard rendering.

## [1.7.0] - 2026-09-24

### Added
- **Dynamic Model Selection & 4-Tier Workload Routing via Jev AI System-One**:
  * **Intelligent Workload Routing**: Inbound user prompts are evaluated prior to model dispatch, dynamically selecting both the optimal Antigravity model and reasoning effort based on cognitive complexity:
    - **Tier 1 (`gemini-3.6-flash`, `low` effort)**: Cheapest / fastest for simple interaction, greetings, smalltalk, and casual chat (fast reflex with 0 thinking tokens).
    - **Tier 2 (`gemini-3.7-flash`, `medium` effort)**: Balanced for standard coding, single-file edits, and moderate debugging.
    - **Tier 3 (`gemini-3.8-flash`, `high` effort)**: High-workload multi-file architecture, complex refactoring, and deep agentic runs.
    - **Tier 4 (`gemini-3.1-pro`, `high` effort)**: Deep algorithmic reasoning and formal mathematical logic.
  * **Structured Reflex Primitives**: Integrated `model_tier` `Choice` primitive in `gemini_hermes/jev/client.py` and `gemini_hermes/services/jev_service.py` with calibrated complexity score thresholds in `gemini_hermes/jev/effort_selector.py`.
- **AgyForwarder & ExecutionRunner Dynamic Execution**:
  * `AgyForwarder._build_command` passes `--model <selected_model>` to `agy` CLI alongside `--effort <effort>`.
  * `ExecutionRunner` decorates live Telegram status bubbles with the active model and effort tag (e.g. `💭 *Gemini-Hermes is thinking [gemini-3.8-flash] (high effort)...*` or `💭 *Gemini-Hermes is thinking [gemini-3.6-flash] (fast reflex)...*`).
- **Telegram `/model` Command & Alias Resolution**:
  * Added `/model` command in `gemini_hermes/gateway/handlers/system_handlers.py` to inspect active model, selection mode (Dynamic vs Static), and tier breakdown.
  * Supported alias switching (e.g. `/model 3.6`, `/model 3.7`, `/model 3.8`, `/model pro`) with runtime forwarder updates.
- **Terminal UI Dashboard Telemetry (`./run.sh monitor`)**:
  * Live monitoring of dynamically selected model, reasoning effort, fast-path tags, and turn progression in `gemini_hermes/cli_monitor.py`.
- **Dual Verification Test Suite Expansion**:
  * Added dedicated dual-verification test suite `tests/test_dynamic_model.py` (13 positive and negative tests covering Tier 1–4 routing, Jev choice overrides, forwarder command building, runner execution, telegram commands, timeout fallbacks, API error fallbacks, and invalid models).
  * Expanded total automated test suite to **123 passing unit & integration tests** (100% pass rate).

## [1.6.0] - 2026-09-24

### Added
- **Modular Gateway Architecture Refactoring**:
  * Deconstructed monolithic `telegram_bot.py` into clean, modern architectural layers: `services/telegram_client.py` (API transport), `helpers/` (`reply_parser.py`, `intent_classifier.py`), `handlers/` (modular command & lifecycle handlers), `models.py` (`QueuedTask`), and `runner.py` (`ExecutionRunner`). Preserved 100% backward compatibility for all existing scripts and tests.
- **TypeSafe AI (Jev) Foundation & Isolated System-One Shell**:
  * **100% Optional Architecture**: Core Gemini-Hermes operates independently with zero required TypeSafe dependencies. Kept core `requirements.txt` ultra-lean and provided `requirements-jev.txt` for optional Jev reflex capabilities (`typesafe-sdk>=0.7.1`).
  * **Decoupled Service Shell (`JevService`)**: Created `gemini_hermes/services/jev_service.py` with strict timeout guards (`asyncio.wait_for`, default 5.0s) and silent fallback to standard execution if TypeSafe is down, slow, or disabled.
  * **Structured Reflex Models**: Added `JevReflexDecision` dataclass capturing Choice, Score, and Noul outputs (`intent`, `complexity_score`, `needs_deep_reasoning`, `latency_ms`).
  * **Interactive Configuration Wizard (`./run.sh config`)**: Added dedicated CLI configuration command and wizard to easily configure `TYPESAFE_API_KEY`, `TYPESAFE_MODEL`, `TYPESAFE_API_BASE`, and `JEV_ENABLED` without clobbering existing `.env` values.
  * **System Diagnostics Integration**: Added TypeSafe AI readiness check to `./run.sh test` (Section 5) inspecting credentials and SDK installation without invoking paid tokens.
  * **Live Verification Harness**: Added `scripts/test_typesafe_live.py` for testing connectivity and primitive responses against live TypeSafe servers.
- **Dual Verification Test Suite Expansion**:
  * Added 8 unit tests in `tests/test_modular_gateway.py`.
  * Added 11 unit tests in `tests/test_jev_service.py` covering positive and negative/resilience paths.
  * Total project tests increased from 62 to **81 passing unit tests** (100% pass rate).

## [1.5.2] - 2026-09-23

### Added
- **Targeted Telegram Message Quoting & Contextual Reply Awareness**:
  * **Outbound Message Targeting**: Bot responses and initial thinking status bubbles pass `reply_to_message_id` and Telegram 7.0+ `reply_parameters` with `allow_sending_without_reply=True`, visually linking bot answers to originating user prompts.
  * **Inbound Reply Context Extraction**: When users swipe or reply to messages in Telegram, contextual metadata (`[Replying to message from <Sender>: "<quoted preview>"]`) is automatically extracted and injected into the prompt context.
  * **Broad Media Type Quoting**: Full inbound quote support for text, photos, documents, voice messages, audio files, videos, stickers (with emoji), polls, shared locations, and contacts.
  * **Secondary Zero-Drop Fallback**: If Telegram API rejects reply targeting on both Markdown and plain-text attempts (e.g. deleted message or server mismatch), `send_message` automatically strips reply parameters and sends directly to guarantee zero message loss.
  * **Command Reply Context Preservation**: Commands such as `/btw` and `/steer` preserve quoted context when invoked via message replies.
  * **Metadata Continuity in Task Queue**: Added `QueuedTask` string subclass ensuring queued items preserve originating `message_id` across FIFO queues and drain cycles.
- **Dual Verification Test Suite for Chat Reply (`TestChatReply`)**: Added 14 unit and integration tests (4 Positive + 10 Negative stress tests) in `tests/test_gemini_hermes.py`, bringing total project tests to 62 (100% pass rate).

## [1.5.1] - 2026-09-22

### Added
- **Automatic Chat Queueing ("Zero Message Drop")**: Upgraded Telegram gateway (`gemini_hermes/gateway/telegram_bot.py`) to automatically enqueue incoming user messages and attachments sent without slash commands during active execution, completely eliminating dropped messages.
- **Queue Capacity Guard (`max_queue_size = 10`)**: Protected execution memory with an explicit capacity limit that rejects excess messages gracefully with an alert if the queue fills up.
- **Dual Verification Test Suite for Auto Chat Queueing**: Added `TestAutoChatQueue` in `tests/test_gemini_hermes.py` covering:
  * `test_positive_auto_queue_single_chat`: Plain chat enqueued with position `#1` confirmation and executed upon task completion.
  * `test_positive_auto_queue_multiple_chats_sequential`: 3 consecutive chats queued in FIFO order and displayed in `/queue`.
  * `test_positive_queue_image_attachment`: Photo attachments queued and structured into vision inspection prompts.
  * `test_negative_queue_capacity_overflow`: Enforcing 10-item cap; excess items rejected gracefully with queue-full alert.
  * `test_negative_empty_or_whitespace_message_during_active_task`: Whitespace/empty messages rejected without queue pollution.
  * `test_negative_active_task_crash_resilience`: Engine crash/unhandled exception does not stall queue; next item executes cleanly.
  * `test_negative_cancel_aborts_active_and_purges_queue`: `/cancel` aborts ongoing task and purges all queued messages.
  * `test_negative_reset_aborts_active_and_purges_queue`: `/reset` aborts active task and clears task queues.
  * `test_negative_steer_preserves_queue_without_premature_trigger`: `/steer` mid-flight redirects without premature queue execution.

### Changed
- **Polished Queue Progress Display**: Enhanced `handle_queue` and `_run_queued_task` to format plain text messages and image/file attachments cleanly.

## [1.5.0] - 2026-09-21

### Added
- **Tiered Quality Memory Architecture (Hot vs. Warm Memory)**: Implemented structured memory tiering in `MemoryStore` (`gemini_hermes/memory/store.py`), separating fast in-prompt working context ("Hot Memory") from permanent on-disk archives ("Warm Memory" in `data/memory/archive/BACKLOG_ARCHIVE.md`).
- **Dynamic Hot Backlog Capping**: `get_hot_backlog(max_recent_completed=5)` guarantees that prompt context preserves 100% of active tasks `[ ]` while capping completed milestones `[x]` to the 5 most recent entries with an archival indicator, preventing unbounded token bloat and attention dilution.
- **Backlog Archiving & Migration Engine**: `archive_completed_backlog(keep_recent=5)` atomically migrates older resolved tasks and their multiline nested verification logs to `data/memory/archive/BACKLOG_ARCHIVE.md`.
- **Telegram `/compact` Command**: Added `/compact` command to Telegram gateway, allowing one-touch memory compaction, archiving, and real-time telemetry reporting on hot vs. archived token metrics.
- **Dual Verification Test Suite for Tiered Memory**: Added `TestTieredQualityMemory` in `tests/test_gemini_hermes.py` covering:
  * `test_positive_hot_backlog_filtering`: Verifies active task retention and completed task capping.
  * `test_positive_archive_completed_tasks_multiline`: Verifies multiline nested task preservation in warm archive.
  * `test_positive_memory_stats_metrics`: Verifies token and character metrics calculation.
  * `test_positive_compact_command_flow`: Verifies Telegram `/compact` command flow and response formatting.
  * `test_negative_no_op_when_under_threshold`: Verifies idempotent no-op when completed tasks are below threshold.
  * `test_negative_empty_or_malformed_backlog_graceful`: Verifies graceful handling of empty or unformatted markdown.

## [1.4.3] - 2026-09-21


### Added
- **/steer Command (Mid-Flight Course Correction & Immediate Intervention)**: Added `/steer <instruction>` allowing the user to immediately intervene and redirect the agent mid-flight during active tasks or provide high-priority guidance when idle.
- **Context-Preserving Steering Prompting**: Seamlessly halts the active subprocess/turn, captures previous task objective & current action, and synthesizes an authoritative `[USER STEERING DIRECTIVE]` resuming within the same conversation session without context loss.
- **Dual Verification Test Suite for /steer**: Added `TestSteerCommand` in `tests/test_gemini_hermes.py` covering:
  * `test_positive_midflight_steering_interception`: Verifies active task cancellation, steering notification, and structured directive handoff.
  * `test_positive_idle_steering`: Verifies direct steering execution when no task is running.
  * `test_negative_empty_directive_guidance`: Verifies graceful usage instructions when called with empty input.
  * `test_negative_steered_cancellation_suppresses_generic_cancel_and_queue_race`: Verifies that steered task cancellation suppresses generic cancellation messages, updates status message in-place (`⏸️ Superseded by /steer`), and prevents queued tasks from prematurely firing.

### Changed
- **Task Cancellation & Race Condition Hardening**: Hardened `handle_chat_message` `except asyncio.CancelledError` and `finally` blocks to distinguish between user `/cancel` vs `/steer` interventions, preventing task queue race conditions.
- **Enhanced Busy Notice**: Polished Telegram busy notification to explicitly highlight `/steer <new direction>` alongside `/btw` and `/cancel`.

## [1.4.2] - 2026-09-21

### Added
- **task_watcher Modular Procedure (v1.0.0)**: Builtin skill enforcing zero premature exits on long-running tasks (`npm run build`, background file transfers, compilers). Defines active process polling, log tracking, and scheduled engine wakeup alerts (`schedule`).
- **Dual Verification Test Suite for In-Place Status Updates**: Added automated unit tests `test_positive_in_place_status_flow` and `test_negative_fallback_when_edit_fails` in `tests/test_gemini_hermes.py` validating that tool transitions update a single message in-place and fall back gracefully if message editing is rejected.

### Changed
- **Telegram Status Message Aggregation (Zero Status Spam)**: Refactored `telegram_bot.py` turn execution to mutate and edit a single status message handle in-place (`🔨 *Currently:* <action>`) across intermediate tool executions, eliminating conversational clutter and bubble spam in Telegram.
- **Upgraded Skills Catalog**: Builtin skills catalog expanded to 9 active procedures.

## [1.4.1] - 2026-09-20

### Added
- **Absolute Factual Integrity ("NEVER LIE")**: Codified Cardinal Directive #8 across `HERMES_BASE_INSTRUCTIONS`, system prompt headers, prebuilt blueprints (`DEFAULT_USER_TEMPLATE`, `DEFAULT_MEMORY_TEMPLATE`), and `memory_keeper` procedure (v1.2.1), strictly prohibiting hallucination, fabrication, or claiming actions are saved/completed without verified physical tool execution.
- **Physical Memory Persistence Architecture**: Enforced physical file persistence on disk under `data/memory/` (`USER.md`, `MEMORY.md`, `BACKLOG.md`, `REFERENCES.md`) by injecting active storage directory path metadata and tool execution obligations directly into system prompt context.
- **Interactive Memory Management CLI Suite**: Added `./run.sh memory {show|add-user|add-task|add-memory|add-ref}` and `python3 -m gemini_hermes.cli memory ...` subcommands for terminal inspection and direct memory state manipulation.
- **Expanded Memory Test Suite**: Added 21 automated regression tests covering prompt storage path injection, truthfulness directive assertions, and memory CLI subcommands.

### Changed
- **Sanitized Open-Source Production Baseline**: Internationalized all directives to English and sanitized personal contexts from `data/memory/USER.md` and `data/memory/BACKLOG.md` for clean public distribution.

## [1.4.0] - 2026-09-19

### Added
- **Deliberate Development Cadence ("Slow is Smooth, Smooth is Fast")**: Codified core engineering standards in `USER.md` prioritizing incremental, bug-free delivery over rushed one-shot implementations that generate debugging debt.
- **Rigorous Dual Verification Standard**: Mandated both positive (happy path) and negative (boundary cases, invalid inputs, failure handling) verification for all features, skills, and code changes.
- **Sensible UI/UX Polish Autonomy**: Formalized authority to proactively introduce layout, visual hierarchy, styling, and ergonomic refinements without disturbing core business logic.
- **5-Phase Skill Creation Pipeline**: Formulated and codified the 5-phase skill creation pipeline (Phase 1: Goal & Boundary Definition, Phase 2: Procedure & Edge-Case Architecture, Phase 3: Incremental Draft & Review, Phase 4: Positive & Negative Stress Testing, Phase 5: Catalog Registration & Packaging) in `README.md` and `USER.md`.
- **Upgraded Skill Creator Procedure (v1.1.0)**: Updated `skill_creator` to v1.1.0 enforcing the 5-phase deliberate creation protocol across the agent skill registry.
- **Long-Term Memory Scaling Protocol**: Established memory preservation architecture covering semantic distillation, modular hot/warm/cold tiering, periodic pruning, and graduating recurrent patterns into reusable skills.
- **Enhanced Prebuilt Memory Blueprints**: Updated `DEFAULT_USER_TEMPLATE` and `DEFAULT_MEMORY_TEMPLATE` in `templates.py` to seed fresh installations with deliberate development standards, testing requirements, and memory lifecycle protocols out of the box.
- **Base Persona System Prompt Directives**: Added explicit Section 7 ("Deliberate Cadence & Rigorous Dual Verification") to `HERMES_BASE_INSTRUCTIONS`.
- **Upgraded Memory Keeper Procedure (v1.2.0)**: Extended `memory_keeper` with long-term memory scaling, semantic distillation, and tiered storage lifecycles.

### Changed
- **Skill Storage De-duplication**: Pruned redundant duplicate files from `data/skills/`, eliminating duplicate disk I/O and ensuring `data/skills/` cleanly serves as an isolated repository for newly created custom skills while built-in skills load directly from package resources.

## [1.3.9] - 2026-09-19

### Added
- **Automated Regression Test Suite**: Added a comprehensive unit test suite in `tests/test_gemini_hermes.py` covering Configuration, MemoryStore (all 4 storage domains), SkillManager, ProjectManager, System Prompt generation, StreamParser, and Gateway Formatter with 100% pass rate.
- **Thinking Delta Stream Parsing**: Enabled real-time cognitive thought parsing (`thinking_delta` and `thought`) in `stream_parser.py` for immediate scratchpad telemetry.
- **Enhanced CLI Diagnostics**: Extended `run_diagnostics()` in `gemini_hermes/cli.py` to audit and report byte counts for `BACKLOG.md` and `REFERENCES.md`.

### Changed
- **Stream Parser Code Hygiene**: Removed vestigial worker role arguments from `ToolExecutionUpdate` in `stream_parser.py` to strictly reflect direct solo execution standards.

## [1.3.8] - 2026-09-18

### Added
- **Singleton PID File Lock**: Added atomic PID locking in `gemini_hermes/cli.py` to prevent duplicate bot instances and ensure clean daemon lifecycle during background restarts.
- **Sanitized Public Distribution**: Maintained clean, generic starter templates for `data/memory/` and `data/projects/projects.json` on `main`, isolating personal tasks, sheets, and scratch projects to development branches.

### Merged
- **Modular Multi-Domain Memory Architecture**: Fully merged `MemoryStore` multi-domain persistence (`MEMORY.md`, `USER.md`, `BACKLOG.md`, `REFERENCES.md`) and `/task_add`, `/ref_add` gateway commands into `main`.

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
