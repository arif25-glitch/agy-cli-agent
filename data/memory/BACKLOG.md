# Active Task Backlog & Operational Notes

## Active Tasks

- [ ] Await user & community alignment on TypeSafe AI (Jev) System-One integration touchpoints:
  * Decide whether to hook Jev into `/btw` sidecar intent classification (`helpers/intent_classifier.py`).
  * Decide whether to hook Jev into dynamic reasoning effort selection (`--effort low/medium/high`).
  * Decide whether to hook Jev into inbound Telegram reflex pre-filtering.

- *(Historical completed milestones archived in `data/memory/archive/BACKLOG_ARCHIVE.md`)*

## Operational Notes & Inquiries
- Production Release `v1.6.0` is deployed with TypeSafe AI (Jev) System-One shell ready and 100% decoupled.
- Core bot features (chat replying, auto-queueing, `/steer`, `/btw`, tiered memory) are verified and running independently.
- Jev is disabled by default (`JEV_ENABLED=false`) until users configure keys via `./run.sh config` and choose integration points.
