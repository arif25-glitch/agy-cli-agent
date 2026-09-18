# Changelog

All notable changes to the Gemini-Hermes AI Agent project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
