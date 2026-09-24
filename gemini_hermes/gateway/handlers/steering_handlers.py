"""
Sidecar (/btw) and course-correction (/steer) handlers.
"""
import asyncio
import logging
import time
from typing import Any, Optional

from gemini_hermes.gateway.models import QueuedTask
from gemini_hermes.gateway.formatter import format_hermes_output

logger = logging.getLogger("gemini-hermes.telegram.steering")


async def handle_btw_ephemeral_question(
    bot: Any,
    chat_id: int,
    query: str,
    task_preview: Optional[str] = None,
    last_action: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
):
    """
    Executes an ephemeral, side-channel question in parallel without interrupting
    or polluting the primary background task's context window.
    """
    try:
        placeholder_text = f"💬 *Side Question (/btw):*\n_{query}_\n\n⏳ _Consulting proxy engine..._"
        msg_id = await bot.send_message(chat_id, placeholder_text, reply_to_message_id=reply_to_message_id)

        task_clause = ""
        if task_preview:
            task_clause = (
                f"\nBackground Context: The user is currently running an active operation: '{task_preview}'. "
                f"Current operation step is '{last_action or 'executing'}'. "
                f"If the question inquires about this operation, incorporate this context.\n"
            )

        prompt = (
            f"You are Gemini-Hermes, answering an ephemeral side query (/btw) on Telegram.{task_clause}\n"
            f"User Question: {query}\n\n"
            f"Instructions:\n"
            f"- Answer concisely, directly, and accurately.\n"
            f"- If it's a general knowledge, absurd, or technical question, answer helpfully and engagingly.\n"
            f"- Do NOT attempt to run tools or commands.\n"
            f"- Keep formatting clean and readable for mobile Telegram."
        )

        raw_answer = await bot.forwarder.ask_quick(prompt, timeout=35.0)

        if not raw_answer or not raw_answer.strip():
            final_text = (
                f"💬 *Side Answer (/btw):*\n_{query}_\n\n"
                f"⚠️ _Unable to retrieve side answer at this moment (engine timeout or busy)._\n\n"
                f"_The primary task continues running unaffected._"
            )
        else:
            formatted_body = format_hermes_output(raw_answer.strip())
            status_footer = (
                f"\n\n_Primary task continues running in background._"
                if task_preview
                else ""
            )
            final_text = f"💬 *Side Answer (/btw):*\n_{query}_\n\n{formatted_body}{status_footer}"

        if msg_id:
            edited = await bot.edit_message_text(chat_id, msg_id, final_text)
            if not edited:
                await bot.send_message(chat_id, final_text)
        else:
            await bot.send_message(chat_id, final_text)

    except Exception as e:
        logger.error(f"Error handling ephemeral /btw question: {e}", exc_info=True)
        fallback = (
            f"💬 *Side Answer (/btw):*\n"
            f"⚠️ _An error occurred while answering your side question._\n\n"
            f"_The primary task continues running unaffected._"
        )
        await bot.send_message(chat_id, fallback)


async def handle_btw(bot: Any, chat_id: int, user_id: int, text: str, message_id: Optional[int] = None):
    query = text.strip()
    if not query:
        await bot.send_message(
            chat_id,
            "ℹ️ *Usage of `/btw`:*\n\n"
            "• *Side questions & trivia:* `/btw why is the sky blue?` or `/btw ? what is TCP?`\n"
            "• *Live status check:* `/btw what are you doing now?`\n"
            "• *Queue next task:* `/btw after this, write tests` or `/btw task: deploy app`\n\n"
            "_Side questions run in parallel without interrupting or polluting active tasks._",
            reply_to_message_id=message_id,
        )
        return

    if hasattr(bot, "_classify_btw_intent_async"):
        intent, clean_query = await bot._classify_btw_intent_async(query)
    else:
        intent, clean_query = bot._classify_btw_intent(query)
    is_running = chat_id in bot._active_tasks and not bot._active_tasks[chat_id].done()

    if not is_running:
        if intent == "live_status":
            await bot.send_message(
                chat_id,
                "ℹ️ *Status:* No background task is currently running. I am idle and ready for requests!",
                reply_to_message_id=message_id,
            )
            return
        elif intent == "question":
            # Execute as an ephemeral side question
            asyncio.create_task(
                bot._handle_btw_ephemeral_question(chat_id, clean_query, reply_to_message_id=message_id)
            )
            return
        else:
            # Task intent: execute directly as a chat message
            await bot.send_message(
                chat_id,
                f"💡 *Executing `/btw` task directly:* `{clean_query}`",
                reply_to_message_id=message_id,
            )
            task = asyncio.create_task(
                bot.handle_chat_message(chat_id, user_id, clean_query, reply_to_message_id=message_id)
            )
            bot._active_tasks[chat_id] = task
            return

    # An active task is currently running in background
    info = bot._active_task_info.get(chat_id, {})
    last_action = info.get("last_action", "Executing operation...")
    start_time = info.get("start_time", time.time())
    elapsed = int(time.time() - start_time)
    task_prompt = info.get("text", "")
    task_preview = task_prompt.splitlines()[0] if task_prompt else "Ongoing operation"
    if len(task_preview) > 75:
        task_preview = task_preview[:72] + "..."

    if intent == "live_status":
        status_text = (
            f"💬 *Side Query (Live Task Telemetry):*\n\n"
            f"• *Primary Task:* `{task_preview}`\n"
            f"• *Current Step:* {last_action}\n"
            f"• *Elapsed Time:* `{elapsed}s`\n"
            f"• *Status:* ⚙️ Actively executing in background\n\n"
            f"_The primary task continues uninterrupted._"
        )
        await bot.send_message(chat_id, status_text, reply_to_message_id=message_id)
        return

    elif intent == "question":
        # Ephemeral side question executed concurrently in background
        asyncio.create_task(
            bot._handle_btw_ephemeral_question(
                chat_id,
                clean_query,
                task_preview=task_preview,
                last_action=last_action,
                reply_to_message_id=message_id,
            )
        )
        return

    else:
        # Steering directive or Queued Task
        if chat_id not in bot._task_queues:
            bot._task_queues[chat_id] = []
        max_q = getattr(bot, "max_queue_size", 10)
        if len(bot._task_queues[chat_id]) >= max_q:
            await bot.send_message(
                chat_id,
                f"⚠️ *Task Queue Full* ({len(bot._task_queues[chat_id])}/{max_q} items).\n\n"
                "Please wait for active tasks to complete, or use `/cancel` to clear the queue.",
                reply_to_message_id=message_id,
            )
            return
        queued_item = QueuedTask(clean_query, message_id=message_id, item_type="btw_task")
        bot._task_queues[chat_id].append(queued_item)
        q_pos = len(bot._task_queues[chat_id])

        reply_text = (
            f"📥 *Queued Task for Later Execution (/btw):*\n"
            f"`{clean_query}`\n\n"
            f"• *Primary Task:* Continues in background ({last_action})\n"
            f"• *Queue Position:* `#{q_pos}`\n"
            f"• *Execution:* Will automatically run as soon as the active operation completes!"
        )
        await bot.send_message(chat_id, reply_text, reply_to_message_id=message_id)


async def handle_steer(bot: Any, chat_id: int, user_id: int, text: str, message_id: Optional[int] = None):
    directive = text.strip()
    if not directive:
        await bot.send_message(
            chat_id,
            "🧭 *Usage of `/steer`:*\n\n"
            "Use `/steer <instruction>` to immediately redirect or change the agent's course of action.\n\n"
            "• *Mid-Flight Intervention:* If an operation is running, `/steer <new direction>` instantly halts the active step and pivots to your new instructions within the same conversation.\n"
            "• *Direct Guidance:* If idle, `/steer <directive>` executes your instructions with high steering priority.\n\n"
            "*Examples:*\n"
            "• `/steer Stop creating Postgres tables, use SQLite with Prisma instead`\n"
            "• `/steer Switch focus to writing unit tests first`\n"
            "• `/steer Keep current backend code, but change UI to dark mode`",
            reply_to_message_id=message_id,
        )
        return

    is_running = chat_id in bot._active_tasks and not bot._active_tasks[chat_id].done()

    if is_running:
        info = bot._active_task_info.get(chat_id, {})
        info["steered"] = True
        last_action = info.get("last_action", "Executing operation...")
        task_prompt = info.get("text", "")
        task_preview = task_prompt.splitlines()[0] if task_prompt else "Ongoing operation"
        if len(task_preview) > 75:
            task_preview = task_preview[:72] + "..."

        # Cancel running task
        curr_task = bot._active_tasks.get(chat_id)
        if curr_task and not curr_task.done():
            curr_task.cancel()

        # Brief pause to allow cancellation cleanup to propagate
        await asyncio.sleep(0.1)

        steer_prompt = (
            f"[USER STEERING DIRECTIVE]\n"
            f"The user has explicitly intervened to steer and redirect your course of action.\n\n"
            f"• Previous Objective: {task_preview}\n"
            f"• Status Before Steering: {last_action}\n"
            f"• New Steering Direction: {directive}\n\n"
            f"Operating Instructions:\n"
            f"1. Immediately adopt the new steering direction above.\n"
            f"2. Stop and discard any previous sub-tasks, plans, or assumptions that conflict with this directive.\n"
            f"3. Acknowledge the course correction concisely and proceed to execute the new direction directly."
        )

        await bot.send_message(
            chat_id,
            f"🧭 *Course Correction (Steering Applied)*\n\n"
            f"• *Previous Action:* `{last_action}` (redirected)\n"
            f"• *New Direction:* `{directive}`\n\n"
            f"_Pivoting immediately into the updated direction..._",
            reply_to_message_id=message_id,
        )

        new_task = asyncio.create_task(
            bot.handle_chat_message(chat_id, user_id, steer_prompt, reply_to_message_id=message_id)
        )
        bot._active_tasks[chat_id] = new_task
        return
    else:
        steer_prompt = (
            f"[USER STEERING DIRECTIVE]\n"
            f"The user has provided an explicit steering directive:\n"
            f"{directive}\n\n"
            f"Operating Instructions:\n"
            f"1. Adopt this direction as top priority.\n"
            f"2. Proceed to execute according to this directive."
        )

        await bot.send_message(
            chat_id,
            f"🧭 *Steering Directive Applied:*\n`{directive}`\n\n_Executing with updated steering focus..._",
            reply_to_message_id=message_id,
        )

        task = asyncio.create_task(
            bot.handle_chat_message(chat_id, user_id, steer_prompt, reply_to_message_id=message_id)
        )
        bot._active_tasks[chat_id] = task
        return
