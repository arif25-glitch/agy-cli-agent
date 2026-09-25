# Active Task Backlog & Operational Notes

- [x] Dynamic / Relative Growth Rotation (Fixes the Rotation Loop):
  * [x] Relative token growth tracking: `SessionStore` tracks `session_baseline_tokens` on Turn 1 and `last_turn_input_tokens`, calculating relative context delta rather than fixed static ceilings.
  * [x] Minimum turn guardrail (`min_turns = 2`): Guarantees new sessions never rotate on single initial turns even when base prompts are large, breaking the single-turn rotation loop.
  * [x] Relative growth thresholding & expansion ratio: Rotates when context expands by `+40,000` tokens beyond baseline or hits turn limits (`15`), with hard safety ceiling (`120,000` tokens) against window overflow.
  * [x] Runner execution & config: Exposed in `Config` and wired through `ExecutionRunner` with smooth session rotation and Context Bridge handover.

- [x] Autonomous Memory Pruning & Archiving across 2 Worlds (Keeps Base Context Lean):
  * [x] 2-World Architecture (Pure Core vs Jev AI): World 1 (Pure Core) provides 100% deterministic, zero-dependency pruning for completed backlog tasks (`BACKLOG_ARCHIVE.md`) and stale memory notes (`MEMORY_ARCHIVE.md`); World 2 (Jev AI Accelerator) adds `JevMemoryPruner` with semantic `Choice` classification (transient vs evergreen) and automatic graceful fallback.
  * [x] Memory Notes Pruning: Added `MemoryNotesArchiver` in `gemini_hermes/memory/archiver.py` to preserve core directives intact while archiving stale debug facts/notes.
  * [x] Autonomous post-turn lifecycle hook: Integrated into `ExecutionRunner` to automatically prune and tier memory upon turn completion without blocking user messages.
  * [x] Upgraded `/compact` Telegram handler: Supports both manual inspection and autonomous pruning with rich breakdown of archived tasks, stale notes, and token footprint.
  * [x] Dual verification test suites: Positive and negative tests in `tests/test_relative_growth_rotation.py` and `tests/test_autonomous_memory_pruning.py`.

- [x] Token Efficiency & Context Optimization (Differential Prompting, JIT Skills, and Context Checkpointing):
  * [x] Differential Follow-Up Prompts: Turn 0 / initial session initializes full base persona & memory; Turn > 0 passes compact differential continuity note, dropping redundant in-prompt base text and static skill catalogs (>85% prompt token reduction per turn).
  * [x] Cache Prefix Stabilization: Structured prompts with immutable base instructions at index 0 and dynamic turn/session metadata at the bottom, maximizing Gemini KV context cache hits.
  * [x] Jev Just-In-Time (JIT) Skill Activation: Encapsulated `JevSkillSelector` with Jev `Choice` primitive in `gemini_hermes/jev/skill_selector.py` to evaluate incoming tasks and inject only relevant procedures (or 0 skills for standard coding/chat).
  * [x] Autonomous Context Checkpointing & Session Rotation: Added `should_rotate_session`, `rotate_session_with_bridge`, and `pop_context_bridge` in `SessionStore` to automatically reset conversation IDs at token/turn ceilings (`50,000` tokens / `15` turns) while seeding fresh sessions with a compact Context Bridge summary.
  * [x] Dual verification test suite: 9 positive and negative test cases in `tests/test_token_efficiency.py` covering differential prompt generation, cache prefix ordering, JIT skill filtering, timeout fallbacks, session rotation boundaries, and context bridge handover.

- [x] Dynamic Model Selection via Jev AI System-One:
  * [x] Model tier architecture: Mapped workloads to cost-efficient Antigravity models (gemini-3.6-flash for simple/cheap with low effort, gemini-3.7-flash for balanced with medium effort, gemini-3.8-flash for higher workloads / architecture with high effort, gemini-3.1-pro for deep algorithmic reasoning).
  * [x] Jev decision engine integration: Evaluates prompt before model dispatch via Jev System-One (`model_tier` Choice & calibrated complexity thresholds) to dynamically pick model and reasoning effort.
  * [x] Forwarder & Runner execution: Passes `--model` to `agy` CLI in `AgyForwarder` and wired through `ExecutionRunner` with live Telegram status tagging (`[gemini-3.8-flash] (high effort)`).
  * [x] Telegram `/model` command & telemetry: Allows inspecting/switching active model (with aliases `3.6`, `3.7`, `3.8`, `pro`), recorded in `TelemetryExporter`, and displayed live in `./run.sh monitor`.
  * [x] Dual verification test suite: Positive and negative tests covering model routing, timeout fallback, error handling, alias switching, and runner integration (`tests/test_dynamic_model.py`).

- [x] TypeSafe AI (Jev) System-One integration touchpoints:
  * [x] Modular Jev Package Architecture: Encapsulated all Jev capabilities into `gemini_hermes/jev/` (`client.py`, `effort_selector.py`, `btw_classifier.py`, `adapter.py`) preserving strict 2-world isolation between `./run.sh start` and `./run.sh start-jev`.
  * [x] Inbound Telegram reflex pre-filtering: Tested and verified live with Jev AI (`scripts/test_jev_reflex_prefilter.py` & `tests/test_jev_reflex_prefilter.py`). Achieved 100% accuracy across 6 test categories with ~661ms reflex latency.
  * [x] Dynamic reasoning effort selection (`--effort low/medium/high`): Implemented and verified with dual testing (`tests/test_dynamic_effort.py`). Activated exclusively via opt-in `./run.sh start-jev` or `./run.sh background-jev` with zero regressions to standard `./run.sh start`.
  * [x] Fast-Path Conversational Context: Implemented and verified with dual testing (`tests/test_fast_path_context.py`). Automatically slims prompt from ~12k to ~800 tokens for casual chat, keeping user identity (`USER.md`) and setting `--effort low` with 0 thinking tokens.
  * [x] Upgraded `/btw` Sidecar Intent Classification: Integrated Jev `Choice` primitive via `gemini_hermes/jev/btw_classifier.py` and `classify_btw_intent_smart`. Verified with dual test suite (`tests/test_jev_btw_classifier.py`) covering happy paths, low confidence fallback (<0.85), timeout (>1.0s), and deterministic 0ms prefix overrides (`?`, `task:`).

- [x] Session Token Reset & Lifetime Tracking on `/new` and `/reset`:
  * [x] Distinguish session vs lifetime metrics: `SessionStore` now tracks `session_input_tokens` and `session_output_tokens` separately from `total_input_tokens`, `total_output_tokens`, and `lifetime_turns`.
  * [x] Reset command synchronization: Calling `/new` or `/reset` clears session conversation tokens (`0 in / 0 out`, `0 turns`) while preserving historical lifetime token aggregations across all sessions.
  * [x] Instant Telemetry broadcasting: `handle_reset` immediately emits idle telemetry with 0 session tokens to ensure `./run.sh monitor` refreshes immediately.
  * [x] Dual verification test suite: Unit tests in `tests/test_cli_monitor.py` and `tests/test_gemini_hermes.py` validating positive reset behavior, token isolation, and lifetime persistence.

- [x] Total Token Usage & Session Usage in CLI Monitor (`./run.sh monitor`):
  * [x] Session & aggregate token calculations: Implemented `get_total_token_usage()` and `get_session_token_usage()` in `SessionStore` and `MemoryStore` to compute input, output, total tokens, and turn counts per session and across all sessions.
  * [x] Telemetry exporter integration: Updated `TelemetryExporter` and `ExecutionRunner` to capture live session and global token metrics in `telemetry.json` on turn initialization and completion.
  * [x] Dedicated UI panel in CLI Monitor: Added `build_token_usage_panel` in `gemini_hermes/cli_monitor.py` displaying Active Session (Chat ID, Input/Output, Total Tokens, Turn Count) and Lifetime Global Usage (Tracked Sessions, Global Input/Output, Lifetime Total Tokens) with clean human-readable thousands/millions formatting (`1.5k`, `216.29M`).
  * [x] Dual verification test suite: Added positive and negative test cases in `tests/test_cli_monitor.py` covering token formatting, empty/populated session aggregations, offline fallback, and dashboard layout rendering.

- [x] Interactive Terminal UI Dashboard (`./run.sh monitor`):
  * Implemented real-time dashboard (`gemini_hermes/cli_monitor.py`) with rich layout panels.
  * Real-time telemetry exporter (`gemini_hermes/telemetry.py`) tracking active turns, chat ID, reasoning effort, queue depth, and Jev reflex metrics with zero locking.
  * Added `./run.sh monitor` command and integrated into CLI subcommands.
  * Verified with dual testing (`tests/test_cli_monitor.py`) covering active daemon and offline daemon handling.

- *(Historical completed milestones archived in `data/memory/archive/BACKLOG_ARCHIVE.md`)*

## Operational Notes & Inquiries
- Production Release `v1.7.3` updated: Dynamic Relative Growth Rotation (Fixed Rotation Loop) & Autonomous Memory Pruning across 2 Worlds deployed.
- Strict 2-world boundary maintained:
  * Standard `./run.sh start`: 100% pure engine execution, differential prompts, pure core deterministic backlog & note pruning (`BACKLOG_ARCHIVE.md`, `MEMORY_ARCHIVE.md`), static configured model (`config.agy_model`), pure regex/keyword heuristics for `/btw`, zero external SDK or network calls.
  * Accelerated `./run.sh start-jev` / `./run.sh background-jev`: Dynamic model routing (3.6-flash, 3.7-flash, 3.8-flash, 3.1-pro), dynamic reasoning effort (`low`, `medium`, `high`), JIT skill auto-selection, and Jev smart semantic memory pruning (`transient` vs `evergreen`) with automatic graceful fallback.
- Interactive Monitor: Run `./run.sh monitor` anytime in a terminal window for live visual telemetry including active model, active task queue, and total session/lifetime token usage.
- Test Suite: All 150 tests passing cleanly (`Ran 150 tests in 12.063s, OK`).

