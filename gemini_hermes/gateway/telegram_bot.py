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
from gemini_hermes.persona.system_prompt import build_system_prompt
from gemini_hermes.brain.agy_forwarder import AgyForwarder
from gemini_hermes.brain.stream_parser import TokenDelta, ForwarderResult, ToolExecutionUpdate
from gemini_hermes.gateway.formatter import (
    format_hermes_output,
    split_message,
    humanize_error,
    sanitize_streaming_markdown,
)

logger = logging.getLogger("gemini-hermes.telegram")


class TelegramBot:
    def __init__(
        self,
        token: Optional[str] = None,
        memory_store: Optional[MemoryStore] = None,
        skill_manager: Optional[SkillManager] = None,
        project_manager: Optional[ProjectManager] = None,
        forwarder: Optional[AgyForwarder] = None,
    ):
        self.token = token or config.bot_token
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.memory_store = memory_store or MemoryStore()
        self.skill_manager = skill_manager or SkillManager()
        self.project_manager = project_manager or ProjectManager()
        self.forwarder = forwarder or AgyForwarder()
        self.media_dir = os.path.join(config.workspace_dir, "data", "media")
        os.makedirs(self.media_dir, exist_ok=True)
        self.client: Optional[httpx.AsyncClient] = None
        self.is_running = False
        self.last_update_id = 0
        self.bot_info: Dict[str, Any] = {}
        self._active_tasks: Dict[int, asyncio.Task] = {}
        self._active_task_info: Dict[int, Dict[str, Any]] = {}
        self._task_queues: Dict[int, List[str]] = {}

    async def _api_call(self, method: str, json_data: Optional[Dict[str, Any]] = None, timeout: float = 35.0) -> Any:
        if not self.client or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=timeout)
        url = f"{self.api_url}/{method}"
        try:
            resp = await self.client.post(url, json=json_data, timeout=timeout)
            data = resp.json()
            if not data.get("ok"):
                logger.warning(f"Telegram API {method} returned not ok: {data}")
            return data
        except Exception as e:
            logger.error(f"Telegram API request {method} error: {e}")
            return {"ok": False, "error": str(e)}

    async def get_me(self) -> Dict[str, Any]:
        res = await self._api_call("getMe")
        if res.get("ok"):
            self.bot_info = res.get("result", {})
            return self.bot_info
        return {}

    async def get_file_path(self, file_id: str) -> Optional[str]:
        res = await self._api_call("getFile", {"file_id": file_id})
        if res.get("ok"):
            return res["result"].get("file_path")
        return None

    async def download_file_to(self, file_path: str, dest_path: str) -> bool:
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        try:
            if not self.client or self.client.is_closed:
                self.client = httpx.AsyncClient(timeout=60.0)
            resp = await self.client.get(file_url, timeout=60.0)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                logger.error(f"Download failed for {file_path}: status {resp.status_code}")
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {e}")
        return False

    async def send_message(
        self, chat_id: int, text: str, parse_mode: Optional[str] = "Markdown"
    ) -> Optional[int]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        res = await self._api_call("sendMessage", payload)
        if not res.get("ok") and parse_mode:
            # Fallback without markdown parsing if syntax error occurs
            res = await self._api_call(
                "sendMessage",
                {"chat_id": chat_id, "text": text},
            )
        if res.get("ok"):
            return res["result"]["message_id"]
        return None

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        res = await self._api_call(
            "deleteMessage",
            {"chat_id": chat_id, "message_id": message_id},
        )
        return bool(res.get("ok"))

    async def edit_message_text(
        self, chat_id: int, message_id: int, text: str, parse_mode: Optional[str] = "Markdown"
    ) -> bool:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        res = await self._api_call("editMessageText", payload)
        if not res.get("ok"):
            desc = res.get("description", "")
            if "message is not modified" in desc:
                return True
            if parse_mode:
                # Fallback without markdown
                fallback_res = await self._api_call(
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                    },
                )
                if not fallback_res.get("ok") and "message is not modified" in fallback_res.get("description", ""):
                    return True
                return bool(fallback_res.get("ok"))
        return bool(res.get("ok"))

    async def send_chat_action(self, chat_id: int, action: str = "typing"):
        await self._api_call("sendChatAction", {"chat_id": chat_id, "action": action}, timeout=10.0)

    def is_user_allowed(self, user_id: int) -> bool:
        if not config.allowed_users:
            return True
        return user_id in config.allowed_users

    async def handle_unauthorized(self, chat_id: int, user_id: int):
        msg = (
            f"⛔ *Access Restricted*\n\n"
            f"Your Telegram User ID: `{user_id}`\n"
            f"Chat ID: `{chat_id}`\n\n"
            f"To access Gemini-Hermes, add your User ID to `TELEGRAM_ALLOWED_USERS` in your `.env` configuration."
        )
        await self.send_message(chat_id, msg)

    async def handle_start(self, chat_id: int, user_id: int):
        skills_count = len(self.skill_manager.get_all_skills())
        text = (
            f"🤖 *Welcome to Gemini-Hermes (v{config.app_version})!*\n\n"
            f"I am an autonomous, persistent AI agent colleague inspired by *Nous Research's Hermes*, "
            f"powered by *Google Antigravity CLI (`agy`)* as my proxy model execution engine.\n\n"
            f"⚙️ *Engine:* Antigravity CLI Proxy (`agy`)\n"
            f"📦 *App Version:* `v{config.app_version}`\n"
            f"🧠 *Reasoning Effort:* `{config.reasoning_effort}`\n"
            f"💾 *Persistent Memory:* Active (`MEMORY.md` & `USER.md`)\n"
            f"🛠️ *Skills Catalog:* `{skills_count}` active skills\n\n"
            f"💡 *Commands:*\n"
            f"• `/new` or `/reset` - Start a fresh conversation\n"
            f"• `/status` - Check agent health and statistics\n"
            f"• `/memory` - Inspect persistent memory files\n"
            f"• `/memory_add <text>` - Save a permanent fact or instruction\n"
            f"• `/skills` - View all available modular skills\n"
            f"• `/skill <name>` - View skill procedure details\n"
            f"• `/exec <bash>` - Execute host shell command\n"
            f"• `/help` - Show this guide\n\n"
            f"Send me any question, project task, or instruction to begin!"
        )
        await self.send_message(chat_id, text)

    async def handle_help(self, chat_id: int):
        text = (
            f"📚 *Gemini-Hermes Command Reference:*\n\n"
            f"• `/new` / `/reset` - Clears the current conversation thread and begins a fresh session.\n"
            f"• `/status` - Shows active conversation ID, turns, token metrics, and engine status.\n"
            f"• `/memory` - Displays your current `MEMORY.md` and `USER.md` entries.\n"
            f"• `/memory_add <note>` - Manually saves a new note to persistent long-term memory.\n"
            f"• `/memory_reset` - Resets persistent memory to default initial state.\n"
            f"• `/skills` - Lists all modular procedural skills currently registered.\n"
            f"• `/skill <name>` - Displays the exact instructions and metadata of a skill.\n"
            f"• `/projects` - List all bookmarked projects and their state.\n"
            f"• `/project <id>` - Inspect detailed state, tasks, and tech stack of a project.\n"
            f"• `/project_add <name> <path>` - Bookmark a new active project into persistent state.\n"
            f"• `/project_task <id> <task>` - Add a new task or milestone to a project.\n"
            f"• `/btw <note/query>` - Ask a side question, steer, or queue a task while an operation is running.\n"
            f"• `/queue` - View active task and pending /btw queue.\n"
            f"• `/cancel` - Abort the active background task and clear the queue.\n"
            f"• `/exec <command>` - Runs a shell command on the host machine and streams the output.\n"
            f"• `/help` - Displays this menu.\n\n"
            f"💬 *Natural Conversation:*\n"
            f"You can also ask me directly to learn new skills, recall previous discussions, "
            f"research topics, analyze complex problems, and run multi-step workflows."
        )
        await self.send_message(chat_id, text)

    async def handle_status(self, chat_id: int):
        sess = self.memory_store.get_session(chat_id)
        health = await self.forwarder.check_health()
        status_symbol = "🟢 Online" if health.get("ok") else "🔴 Error"

        text = (
            f"📊 *Gemini-Hermes Status:*\n\n"
            f"• *App Version:* `v{config.app_version}`\n"
            f"• *Model Engine:* {status_symbol}\n"
            f"• *Binary:* `{self.forwarder.agy_bin}`\n"
            f"• *Reasoning Effort:* `{config.reasoning_effort}`\n"
            f"• *Current Conversation ID:* `{sess.get('conversation_id') or 'None (Fresh Session)'}`\n"
            f"• *Session Turns:* `{sess.get('turn_count', 0)}`\n"
            f"• *Tokens Used:* ~{sess.get('total_input_tokens', 0) + sess.get('total_output_tokens', 0):,}\n"
            f"• *Registered Skills:* `{len(self.skill_manager.get_all_skills())}`\n"
            f"• *Indexed Projects:* `{len(self.project_manager.list_projects())}`\n"
            f"• *Memory File:* `data/memory/MEMORY.md`"
        )
        await self.send_message(chat_id, text)

    async def handle_memory(self, chat_id: int):
        mem = self.memory_store.get_long_term_memory().strip()
        usr = self.memory_store.get_user_profile().strip()
        text = f"🧠 *Persistent Memory (`MEMORY.md`):*\n```markdown\n{mem[:1800]}\n```\n\n👤 *User Profile (`USER.md`):*\n```markdown\n{usr[:1800]}\n```"
        await self.send_message(chat_id, text)

    async def handle_memory_add(self, chat_id: int, note: str):
        if not note.strip():
            await self.send_message(chat_id, "⚠️ Please provide text to save: `/memory_add <text>`")
            return
        self.memory_store.append_to_memory(note)
        await self.send_message(chat_id, f"✅ Successfully saved to persistent memory:\n`{note.strip()}`")

    async def handle_skills(self, chat_id: int):
        skills = self.skill_manager.get_all_skills()
        if not skills:
            await self.send_message(chat_id, "No skills registered yet.")
            return

        lines = ["🛠️ *Registered Hermes Skills:*\n"]
        for s in skills.values():
            tags = f" `[{', '.join(s.tags)}]`" if s.tags else ""
            lines.append(f"• *{s.name}*{tags}\n  _{s.description}_")
        lines.append("\nUse `/skill <name>` to view full instructions.")
        await self.send_message(chat_id, "\n".join(lines))

    async def handle_skill_detail(self, chat_id: int, skill_name: str):
        skill = self.skill_manager.get_skill(skill_name.strip())
        if not skill:
            await self.send_message(chat_id, f"⚠️ Skill `{skill_name}` not found. Use `/skills` to list available.")
            return

        text = (
            f"📖 *Skill:* `{skill.name}` (v{skill.version})\n"
            f"*{skill.description}*\n\n"
            f"```markdown\n{skill.instructions[:3500]}\n```"
        )
        await self.send_message(chat_id, text)

    async def handle_projects(self, chat_id: int):
        projects = self.project_manager.list_projects()
        if not projects:
            await self.send_message(
                chat_id,
                "📁 No projects currently indexed. Use `/project_add <name> <path>` to bookmark one."
            )
            return

        lines = ["📁 *Indexed Projects (Persistent State):*\n"]
        for p in projects:
            lines.append(p.to_summary() + "\n")
        lines.append("Use `/project <id>` to inspect detailed state and tasks.")
        await self.send_message(chat_id, "\n".join(lines))

    async def handle_project_detail(self, chat_id: int, identifier: str):
        if not identifier.strip():
            await self.handle_projects(chat_id)
            return

        project = self.project_manager.get_project(identifier.strip())
        if not project:
            await self.send_message(chat_id, f"⚠️ Project `{identifier}` not found. Type `/projects` to list active projects.")
            return

        tasks_str = "\n".join(f"  {i+1}. {t}" for i, t in enumerate(project.active_tasks)) if project.active_tasks else "  (No pending tasks)"
        text = (
            f"📁 *Project:* `{project.name}` (`{project.id}`)\n"
            f"• *Status:* `{project.status}`\n"
            f"• *Path:* `{project.path}`\n"
            f"• *Tech Stack:* `{project.tech_stack or 'None'}`\n"
            f"• *Last Worked On:* `{project.last_worked_on[:19]}`\n\n"
            f"📝 *Description:*\n_{project.description or 'No description provided.'}_\n\n"
            f"📋 *Active Tasks:*\n{tasks_str}\n\n"
            f"💡 *Notes:*\n```\n{project.notes or 'No notes recorded.'}\n```"
        )
        await self.send_message(chat_id, text)

    async def handle_project_add(self, chat_id: int, arg_str: str):
        parts = arg_str.strip().split(maxsplit=2)
        if len(parts) < 2:
            await self.send_message(chat_id, "⚠️ Usage: `/project_add <name> <path> [description]`")
            return
        name = parts[0]
        path = parts[1]
        desc = parts[2] if len(parts) > 2 else ""
        proj = self.project_manager.bookmark_project(name=name, path=path, description=desc)
        await self.send_message(
            chat_id,
            f"✅ *Successfully bookmarked project:*\n"
            f"• Name: `{proj.name}`\n"
            f"• ID: `{proj.id}`\n"
            f"• Path: `{proj.path}`\n\n"
            f"Type `/project {proj.id}` to view details."
        )

    async def handle_project_task(self, chat_id: int, arg_str: str):
        parts = arg_str.strip().split(maxsplit=1)
        if len(parts) < 2:
            await self.send_message(chat_id, "⚠️ Usage: `/project_task <project_id> <task description>`")
            return
        pid = parts[0]
        task_desc = parts[1]
        proj = self.project_manager.add_task(pid, task_desc)
        if not proj:
            await self.send_message(chat_id, f"⚠️ Project `{pid}` not found. Use `/projects` to list.")
            return
        await self.send_message(chat_id, f"✅ Added task to *{proj.name}*:\n• `{task_desc}`")

    async def handle_exec(self, chat_id: int, command: str):
        if not command.strip():
            await self.send_message(chat_id, "⚠️ Usage: `/exec <bash command>`")
            return

        await self.send_chat_action(chat_id, "typing")
        status_msg_id = await self.send_message(chat_id, f"⚡ *Executing:* `{command}`...")

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        out_str = stdout.decode("utf-8", errors="replace")
        err_str = stderr.decode("utf-8", errors="replace")

        result = f"*Exit Code:* `{proc.returncode}`\n"
        if out_str.strip():
            result += f"**Output:**\n```\n{out_str[:3500]}\n```\n"
        if err_str.strip():
            result += f"**Errors:**\n```\n{err_str[:3500]}\n```"

        if status_msg_id:
            await self.edit_message_text(chat_id, status_msg_id, result)
        else:
            await self.send_message(chat_id, result)

    async def handle_btw(self, chat_id: int, user_id: int, text: str):
        query = text.strip()
        if not query:
            await self.send_message(
                chat_id,
                "ℹ️ *Usage of `/btw`:*\n"
                "• *Side quest / live status:* `/btw where are you now?`\n"
                "• *Steer active task:* `/btw remember to use Tailwind and SQLite`\n"
                "• *Queue next task:* `/btw after this, write a comprehensive README.md`",
            )
            return

        is_running = chat_id in self._active_tasks and not self._active_tasks[chat_id].done()

        if not is_running:
            # No task currently running - execute directly as a chat message
            await self.send_message(chat_id, f"💡 *Executing `/btw` directly:* `{query}`")
            task = asyncio.create_task(self.handle_chat_message(chat_id, user_id, query))
            self._active_tasks[chat_id] = task
            return

        # An active task is currently running in background
        info = self._active_task_info.get(chat_id, {})
        last_action = info.get("last_action", "Executing operation...")
        start_time = info.get("start_time", time.time())
        elapsed = int(time.time() - start_time)
        task_prompt = info.get("text", "")
        task_preview = task_prompt.splitlines()[0] if task_prompt else "Ongoing operation"
        if len(task_preview) > 75:
            task_preview = task_preview[:72] + "..."

        query_lower = query.lower()
        status_keywords = [
            "where are you", "what are you", "what are u", "where r u",
            "progress", "status", "how is", "how's", "sedang apa",
            "lagi apa", "sampai mana", "current step", "doing",
            "working on", "update", "how far", "is it done"
        ]
        is_inquiry = any(k in query_lower for k in status_keywords) or (
            query.endswith("?") and any(w in query_lower for w in ["now", "current", "step", "you", "task", "job", "doing"])
        )

        if is_inquiry:
            # Side Quest: Real-time telemetry response without stopping the primary background task
            status_text = (
                f"💬 *Side Query (Live Task Telemetry):*\n\n"
                f"• *Primary Task:* `{task_preview}`\n"
                f"• *Current Step:* {last_action}\n"
                f"• *Elapsed Time:* `{elapsed}s`\n"
                f"• *Status:* ⚙️ Actively executing in background\n\n"
                f"_The primary task continues uninterrupted._"
            )
            await self.send_message(chat_id, status_text)
            return

        # Steering directive or Queued Task
        if chat_id not in self._task_queues:
            self._task_queues[chat_id] = []
        self._task_queues[chat_id].append(query)
        q_pos = len(self._task_queues[chat_id])

        reply_text = (
            f"📥 *Received Side Note / Task (/btw):*\n"
            f"`{query}`\n\n"
            f"• *Primary Task:* Continues in background ({last_action})\n"
            f"• *Action:* Queued at position `#{q_pos}`\n"
            f"• *Execution:* I will evaluate and execute this steering instruction immediately once the active operation completes!"
        )
        await self.send_message(chat_id, reply_text)

    async def handle_queue(self, chat_id: int):
        q = self._task_queues.get(chat_id, [])
        is_running = chat_id in self._active_tasks and not self._active_tasks[chat_id].done()
        if not is_running and not q:
            await self.send_message(chat_id, "📭 Task queue is empty. No tasks are running.")
            return

        lines = ["📋 *Task Queue Status:*\n"]
        if is_running:
            info = self._active_task_info.get(chat_id, {})
            last_act = info.get("last_action", "Running...")
            lines.append(f"• *[ACTIVE]* Currently: `{last_act}`\n")
        if q:
            lines.append("*Queued /btw items:*")
            for i, item in enumerate(q, 1):
                preview = item if len(item) <= 70 else item[:67] + "..."
                lines.append(f"  {i}. `{preview}`")
        else:
            lines.append("• No pending queued items.")

        await self.send_message(chat_id, "\n".join(lines))

    async def _run_queued_task(self, chat_id: int, user_id: int, text: str):
        await asyncio.sleep(0.5)
        await self.send_message(
            chat_id,
            f"⚡ *Starting queued /btw instruction:*\n`{text}`",
        )
        task = asyncio.create_task(self.handle_chat_message(chat_id, user_id, text))
        self._active_tasks[chat_id] = task

    async def handle_chat_message(self, chat_id: int, user_id: int, user_text: str):
        curr_task = asyncio.current_task()
        if curr_task:
            self._active_tasks[chat_id] = curr_task

        self._active_task_info[chat_id] = {
            "text": user_text,
            "start_time": time.time(),
            "last_action": "Thinking and planning...",
            "status_count": 0,
            "user_id": user_id,
        }

        sess = self.memory_store.get_session(chat_id)
        conv_id = sess.get("conversation_id")

        # Build prompt with Hermes cognitive persona, memory, skills, and project index
        system_prompt = build_system_prompt(
            self.memory_store,
            self.skill_manager,
            project_manager=self.project_manager,
            current_chat_id=chat_id,
        )
        full_prompt = (
            f"{system_prompt}\n\n"
            f"### User Message\n{user_text}\n\n"
            f"Respond adhering to your Gemini-Hermes persona."
        )

        await self.send_chat_action(chat_id, "typing")

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
                        await self.send_chat_action(chat_id, "typing")
                    await asyncio.wait_for(stop_typing.wait(), timeout=4.5)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    break

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
                            pulse_text = f"⏳ Still executing: {action} ({elapsed}s elapsed)..."
                            await self.send_message(chat_id, pulse_text, parse_mode=None)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Tool heartbeat error: {e}")

        typing_task = asyncio.create_task(_typing_heartbeat())
        tool_heartbeat_task = asyncio.create_task(_tool_heartbeat())

        placeholder_id: Optional[int] = None
        if config.stream_updates:
            placeholder_id = await self.send_message(chat_id, "💭 *Gemini-Hermes is thinking...*")

        accumulated_text = ""
        last_edit_time = time.time()
        last_status_time = 0.0
        last_status_action = ""
        status_messages_sent = 0
        last_active_action = ""
        final_result: Optional[ForwarderResult] = None

        try:
            async for event in self.forwarder.forward_stream(full_prompt, conv_id):
                if isinstance(event, TokenDelta):
                    tool_active_event.clear()
                    current_tool_start[0] = 0.0
                    is_typing_active.set()
                    accumulated_text += event.text
                    now = time.time()
                    if (
                        placeholder_id
                        and config.stream_updates
                        and (now - last_edit_time >= config.stream_edit_interval)
                        and len(accumulated_text.strip()) > 0
                    ):
                        last_edit_time = now
                        formatted_preview = format_hermes_output(accumulated_text)
                        preview = sanitize_streaming_markdown(formatted_preview) + " ▌"
                        if len(preview) <= 4000:
                            await self.edit_message_text(chat_id, placeholder_id, preview)

                elif isinstance(event, ToolExecutionUpdate):
                    is_typing_active.clear()
                    tool_active_event.set()
                    current_tool_name[0] = event.action
                    current_tool_start[0] = time.time()
                    last_active_action = event.action
                    if chat_id in self._active_task_info:
                        self._active_task_info[chat_id]["last_action"] = event.action
                        self._active_task_info[chat_id]["status_count"] += 1
                    now = time.time()
                    interval = getattr(config, "status_notify_interval", 1.2)
                    if event.action != last_status_action and (now - last_status_time >= interval):
                        last_status_time = now
                        last_status_action = event.action
                        status_messages_sent += 1

                        # On first tool action, remove the initial thinking placeholder
                        if placeholder_id:
                            try:
                                await self.delete_message(chat_id, placeholder_id)
                            except Exception:
                                pass
                            placeholder_id = None

                        # Push status update message directly to Telegram
                        status_msg = f"🔨 Currently, {event.action}..."
                        await self.send_message(chat_id, status_msg, parse_mode=None)

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
            self.memory_store.update_session(
                chat_id,
                conversation_id=new_conv_id,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )

            # Format hermes output
            formatted_text = format_hermes_output(final_text)
            chunks = split_message(formatted_text)

            if placeholder_id:
                # No status messages sent; edit placeholder directly
                await self.edit_message_text(chat_id, placeholder_id, chunks[0])
                for chunk in chunks[1:]:
                    await self.send_message(chat_id, chunk)
            else:
                # Status messages were sent; send final response at bottom of conversation
                for chunk in chunks:
                    await self.send_message(chat_id, chunk)

        except asyncio.CancelledError:
            logger.info(f"Task for chat_id={chat_id} was cancelled by user.")
            cancel_msg = "🛑 *Operation Cancelled.*\nThe ongoing request was stopped."
            if placeholder_id:
                await self.edit_message_text(chat_id, placeholder_id, cancel_msg)
            else:
                await self.send_message(chat_id, cancel_msg)
            raise
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
            err_text = humanize_error(str(e), last_action=last_active_action)
            if placeholder_id:
                await self.edit_message_text(chat_id, placeholder_id, err_text)
            else:
                await self.send_message(chat_id, err_text)
        finally:
            stop_typing.set()
            if not typing_task.done():
                typing_task.cancel()
            if not tool_heartbeat_task.done():
                tool_heartbeat_task.cancel()
            self._active_tasks.pop(chat_id, None)
            self._active_task_info.pop(chat_id, None)

            # Check if there is a queued /btw task
            if chat_id in self._task_queues and self._task_queues[chat_id]:
                next_task_text = self._task_queues[chat_id].pop(0)
                logger.info(f"Triggering next queued task for chat_id={chat_id}: {next_task_text[:50]}")
                asyncio.create_task(self._run_queued_task(chat_id, user_id, next_task_text))

    async def process_update(self, update: Dict[str, Any]):
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        from_user = msg.get("from", {})
        user_id = from_user.get("id")
        text = msg.get("text", "")
        photo = msg.get("photo")
        doc = msg.get("document")
        caption = msg.get("caption", "").strip()

        if not chat_id or not user_id:
            return

        # Security check
        if not self.is_user_allowed(user_id):
            logger.warning(f"Unauthorized access attempt from user_id={user_id}, chat_id={chat_id}")
            await self.handle_unauthorized(chat_id, user_id)
            return

        # Check for active running task to prevent race conditions & lock contention
        is_command = bool(text and text.strip().startswith("/"))
        if not is_command and chat_id in self._active_tasks and not self._active_tasks[chat_id].done():
            await self.send_message(
                chat_id,
                "⏳ *Still processing...*\n\n"
                "I am currently working on your previous request. You can:\n"
                "• Ask a side question, steer, or queue a task with `/btw <message>`\n"
                "• Check live status with `/status`\n"
                "• View task queue with `/queue`\n"
                "• Type `/cancel` to abort or `/reset` to start fresh."
            )
            return

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
                        f"[Attached User Image: {local_path}]\n"
                        f"Caption / Question: {caption or 'Please inspect and analyze this image in detail.'}\n\n"
                        f"System Instruction: The user has attached an image in Telegram, saved on disk at '{local_path}'. "
                        f"You MUST use your `view_file` tool to inspect this image file and see its visual contents, "
                        f"then provide your detailed analysis or answer to the user's caption."
                    )
                    await self.handle_chat_message(chat_id, user_id, user_prompt)
                    return
                else:
                    await self.send_message(chat_id, "⚠️ Failed to download the attached image. Please try again.")
                    return
            else:
                await self.send_message(chat_id, "⚠️ Could not retrieve image metadata from Telegram.")
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
                    is_image = doc_mime.startswith("image/") or file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
                    instruction = (
                        f"Use your `view_file` tool to view and visually analyze this image."
                        if is_image
                        else f"Use your file inspection tools to examine and analyze this file."
                    )
                    user_prompt = (
                        f"[Attached User File: {local_path}]\n"
                        f"File Name: {file_name} (MIME: {doc_mime})\n"
                        f"Caption / Question: {caption or f'Please inspect the attached file {file_name}.'}\n\n"
                        f"System Instruction: The user has attached a file in Telegram, saved on disk at '{local_path}'. "
                        f"{instruction} Then respond directly to the user."
                    )
                    await self.handle_chat_message(chat_id, user_id, user_prompt)
                    return
                else:
                    await self.send_message(chat_id, "⚠️ Failed to download the attached file. Please try again.")
                    return

        if not text:
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
                if chat_id in self._active_tasks and not self._active_tasks[chat_id].done():
                    self._active_tasks[chat_id].cancel()
                    self._active_tasks.pop(chat_id, None)
                self._task_queues.pop(chat_id, None)
                self._active_task_info.pop(chat_id, None)
                self.memory_store.reset_session(chat_id)
                await self.send_message(
                    chat_id,
                    "🔄 *Conversation reset.* Ongoing background tasks have been stopped, and a fresh session initiated!",
                )
            elif cmd == "/btw":
                await self.handle_btw(chat_id, user_id, arg)
            elif cmd == "/queue":
                await self.handle_queue(chat_id)
            elif cmd == "/cancel":
                cancelled = False
                if chat_id in self._active_tasks and not self._active_tasks[chat_id].done():
                    self._active_tasks[chat_id].cancel()
                    self._active_tasks.pop(chat_id, None)
                    cancelled = True
                self._active_task_info.pop(chat_id, None)
                q_count = len(self._task_queues.get(chat_id, []))
                self._task_queues.pop(chat_id, None)
                if cancelled or q_count:
                    await self.send_message(chat_id, f"🛑 Ongoing task cancelled and {q_count} queued item(s) cleared.")
                else:
                    await self.send_message(chat_id, "ℹ️ No running task or queued items to cancel.")
            elif cmd == "/status":
                await self.handle_status(chat_id)
            elif cmd == "/memory":
                await self.handle_memory(chat_id)
            elif cmd == "/memory_add":
                await self.handle_memory_add(chat_id, arg)
            elif cmd == "/memory_reset":
                self.memory_store.reset_long_term_memory()
                await self.send_message(chat_id, "🧹 Long-term memory has been reset to defaults.")
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
            await self.handle_chat_message(chat_id, user_id, text)

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
