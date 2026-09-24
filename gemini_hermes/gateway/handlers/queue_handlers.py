"""
Queue management and lifecycle command handlers: enqueue, sequential drain, /queue, /cancel, /reset.
"""
import asyncio
import logging
from typing import Any, Optional
from gemini_hermes.gateway.models import QueuedTask

logger = logging.getLogger("gemini-hermes.telegram.queue")


async def enqueue_task(
    bot: Any,
    chat_id: int,
    item: str,
    item_type: str = "message",
    preview_override: Optional[str] = None,
    message_id: Optional[int] = None,
) -> bool:
    """
    Enqueues an item (chat message, image prompt, doc prompt) into the sequential task queue.
    Enforces max_queue_size to prevent runaway memory or queue exhaustion.
    """
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
        return False

    queued_item = (
        item if isinstance(item, QueuedTask)
        else QueuedTask(item, message_id=message_id, item_type=item_type)
    )
    bot._task_queues[chat_id].append(queued_item)
    q_pos = len(bot._task_queues[chat_id])

    if preview_override:
        preview = preview_override
    elif item_type == "image":
        preview = "Attached Image Analysis"
    elif item_type == "document":
        preview = "Attached File Analysis"
    else:
        preview = item if len(item) <= 80 else item[:77] + "..."

    type_label = item_type.capitalize()
    await bot.send_message(
        chat_id,
        f"📥 *{type_label} Queued* (`#{q_pos}` in queue)\n"
        f"`{preview}`\n\n"
        f"• *Status:* Active operation still executing\n"
        f"• *Next:* Will run automatically once current task completes.\n"
        f"• _Quick actions: `/steer <msg>` to redirect now | `/queue` | `/cancel`_",
        reply_to_message_id=message_id,
    )
    return True


async def run_queued_task(
    bot: Any,
    chat_id: int,
    user_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None,
):
    try:
        await asyncio.sleep(0.5)
        if reply_to_message_id is None:
            reply_to_message_id = getattr(text, "message_id", None)

        item_type = getattr(text, "item_type", "")
        if item_type == "image" or "[Attached User Image:" in text:
            notice = "⚡ *Processing queued image analysis...*"
        elif item_type == "document" or "[Attached User File:" in text:
            notice = "⚡ *Processing queued file analysis...*"
        else:
            preview = text if len(text) <= 80 else text[:77] + "..."
            notice = f"⚡ *Processing queued task:*\n`{preview}`"
        await bot.send_message(chat_id, notice, reply_to_message_id=reply_to_message_id)
        task = asyncio.create_task(
            bot.handle_chat_message(chat_id, user_id, text, reply_to_message_id=reply_to_message_id)
        )
        bot._active_tasks[chat_id] = task
    except Exception as e:
        logger.error(f"Error starting queued task for chat_id={chat_id}: {e}", exc_info=True)


async def handle_queue(bot: Any, chat_id: int):
    q = bot._task_queues.get(chat_id, [])
    is_running = chat_id in bot._active_tasks and not bot._active_tasks[chat_id].done()
    if not is_running and not q:
        await bot.send_message(chat_id, "📭 Task queue is empty. No tasks are running.")
        return

    lines = ["📋 *Task Queue Status:*\n"]
    if is_running:
        info = bot._active_task_info.get(chat_id, {})
        last_act = info.get("last_action", "Running...")
        lines.append(f"• *[ACTIVE]* Currently: `{last_act}`\n")
    if q:
        lines.append("*Queued items:*")
        for i, item in enumerate(q, 1):
            preview = item if len(item) <= 70 else item[:67] + "..."
            lines.append(f"  {i}. `{preview}`")
    else:
        lines.append("• No pending queued items.")

    await bot.send_message(chat_id, "\n".join(lines))


async def handle_cancel(bot: Any, chat_id: int):
    cancelled = False
    if chat_id in bot._active_tasks and not bot._active_tasks[chat_id].done():
        bot._active_tasks[chat_id].cancel()
        bot._active_tasks.pop(chat_id, None)
        cancelled = True
    bot._active_task_info.pop(chat_id, None)
    q_count = len(bot._task_queues.get(chat_id, []))
    bot._task_queues.pop(chat_id, None)
    if cancelled or q_count:
        await bot.send_message(chat_id, f"🛑 Ongoing task cancelled and {q_count} queued item(s) cleared.")
    else:
        await bot.send_message(chat_id, "ℹ️ No running task or queued items to cancel.")


async def handle_reset(bot: Any, chat_id: int):
    if chat_id in bot._active_tasks and not bot._active_tasks[chat_id].done():
        bot._active_tasks[chat_id].cancel()
        bot._active_tasks.pop(chat_id, None)
    bot._task_queues.pop(chat_id, None)
    bot._active_task_info.pop(chat_id, None)
    bot.memory_store.reset_session(chat_id)
    await bot.send_message(
        chat_id,
        "🔄 *Conversation reset.* Ongoing background tasks have been stopped, and a fresh session initiated!",
    )
