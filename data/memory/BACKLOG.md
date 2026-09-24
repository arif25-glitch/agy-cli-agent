# Active Task Backlog & Operational Notes

## Active Tasks

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

- [x] Interactive Terminal UI Dashboard (`./run.sh monitor`):
  * Implemented real-time dashboard (`gemini_hermes/cli_monitor.py`) with rich layout panels.
  * Real-time telemetry exporter (`gemini_hermes/telemetry.py`) tracking active turns, chat ID, reasoning effort, queue depth, and Jev reflex metrics with zero locking.
  * Added `./run.sh monitor` command and integrated into CLI subcommands.
  * Verified with dual testing (`tests/test_cli_monitor.py`) covering active daemon and offline daemon handling.

- *(Historical completed milestones archived in `data/memory/archive/BACKLOG_ARCHIVE.md`)*

## Operational Notes & Inquiries
- Production Release `v1.7.0` updated: Dynamic Model Selection enabled alongside Dynamic Reasoning Effort and Fast-Path context.
- Strict 2-world boundary maintained:
  * Standard `./run.sh start`: 100% pure engine execution, static configured model (`config.agy_model`), pure regex/keyword heuristics for `/btw`, zero external SDK or network calls.
  * Accelerated `./run.sh start-jev` / `./run.sh background-jev`: Dynamic model routing (3.6-flash, 3.7-flash, 3.8-flash, 3.1-pro) and dynamic reasoning effort (`low`, `medium`, `high`) with automatic graceful fallback.
- Interactive Monitor: Run `./run.sh monitor` anytime in a terminal window for live visual telemetry including active model.
- Test Suite: All 123 tests passing cleanly (`Ran 123 tests in 9.473s, OK`).

