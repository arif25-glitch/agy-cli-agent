# Active Task Backlog & Operational Notes

## Active Tasks

- [x] Dual Verification completed for Modular Gateway Architecture Refactoring:
  * Phase 1 (Goal & Boundary): Deconstruct monolithic `telegram_bot.py` (>1,400 LOC) into clean, React/modern-style layers (services, helpers, handlers, models, execution runner) while preserving 100% backward compatibility for all existing tests and CLI scripts.
  * Phase 2 (Architecture & Decomposition):
    - Services (`services/telegram_client.py`): HTTP transport, API endpoints, message CRUD, file downloads.
    - Helpers (`helpers/reply_parser.py`, `helpers/intent_classifier.py`): Inbound reply context extraction & intent classification.
    - Handlers (`handlers/`): Command & lifecycle handlers (`system_handlers`, `memory_handlers`, `skill_handlers`, `project_handlers`, `queue_handlers`, `steering_handlers`).
    - Models (`models.py`): `QueuedTask` metadata model.
    - Runner (`runner.py`): `ExecutionRunner` encapsulating turn lifecycle, typing heartbeat, tool heartbeat, streaming updates, and queue progression.
    - Gateway Facade (`telegram_bot.py`): Subclasses `TelegramClient` and coordinates handlers while maintaining exact attribute & method parity.
  * Phase 3 (Incremental Draft): Implemented modular package hierarchy with clean imports and re-exports.
  * Phase 4 (Dual Verification - 70 Passed Tests):
    - Full regression run of existing 62 tests in `test_gemini_hermes.py` (100% passed).
    - Added 8 dedicated unit tests in `test_modular_gateway.py` covering positive & negative paths for `QueuedTask`, `classify_btw_intent`, `extract_reply_context` (text, media, malformed payloads), and `TelegramClient` API transport.
    - Verified live diagnostics via `gemini_hermes.cli test` against Telegram API and Antigravity forwarder.
  * Phase 5 (Packaging & Memory Update): Synced physical memory and ready for Jev AI decision engine integration.

- [x] Dual Verification completed for Telegram Targeted Quoting & Contextual Reply Awareness:
  * Phase 1 (Goal & Boundary): Support bi-directional Telegram message replying: outbound reply targeting (`reply_to_message_id`, `reply_parameters`) and inbound reply context extraction (`reply_to_message`).
  * Phase 2 (Architecture & Resilience): Dual Telegram API fallback (strips formatting, then reply params if message was deleted/rejected); comprehensive media extraction (photo, document, voice, audio, video, sticker, poll, location, contact); command context preservation (`/btw`, `/steer`); and queued task metadata continuity via `QueuedTask`.
  * Phase 3 (Incremental Draft): Implemented in `gemini_hermes/gateway/telegram_bot.py` with non-dict payload protection, whitespace sanitization, and 300-char truncation.
  * Phase 4 (Dual Verification - 4 Positive + 10 Negative Tests in `TestChatReply`):
    - Positive 1 (`test_positive_direct_message_reply_payload`): Outbound message attaches reply parameters with `allow_sending_without_reply=True`.
    - Positive 2 (`test_positive_queued_tasks_retain_message_id_and_reply`): Queued tasks retain originating message_id and quote original user message on drain.
    - Positive 3 (`test_positive_inbound_reply_to_message_context_injection`): Quoting a text message injects sender name and quoted text into prompt.
    - Positive 4 (`test_positive_inbound_reply_to_media_context`): Quoting photo or document injects media summary into prompt.
    - Negative 1 (`test_negative_deleted_message_resilience_and_markdown_fallback`): Graceful fallback payload retains reply_to_message_id and allow_sending_without_reply.
    - Negative 2 (`test_negative_plain_string_queue_items_fallback_cleanly`): Legacy plain string queue items execute cleanly with `None` reply ID.
    - Negative 3 (`test_negative_secondary_fallback_without_reply_when_telegram_rejects_reply_parameters`): If Telegram API rejects reply targeting on both attempts, automatically falls back to direct delivery without reply parameters (zero message drop).
    - Negative 4 (`test_negative_malformed_non_dict_reply_to_message_resilience`): Non-dict `reply_to_message` payloads (int, str, None) handled without exceptions.
    - Negative 5 (`test_negative_empty_or_whitespace_reply_text_sanitization`): Whitespace-only reply text sanitized; prevents empty quote artifacts (`""`).
    - Negative 6 (`test_negative_inbound_reply_to_diverse_media_types`): Inbound replies to voice, audio, video, sticker (with/without emoji), poll, location, and contact inject descriptive context.
    - Negative 7 (`test_negative_inbound_reply_from_anonymous_channel_sender`): Quoting channel posts uses `sender_chat.title` or `User` fallback.
    - Negative 8 (`test_negative_command_with_reply_context_preservation`): `/btw` and `/steer` commands preserve reply context when executed as replies.
    - Negative 9 (`test_negative_queued_image_with_reply_context_notice`): Queued images with prepended reply context properly emit image processing notices.
    - Negative 10 (`test_negative_reply_text_long_truncation`): Inbound quoted messages exceeding 300 characters are cleanly truncated with `...`.
  * Phase 5 (Documentation & Release): Committed to `develop/chat-reply`.

- [x] Dual Verification completed for Automatic Chat Queueing ("Zero Message Drop"):
  * Phase 1 (Goal & Boundary): Auto-enqueue incoming plain messages and attachments sent without slash commands during active execution instead of dropping them.
  * Phase 2 (Architecture & Capacity): Designed `_enqueue_task` with `max_queue_size = 10` capacity guard, real-time position notification, and safe sequential queue drain.
  * Phase 3 (Incremental Draft): Upgraded `gemini_hermes/gateway/telegram_bot.py` message routing, media handling, `_run_queued_task`, and `handle_queue`.
  * Phase 4 (Dual Verification - 3 Positive + 6 Negative Tests):
    - Positive 1 (`test_positive_auto_queue_single_chat`): Plain chat enqueued with position `#1` confirmation and executed upon task completion.
    - Positive 2 (`test_positive_auto_queue_multiple_chats_sequential`): 3 consecutive chats queued in FIFO order and displayed in `/queue`.
    - Positive 3 (`test_positive_queue_image_attachment`): Photo attachments queued and structured into vision inspection prompts.
    - Negative 1 (`test_negative_queue_capacity_overflow`): Enforcing 10-item cap; excess items rejected gracefully with queue-full alert.
    - Negative 2 (`test_negative_empty_or_whitespace_message_during_active_task`): Whitespace/empty messages rejected without queue pollution.
    - Negative 3 (`test_negative_active_task_crash_resilience`): Engine crash/unhandled exception does not stall queue; next item executes cleanly.
    - Negative 4 (`test_negative_cancel_aborts_active_and_purges_queue`): `/cancel` aborts ongoing task and purges all queued messages.
    - Negative 5 (`test_negative_reset_aborts_active_and_purges_queue`): `/reset` aborts active task and clears task queues.
    - Negative 6 (`test_negative_steer_preserves_queue_without_premature_trigger`): `/steer` mid-flight redirects without premature queue execution.
  * Phase 5 (Documentation & Release): Updated CHANGELOG.md (v1.5.0), README.md, and physical memory.
- [x] Dual Verification completed for `task_watcher`: Negative path (intercepted TypeScript compilation break TS2322/TS2339/TS2304) and Positive path (clean build + prerendered `/dashboard` route with 100% artifact verification).
- [x] Dual Verification completed for `Zero Status Spam` (In-Place Message Editing):
  * Positive path (`test_positive_in_place_status_flow`): Verified single message handle is updated dynamically across multiple tool steps with zero new bubble emissions.
  * Negative path (`test_negative_fallback_when_edit_fails`): Verified graceful fallback to `send_message` if `editMessageText` fails (e.g. message deleted or API error), preventing lost responses.
- [x] Dual Verification completed for `Dual-Mode /btw` (Ephemeral Side Q&A + Chained Task Queue):
  * Intent Classification (`test_classify_btw_intent`): Verified natural heuristics and explicit prefix overrides (`?`, `q:`, `task:`, `queue:`).
  * Positive Path 1 (`test_positive_live_telemetry_inquiry`): Verified live telemetry synthesis during active background tasks with zero interruption.
  * Positive Path 2 (`test_positive_ephemeral_side_question`): Verified parallel one-shot query execution (`ask_quick` with `--effort low`) answering general/absurd questions with zero transcript pollution.
  * Positive Path 3 (`test_positive_task_queueing`): Verified follow-up directives are queued in `_task_queues` with position acknowledgement.
  * Negative Path 1 (`test_negative_ephemeral_query_failure_fallback`): Verified graceful error handling and user notification when proxy engine times out/fails.
  * Negative Path 2 (`test_negative_empty_query_help`): Verified clean usage guide dispatch for empty queries.
- [x] Implemented and verified `/steer` command:
  * Phase 1 (Goal & Boundary Definition): Real-time mid-flight task interception and immediate redirection.
  * Phase 2 (Architecture & Edge Cases): Active task cancellation, context-preserving prompt structure, in-place superseded notice, and race-free queue protection.
  * Phase 3 (Incremental Draft): Implemented `handle_steer` in `telegram_bot.py`, updated cancellation handlers, and registered command dispatch.
  * Phase 4 (Dual Verification): Verified via 4 automated test cases in `TestSteerCommand`:
    - Positive Path 1 (`test_positive_midflight_steering_interception`): Active task cancelled, directive handoff structured with previous context.
    - Positive Path 2 (`test_positive_idle_steering`): Idle directive executed directly with top priority.
    - Negative Path 1 (`test_negative_empty_directive_guidance`): Clean usage manual dispatched on empty input.
    - Negative Path 2 (`test_negative_steered_cancellation_suppresses_generic_cancel_and_queue_race`): Generic cancel message suppressed, status updated in-place (`⏸️ Superseded by /steer`), and queued tasks preserved without premature execution.
  * Phase 5 (Documentation & Packaging): Updated `/help`, `README.md`, `CHANGELOG.md` (v1.4.3), and physical memory.

## Operational Notes & Inquiries
- (Operational questions or blockers will be listed here)
