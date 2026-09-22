# Active Task Backlog & Operational Notes

## Active Tasks

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
