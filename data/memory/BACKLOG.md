# Active Task Backlog & Operational Notes

## Active Tasks

- [x] TypeSafe AI (Jev) System-One integration touchpoints:
  * [x] Modular Jev Package Architecture: Encapsulated all Jev capabilities into `gemini_hermes/jev/` (`client.py`, `effort_selector.py`, `btw_classifier.py`, `adapter.py`) preserving strict 2-world isolation between `./run.sh start` and `./run.sh start-jev`.
  * [x] Inbound Telegram reflex pre-filtering: Tested and verified live with Jev AI (`scripts/test_jev_reflex_prefilter.py` & `tests/test_jev_reflex_prefilter.py`). Achieved 100% accuracy across 6 test categories with ~661ms reflex latency.
  * [x] Dynamic reasoning effort selection (`--effort low/medium/high`): Implemented and verified with dual testing (`tests/test_dynamic_effort.py`). Activated exclusively via opt-in `./run.sh start-jev` or `./run.sh background-jev` with zero regressions to standard `./run.sh start`.
  * [x] Fast-Path Conversational Context: Implemented and verified with dual testing (`tests/test_fast_path_context.py`). Automatically slims prompt from ~12k to ~800 tokens for casual chat, keeping user identity (`USER.md`) and setting `--effort low` with 0 thinking tokens.
  * [x] Upgraded `/btw` Sidecar Intent Classification: Integrated Jev `Choice` primitive via `gemini_hermes/jev/btw_classifier.py` and `classify_btw_intent_smart`. Verified with dual test suite (`tests/test_jev_btw_classifier.py`) covering happy paths, low confidence fallback (<0.85), timeout (>1.0s), and deterministic 0ms prefix overrides (`?`, `task:`).

- *(Historical completed milestones archived in `data/memory/archive/BACKLOG_ARCHIVE.md`)*

## Operational Notes & Inquiries
- Production Release `v1.6.0` updated: All Jev AI features live in self-contained `gemini_hermes/jev/` module.
- Strict 2-world boundary maintained:
  * Standard `./run.sh start`: 100% pure engine execution, pure regex/keyword heuristics for `/btw`, zero external SDK or network calls.
  * Accelerated `./run.sh start-jev` / `./run.sh background-jev`: Dynamic reasoning effort, fast-path context slimming, and smart `/btw` classification with graceful fallback.
- Test Suite: All 107 tests passing cleanly (`Ran 107 tests in 11.826s, OK`).

