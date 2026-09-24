"""
Telegram Gateway facade for Gemini-Hermes.
Orchestrates client communications, message routing, queuing, and execution workflows.
"""
import os
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
import httpx

from gemini_hermes.config import config
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.skills.manager import SkillManager
from gemini_hermes.projects.manager import ProjectManager
from gemini_hermes.brain.agy_forwarder import AgyForwarder
from gemini_hermes.services.jev_service import JevService
from gemini_hermes.jev.adapter import JevAdapter
from gemini_hermes.gateway.models import QueuedTask
from gemini_hermes.gateway.services.telegram_client import TelegramClient
from gemini_hermes.gateway.helpers.reply_parser import extract_reply_context
from gemini_hermes.gateway.helpers.intent_classifier import classify_btw_intent, classify_btw_intent_smart
from gemini_hermes.gateway.runner import ExecutionRunner
from gemini_hermes.gateway.handlers import (
    handle_unauthorized,
    handle_start,
    handle_help,
    handle_status,
    handle_exec,
    handle_model,
    handle_memory,
    handle_compact,
    handle_memory_add,
    handle_task_add,
    handle_ref_add,
    handle_memory_reset,
    handle_skills,
    handle_skill_detail,
    handle_projects,
    handle_project_detail,
    handle_project_add,
    handle_project_task,
    enqueue_task,
    run_queued_task,
    handle_queue,
    handle_cancel,
    handle_reset,
    handle_btw,
    handle_btw_ephemeral_question,
    handle_steer,
)

logger = logging.getLogger("gemini-hermes.telegram")

# Re-export QueuedTask for backward-compatibility
__all__ = ["QueuedTask", "TelegramBot"]


class TelegramBot(TelegramClient):
    """
    Main Gateway Controller for the Gemini-Hermes Telegram Bot.
    Serves as the high-level facade coordinating modular services, handlers, and runners.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        memory_store: Optional[MemoryStore] = None,
        skill_manager: Optional[SkillManager] = None,
        project_manager: Optional[ProjectManager] = None,
        forwarder: Optional[AgyForwarder] = None,
        jev_service: Optional[JevService] = None,
    ):
        token_val = token or config.bot_token
        super().__init__(token=token_val)

        self.memory_store = memory_store or MemoryStore()
        self.skill_manager = skill_manager or SkillManager()
        self.project_manager = project_manager or ProjectManager()
        self.forwarder = forwarder or AgyForwarder()
        self.jev_service = jev_service or JevService(cfg=config)
        effective_jev_cfg = getattr(self.jev_service, "config", config)
        self.jev_adapter = JevAdapter(cfg=effective_jev_cfg, client=getattr(self.jev_service, "_client", None))

        self.media_dir = os.path.join(config.workspace_dir, "data", "media")
        os.makedirs(self.media_dir, exist_ok=True)

        self.is_running = False
        self.last_update_id = 0
        self.bot_info: Dict[str, Any] = {}
        self._active_tasks: Dict[int, asyncio.Task] = {}
        self._active_task_info: Dict[int, Dict[str, Any]] = {}
        self._task_queues: Dict[int, List[str]] = {}
        self.max_queue_size: int = 10

    async def get_me(self) -> Dict[str, Any]:
        res = await super().get_me()
        if res:
            self.bot_info = res
        return res

    # -------------------------------------------------------------------------
    # Authentication & Access Control
    # -------------------------------------------------------------------------
    def is_user_allowed(self, user_id: int) -> bool:
        if not config.allowed_users:
            return True
        return user_id in config.allowed_users

    async def handle_unauthorized(self, chat_id: int, user_id: int):
        await handle_unauthorized(self, chat_id, user_id)

    # -------------------------------------------------------------------------
    # Command Handlers (Delegated to modular handlers)
    # -------------------------------------------------------------------------
    async def handle_start(self, chat_id: int, user_id: int):
        await handle_start(self, chat_id, user_id)

    async def handle_help(self, chat_id: int):
        await handle_help(self, chat_id)

    async def handle_status(self, chat_id: int):
        await handle_status(self, chat_id)

    async def handle_memory(self, chat_id: int):
        await handle_memory(self, chat_id)

    async def handle_compact(self, chat_id: int):
        await handle_compact(self, chat_id)

    async def handle_memory_add(self, chat_id: int, note: str):
        await handle_memory_add(self, chat_id, note)

    async def handle_task_add(self, chat_id: int, task: str):
        await handle_task_add(self, chat_id, task)

    async def handle_ref_add(self, chat_id: int, arg: str):
        await handle_ref_add(self, chat_id, arg)

    async def handle_skills(self, chat_id: int):
        await handle_skills(self, chat_id)

    async def handle_skill_detail(self, chat_id: int, skill_name: str):
        await handle_skill_detail(self, chat_id, skill_name)

    async def handle_projects(self, chat_id: int):
        await handle_projects(self, chat_id)

    async def handle_project_detail(self, chat_id: int, identifier: str):
        await handle_project_detail(self, chat_id, identifier)

    async def handle_project_add(self, chat_id: int, arg_str: str):
        await handle_project_add(self, chat_id, arg_str)

    async def handle_project_task(self, chat_id: int, arg_str: str):
        await handle_project_task(self, chat_id, arg_str)

    async def handle_exec(self, chat_id: int, command: str):
        await handle_exec(self, chat_id, command)

    # -------------------------------------------------------------------------
    # Intent & Sidecar (/btw) & Steering (/steer)
    # -------------------------------------------------------------------------
    def _classify_btw_intent(self, text: str):
        """Synchronous pure heuristic intent classification (zero external network)."""
        return classify_btw_intent(text)

    async def _classify_btw_intent_async(self, text: str):
        """Smart intent classification with Jev System-One support and heuristic fallback."""
        return await classify_btw_intent_smart(text, jev_adapter=self.jev_adapter)

    async def _handle_btw_ephemeral_question(
        self,
        chat_id: int,
        query: str,
        task_preview: Optional[str] = None,
        last_action: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ):
        await handle_btw_ephemeral_question(
            self,
            chat_id,
            query,
            task_preview=task_preview,
            last_action=last_action,
            reply_to_message_id=reply_to_message_id,
        )

    async def handle_btw(self, chat_id: int, user_id: int, text: str, message_id: Optional[int] = None):
        await handle_btw(self, chat_id, user_id, text, message_id=message_id)

    async def handle_steer(self, chat_id: int, user_id: int, text: str, message_id: Optional[int] = None):
        await handle_steer(self, chat_id, user_id, text, message_id=message_id)

    # -------------------------------------------------------------------------
    # Task Queue Management
    # -------------------------------------------------------------------------
    async def _enqueue_task(
        self,
        chat_id: int,
        item: str,
        item_type: str = "message",
        preview_override: Optional[str] = None,
        message_id: Optional[int] = None,
    ) -> bool:
        return await enqueue_task(
            self,
            chat_id=chat_id,
            item=item,
            item_type=item_type,
            preview_override=preview_override,
            message_id=message_id,
        )

    async def handle_queue(self, chat_id: int):
        await handle_queue(self, chat_id)

    async def _run_queued_task(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
    ):
        await run_queued_task(self, chat_id, user_id, text, reply_to_message_id=reply_to_message_id)

    # -------------------------------------------------------------------------
    # Core Execution Loop (Delegated to ExecutionRunner)
    # -------------------------------------------------------------------------
    async def handle_chat_message(
        self,
        chat_id: int,
        user_id: int,
        user_text: str,
        reply_to_message_id: Optional[int] = None,
    ):
        await ExecutionRunner.execute_turn(
            self,
            chat_id=chat_id,
            user_id=user_id,
            user_text=user_text,
            reply_to_message_id=reply_to_message_id,
        )

    # -------------------------------------------------------------------------
    # Message Dispatcher & Update Ingestion
    # -------------------------------------------------------------------------
    async def process_update(self, update: Dict[str, Any]):
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        from_user = msg.get("from", {})
        user_id = from_user.get("id")
        message_id = msg.get("message_id")
        text = msg.get("text", "")
        photo = msg.get("photo")
        doc = msg.get("document")
        caption = msg.get("caption", "").strip()
        reply_to = msg.get("reply_to_message")

        if not chat_id or not user_id:
            return

        # Security check
        if not self.is_user_allowed(user_id):
            logger.warning(f"Unauthorized access attempt from user_id={user_id}, chat_id={chat_id}")
            await self.handle_unauthorized(chat_id, user_id)
            return

        # Check if an active task is running in background for this chat
        is_task_running = chat_id in self._active_tasks and not self._active_tasks[chat_id].done()

        # Contextual quoting from inbound Telegram replies
        reply_context = extract_reply_context(reply_to)

        # Handle photos / images
        if photo:
            await self.send_chat_action(chat_id, "upload_photo")
            highest_photo = photo[-1]
            file_id = highest_photo.get("file_id")
            tg_file_path = await self.get_file_path(file_id) if file_id else None

            if tg_file_path:
                ext = os.path.splitext(tg_file_path)[1] or ".jpg"
                filename = f"photo_{chat_id}_{int(time.time())}_{file_id[:8]}{ext}"
                local_path = os.path.join(self.media_dir, filename)
                downloaded = await self.download_file_to(tg_file_path, local_path)
                if downloaded:
                    user_prompt = (
                        f"{reply_context}"
                        f"[Attached User Image: {local_path}]\n"
                        f"Caption / Question: {caption or 'Please inspect and analyze this image in detail.'}\n\n"
                        f"System Instruction: The user has attached an image in Telegram, saved on disk at '{local_path}'. "
                        f"You MUST use your `view_file` tool to inspect this image file and see its visual contents, "
                        f"then provide your detailed analysis or answer to the user's caption."
                    )
                    if is_task_running:
                        await self._enqueue_task(
                            chat_id=chat_id,
                            item=user_prompt,
                            item_type="image",
                            preview_override=f"Attached Image: {caption}" if caption else "Attached Image Analysis",
                            message_id=message_id,
                        )
                        return
                    else:
                        await self.handle_chat_message(
                            chat_id, user_id, user_prompt, reply_to_message_id=message_id
                        )
                        return
                else:
                    await self.send_message(
                        chat_id,
                        "⚠️ Failed to download the attached image. Please try again.",
                        reply_to_message_id=message_id,
                    )
                    return
            else:
                await self.send_message(
                    chat_id,
                    "⚠️ Could not retrieve image metadata from Telegram.",
                    reply_to_message_id=message_id,
                )
                return

        # Handle documents (e.g. image files or documents sent uncompressed)
        if doc:
            doc_mime = doc.get("mime_type", "")
            file_name = doc.get("file_name", f"doc_{int(time.time())}")
            file_id = doc.get("file_id")
            tg_file_path = await self.get_file_path(file_id) if file_id else None

            if tg_file_path:
                local_path = os.path.join(self.media_dir, f"{int(time.time())}_{file_name}")
                downloaded = await self.download_file_to(tg_file_path, local_path)
                if downloaded:
                    is_image = doc_mime.startswith("image/") or file_name.lower().endswith(
                        (".png", ".jpg", ".jpeg", ".webp", ".gif")
                    )
                    instruction = (
                        f"Use your `view_file` tool to view and visually analyze this image."
                        if is_image
                        else f"Use your file inspection tools to examine and analyze this file."
                    )
                    user_prompt = (
                        f"{reply_context}"
                        f"[Attached User File: {local_path}]\n"
                        f"File Name: {file_name} (MIME: {doc_mime})\n"
                        f"Caption / Question: {caption or f'Please inspect the attached file {file_name}.'}\n\n"
                        f"System Instruction: The user has attached a file in Telegram, saved on disk at '{local_path}'. "
                        f"{instruction} Then respond directly to the user."
                    )
                    if is_task_running:
                        await self._enqueue_task(
                            chat_id=chat_id,
                            item=user_prompt,
                            item_type="document",
                            preview_override=f"File ({file_name}): {caption}" if caption else f"Attached File: {file_name}",
                            message_id=message_id,
                        )
                        return
                    else:
                        await self.handle_chat_message(
                            chat_id, user_id, user_prompt, reply_to_message_id=message_id
                        )
                        return
                else:
                    await self.send_message(
                        chat_id,
                        "⚠️ Failed to download the attached file. Please try again.",
                        reply_to_message_id=message_id,
                    )
                    return

        if not text or not text.strip():
            await self.send_message(chat_id, "ℹ️ Please send text queries, commands, images, or documents.")
            return

        text = text.strip()

        # Handle commands
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].lower().split("@")[0]
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "/start":
                await self.handle_start(chat_id, user_id)
            elif cmd == "/help":
                await self.handle_help(chat_id)
            elif cmd in ("/new", "/reset"):
                await handle_reset(self, chat_id)
            elif cmd == "/btw":
                effective_arg = f"{reply_context}{arg}" if reply_context and arg else arg
                await self.handle_btw(chat_id, user_id, effective_arg, message_id=message_id)
            elif cmd in ("/steer", "/steer:"):
                effective_arg = f"{reply_context}{arg}" if reply_context and arg else arg
                await self.handle_steer(chat_id, user_id, effective_arg, message_id=message_id)
            elif cmd == "/queue":
                await self.handle_queue(chat_id)
            elif cmd == "/cancel":
                await handle_cancel(self, chat_id)
            elif cmd == "/status":
                await self.handle_status(chat_id)
            elif cmd == "/model":
                await handle_model(self, chat_id, arg)
            elif cmd == "/memory":
                await self.handle_memory(chat_id)
            elif cmd == "/compact":
                await self.handle_compact(chat_id)
            elif cmd == "/memory_add":
                await self.handle_memory_add(chat_id, arg)
            elif cmd == "/task_add":
                await self.handle_task_add(chat_id, arg)
            elif cmd == "/ref_add":
                await self.handle_ref_add(chat_id, arg)
            elif cmd == "/memory_reset":
                await handle_memory_reset(self, chat_id)
            elif cmd == "/skills":
                await self.handle_skills(chat_id)
            elif cmd == "/skill":
                await self.handle_skill_detail(chat_id, arg)
            elif cmd == "/projects":
                await self.handle_projects(chat_id)
            elif cmd == "/project":
                await self.handle_project_detail(chat_id, arg)
            elif cmd == "/project_add":
                await self.handle_project_add(chat_id, arg)
            elif cmd == "/project_task":
                await self.handle_project_task(chat_id, arg)
            elif cmd == "/exec":
                await self.handle_exec(chat_id, arg)
            else:
                await self.send_message(chat_id, f"❓ Unknown command: `{cmd}`. Type `/help` for available commands.")
        else:
            effective_text = f"{reply_context}{text}" if reply_context else text
            if is_task_running:
                await self._enqueue_task(
                    chat_id,
                    effective_text,
                    item_type="message",
                    message_id=message_id,
                )
            else:
                await self.handle_chat_message(
                    chat_id,
                    user_id,
                    effective_text,
                    reply_to_message_id=message_id,
                )

    # -------------------------------------------------------------------------
    # Lifecycle & Polling Loop
    # -------------------------------------------------------------------------
    async def run(self):
        if not self.token:
            logger.error("No Telegram Bot Token provided. Configure TELEGRAM_BOT_TOKEN in .env or run setup.")
            return

        self.client = httpx.AsyncClient(timeout=40.0)
        bot = await self.get_me()
        if not bot:
            logger.error("Failed to connect to Telegram API. Verify your bot token.")
            return

        self.is_running = True
        logger.info(f"Gemini-Hermes bot started as @{bot.get('username')} (ID: {bot.get('id')})")
        print(f"🚀 Gemini-Hermes Telegram Gateway is running as @{bot.get('username')}!")

        while self.is_running:
            try:
                res = await self._api_call(
                    "getUpdates",
                    {"offset": self.last_update_id + 1, "timeout": 25},
                    timeout=35.0,
                )
                if res.get("ok"):
                    updates = res.get("result", [])
                    for update in updates:
                        up_id = update.get("update_id", 0)
                        if up_id > self.last_update_id:
                            self.last_update_id = up_id
                        asyncio.create_task(self.process_update(update))
                else:
                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Telegram polling loop: {e}")
                await asyncio.sleep(3)

        if self.client and not self.client.is_closed:
            await self.client.aclose()
        logger.info("Telegram Bot stopped.")

    def stop(self):
        self.is_running = False
