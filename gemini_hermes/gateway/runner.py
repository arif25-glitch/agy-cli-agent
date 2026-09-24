"""
Execution runner managing the turn lifecycle, streaming, tool heartbeats, and queue progression.
"""
import asyncio
import logging
import time
from typing import Any, Optional, List

from gemini_hermes.config import config
from gemini_hermes.persona.system_prompt import build_system_prompt
from gemini_hermes.brain.stream_parser import TokenDelta, ForwarderResult, ToolExecutionUpdate
from gemini_hermes.gateway.formatter import (
    format_hermes_output,
    split_message,
    humanize_error,
    sanitize_streaming_markdown,
)

logger = logging.getLogger("gemini-hermes.telegram.runner")


class ExecutionRunner:
    """
    Executes a single conversational or tool-augmented turn for Gemini-Hermes.
    Coordinates typing heartbeat, tool-execution pulse, incremental streaming,
    in-place status message replacement, and automatic queue drainage.
    """

    @staticmethod
    async def execute_turn(
        bot: Any,
        chat_id: int,
        user_id: int,
        user_text: str,
        reply_to_message_id: Optional[int] = None,
    ):
        curr_task = asyncio.current_task()
        if curr_task:
            bot._active_tasks[chat_id] = curr_task

        bot._active_task_info[chat_id] = {
            "text": user_text,
            "start_time": time.time(),
            "last_action": "Thinking and planning...",
            "status_count": 0,
            "user_id": user_id,
        }

        sess = bot.memory_store.get_session(chat_id)
        conv_id = sess.get("conversation_id")

        # Determine reasoning effort & fast-path eligibility (dynamic via Jev if enabled, else default)
        selected_effort = config.reasoning_effort
        is_fast_path = False
        effort_label = ""
        if getattr(config, "jev_enabled", False) and getattr(config, "jev_dynamic_effort", False):
            jev_adapter = getattr(bot, "jev_adapter", None) or getattr(bot, "jev_service", None)
            if jev_adapter and getattr(jev_adapter, "is_available", False):
                try:
                    selected_effort, decision = await jev_adapter.select_reasoning_effort(
                        user_text,
                        default_effort=config.reasoning_effort,
                        timeout=getattr(config, "jev_timeout", 3.0),
                    )
                    if decision:
                        # Check fast-path eligibility: low effort, casual chat intent, no deep reasoning/tools
                        if (
                            getattr(config, "jev_fast_path", True)
                            and selected_effort == "low"
                            and getattr(decision, "intent", "") in ("casual_chat", "smalltalk", None)
                            and not getattr(decision, "needs_deep_reasoning", False)
                        ):
                            is_fast_path = True
                            effort_label = " (fast reflex)"
                            logger.info(
                                f"Jev fast-path conversational context selected for chat_id={chat_id} "
                                f"(latency={decision.latency_ms:.1f}ms)"
                            )
                        else:
                            effort_label = f" ({selected_effort} effort)"
                            logger.info(
                                f"Jev dynamic effort selected: '{selected_effort}' for chat_id={chat_id} "
                                f"(complexity={decision.complexity_score:.2f}, "
                                f"deep_reasoning={decision.needs_deep_reasoning}, latency={decision.latency_ms:.1f}ms)"
                            )
                except Exception as e:
                    logger.warning(f"Jev dynamic effort evaluation failed: {e}. Using default '{selected_effort}'")

        # Build prompt with Hermes cognitive persona (compact fast-path or full engineering context)
        system_prompt = build_system_prompt(
            bot.memory_store,
            bot.skill_manager,
            project_manager=bot.project_manager,
            current_chat_id=chat_id,
            fast_path=is_fast_path,
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"### User Message\n{user_text}\n\n"
            f"Respond adhering to your Gemini-Hermes persona."
        )

        await bot.send_chat_action(chat_id, "typing")

        stop_typing = asyncio.Event()
        is_typing_active = asyncio.Event()
        is_typing_active.set()  # Initially active while thinking

        tool_active_event = asyncio.Event()
        current_tool_name = [""]
        current_tool_start = [0.0]

        async def _typing_heartbeat():
            while not stop_typing.is_set():
                try:
                    if is_typing_active.is_set():
                        await bot.send_chat_action(chat_id, "typing")
                    await asyncio.wait_for(stop_typing.wait(), timeout=4.5)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    break

        # Single live status/response message handle for in-place editing (mutable container for heartbeat access)
        status_message_ref = [None]  # type: List[Optional[int]]
        has_tool_run = False

        async def _tool_heartbeat():
            while not stop_typing.is_set():
                try:
                    await asyncio.sleep(15.0)
                    if stop_typing.is_set():
                        break
                    if tool_active_event.is_set() and current_tool_start[0] > 0:
                        elapsed = int(time.time() - current_tool_start[0])
                        action = current_tool_name[0]
                        if elapsed >= 15:
                            pulse_msg = f"⏳ Still executing: `{action}` ({elapsed}s elapsed)..."
                            if status_message_ref[0]:
                                await bot.edit_message_text(chat_id, status_message_ref[0], pulse_msg, parse_mode="Markdown")
                            else:
                                sent_id = await bot.send_message(chat_id, pulse_msg, parse_mode="Markdown")
                                if sent_id:
                                    status_message_ref[0] = sent_id
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Tool heartbeat error: {e}")

        typing_task = asyncio.create_task(_typing_heartbeat())
        tool_heartbeat_task = asyncio.create_task(_tool_heartbeat())

        if config.stream_updates:
            status_text = f"💭 *Gemini-Hermes is thinking{effort_label}...*"
            status_message_ref[0] = await bot.send_message(
                chat_id,
                status_text,
                reply_to_message_id=reply_to_message_id,
            )

        accumulated_text = ""
        last_edit_time = time.time()
        last_status_time = 0.0
        last_status_action = ""
        last_active_action = ""
        final_result: Optional[ForwarderResult] = None

        try:
            try:
                stream_gen = bot.forwarder.forward_stream(full_prompt, conv_id, effort=selected_effort)
            except TypeError:
                stream_gen = bot.forwarder.forward_stream(full_prompt, conv_id)

            async for event in stream_gen:
                if isinstance(event, TokenDelta):
                    tool_active_event.clear()
                    current_tool_start[0] = 0.0
                    is_typing_active.set()
                    accumulated_text += event.text
                    now = time.time()
                    if (
                        status_message_ref[0]
                        and config.stream_updates
                        and (now - last_edit_time >= config.stream_edit_interval)
                        and len(accumulated_text.strip()) > 0
                    ):
                        last_edit_time = now
                        formatted_preview = format_hermes_output(accumulated_text)
                        preview = sanitize_streaming_markdown(formatted_preview) + " ▌"
                        if len(preview) <= 4000:
                            await bot.edit_message_text(chat_id, status_message_ref[0], preview)

                elif isinstance(event, ToolExecutionUpdate):
                    is_typing_active.clear()
                    tool_active_event.set()
                    has_tool_run = True
                    current_tool_name[0] = event.action
                    current_tool_start[0] = time.time()
                    last_active_action = event.action
                    if chat_id in bot._active_task_info:
                        bot._active_task_info[chat_id]["last_action"] = event.action
                        bot._active_task_info[chat_id]["status_count"] += 1
                    now = time.time()
                    interval = getattr(config, "status_notify_interval", 1.2)
                    if event.action != last_status_action and (now - last_status_time >= interval):
                        last_status_time = now
                        last_status_action = event.action

                        status_msg = f"🔨 *Currently:* `{event.action}`"
                        if status_message_ref[0]:
                            await bot.edit_message_text(chat_id, status_message_ref[0], status_msg, parse_mode="Markdown")
                        else:
                            sent_id = await bot.send_message(chat_id, status_msg, parse_mode="Markdown")
                            if sent_id:
                                status_message_ref[0] = sent_id

                elif isinstance(event, ForwarderResult):
                    is_typing_active.clear()
                    tool_active_event.clear()
                    current_tool_start[0] = 0.0
                    final_result = event

            # Generation finished
            final_text = (
                final_result.response
                if (final_result and final_result.response.strip())
                else accumulated_text
            )

            new_conv_id = (final_result and final_result.conversation_id) or conv_id

            if final_result and final_result.status in ("ERROR", "TIMEOUT") and final_result.error:
                final_text = humanize_error(final_result.error, last_action=last_active_action)
            elif not final_text.strip():
                if final_result and final_result.error:
                    final_text = humanize_error(final_result.error, last_action=last_active_action)
                else:
                    final_text = humanize_error("Empty response received from engine.", last_action=last_active_action)

            # Update session stats
            in_tok = final_result.input_tokens if final_result else 0
            out_tok = final_result.output_tokens if final_result else 0
            bot.memory_store.update_session(
                chat_id,
                conversation_id=new_conv_id,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )

            # Format hermes output
            formatted_text = format_hermes_output(final_text)
            chunks = split_message(formatted_text)

            if status_message_ref[0]:
                # Clean in-place transition: replace status message with the final response
                edited_ok = await bot.edit_message_text(chat_id, status_message_ref[0], chunks[0])
                if not edited_ok:
                    # If edit failed (e.g. deleted by user or parse error), fallback to send_message
                    await bot.send_message(chat_id, chunks[0], reply_to_message_id=reply_to_message_id)
                for chunk in chunks[1:]:
                    await bot.send_message(chat_id, chunk)
            else:
                if chunks:
                    await bot.send_message(chat_id, chunks[0], reply_to_message_id=reply_to_message_id)
                    for chunk in chunks[1:]:
                        await bot.send_message(chat_id, chunk)

        except asyncio.CancelledError:
            logger.info(f"Task for chat_id={chat_id} was cancelled.")
            info = bot._active_task_info.get(chat_id, {})
            was_steered = info.get("steered", False)
            if was_steered:
                steer_halt_note = f"⏸️ *Superseded by `/steer`:* `{last_active_action or 'Previous operation'}` halted."
                if status_message_ref[0]:
                    await bot.edit_message_text(chat_id, status_message_ref[0], steer_halt_note)
            else:
                cancel_msg = "🛑 *Operation Cancelled.*\nThe ongoing request was stopped."
                if status_message_ref[0]:
                    await bot.edit_message_text(chat_id, status_message_ref[0], cancel_msg)
                else:
                    await bot.send_message(chat_id, cancel_msg, reply_to_message_id=reply_to_message_id)
            raise
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            err_text = humanize_error(str(e), last_action=last_active_action)
            if status_message_ref[0]:
                await bot.edit_message_text(chat_id, status_message_ref[0], err_text)
            else:
                await bot.send_message(chat_id, err_text, reply_to_message_id=reply_to_message_id)
        finally:
            stop_typing.set()
            if not typing_task.done():
                typing_task.cancel()
            if not tool_heartbeat_task.done():
                tool_heartbeat_task.cancel()

            info = bot._active_task_info.get(chat_id, {})
            was_steered = info.get("steered", False)

            if bot._active_tasks.get(chat_id) is curr_task:
                bot._active_tasks.pop(chat_id, None)
            if not was_steered:
                bot._active_task_info.pop(chat_id, None)

            # Check if there is a queued /btw task (only if not steered)
            if not was_steered and chat_id in bot._task_queues and bot._task_queues[chat_id]:
                next_task_text = bot._task_queues[chat_id].pop(0)
                next_reply_id = getattr(next_task_text, "message_id", None)
                logger.info(
                    f"Triggering next queued task for chat_id={chat_id}: {next_task_text[:50]} (reply_to={next_reply_id})"
                )
                if next_reply_id is not None:
                    asyncio.create_task(
                        bot._run_queued_task(chat_id, user_id, next_task_text, reply_to_message_id=next_reply_id)
                    )
                else:
                    asyncio.create_task(bot._run_queued_task(chat_id, user_id, next_task_text))
