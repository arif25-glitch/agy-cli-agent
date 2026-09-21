import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from gemini_hermes.config import MEMORY_DIR, SESSIONS_DIR
from gemini_hermes.memory.templates import (
    DEFAULT_MEMORY_TEMPLATE,
    DEFAULT_USER_TEMPLATE,
    DEFAULT_BACKLOG_TEMPLATE,
    DEFAULT_REFERENCES_TEMPLATE,
    DEFAULT_ARCHIVE_TEMPLATE,
)

logger = logging.getLogger("gemini-hermes.memory")



class MemoryStore:
    def __init__(self, memory_dir: Path = MEMORY_DIR, sessions_dir: Path = SESSIONS_DIR):
        self.memory_dir = memory_dir
        self.sessions_dir = sessions_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.memory_file = self.memory_dir / "MEMORY.md"
        self.user_file = self.memory_dir / "USER.md"
        self.backlog_file = self.memory_dir / "BACKLOG.md"
        self.references_file = self.memory_dir / "REFERENCES.md"
        self.archive_dir = self.memory_dir / "archive"
        self.backlog_archive_file = self.archive_dir / "BACKLOG_ARCHIVE.md"
        self.sessions_file = self.sessions_dir / "sessions.json"

        self._init_defaults()

    def _init_defaults(self):
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        if not self.memory_file.exists():
            default_memory = DEFAULT_MEMORY_TEMPLATE.format(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            self.memory_file.write_text(default_memory, encoding="utf-8")

        if not self.user_file.exists():
            self.user_file.write_text(DEFAULT_USER_TEMPLATE, encoding="utf-8")

        if not self.backlog_file.exists():
            self.backlog_file.write_text(DEFAULT_BACKLOG_TEMPLATE, encoding="utf-8")

        if not self.references_file.exists():
            self.references_file.write_text(DEFAULT_REFERENCES_TEMPLATE, encoding="utf-8")

        if not self.sessions_file.exists():
            self._save_sessions({})

    def get_long_term_memory(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def get_user_profile(self) -> str:
        if self.user_file.exists():
            return self.user_file.read_text(encoding="utf-8")
        return ""

    def get_backlog(self) -> str:
        if self.backlog_file.exists():
            return self.backlog_file.read_text(encoding="utf-8")
        return ""

    def get_references(self) -> str:
        if self.references_file.exists():
            return self.references_file.read_text(encoding="utf-8")
        return ""

    def append_to_memory(self, note: str, section: str = "Key Facts & Lessons"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"- [{timestamp}] {note.strip()}\n"
        content = self.get_long_term_memory()

        if f"## {section}" in content:
            parts = content.split(f"## {section}")
            new_content = parts[0] + f"## {section}\n" + entry + parts[1].lstrip("\n")
        else:
            new_content = content.rstrip() + f"\n\n## {section}\n" + entry

        self.memory_file.write_text(new_content, encoding="utf-8")
        logger.info(f"Appended memory note: {note[:60]}...")

    def update_user_profile(self, preference: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"- [{timestamp}] {preference.strip()}\n"
        content = self.get_user_profile()
        new_content = content.rstrip() + "\n" + entry
        self.user_file.write_text(new_content, encoding="utf-8")
        logger.info(f"Updated user profile: {preference[:60]}...")

    def append_to_backlog(self, task: str, section: str = "Active Tasks"):
        entry = f"- {task.strip()}\n"
        content = self.get_backlog()

        if f"## {section}" in content:
            parts = content.split(f"## {section}")
            new_content = parts[0] + f"## {section}\n" + entry + parts[1].lstrip("\n")
        else:
            new_content = content.rstrip() + f"\n\n## {section}\n" + entry

        self.backlog_file.write_text(new_content, encoding="utf-8")
        logger.info(f"Appended backlog task: {task[:60]}...")

    def append_to_references(self, title: str, url: str, section: str = "Sheets & Spreadsheets"):
        entry = f"- {title.strip()}: {url.strip()}\n"
        content = self.get_references()

        if f"## {section}" in content:
            parts = content.split(f"## {section}")
            new_content = parts[0] + f"## {section}\n" + entry + parts[1].lstrip("\n")
        else:
            new_content = content.rstrip() + f"\n\n## {section}\n" + entry

        self.references_file.write_text(new_content, encoding="utf-8")
        logger.info(f"Appended reference: {title[:60]}...")

    def reset_long_term_memory(self):
        self.memory_file.unlink(missing_ok=True)
        self.user_file.unlink(missing_ok=True)
        self.backlog_file.unlink(missing_ok=True)
        self.references_file.unlink(missing_ok=True)
        self._init_defaults()

    def _load_sessions(self) -> Dict[str, Any]:
        if self.sessions_file.exists():
            try:
                return json.loads(self.sessions_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Error loading sessions file: {e}")
        return {}

    def _save_sessions(self, data: Dict[str, Any]):
        self.sessions_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_session(self, chat_id: int) -> Dict[str, Any]:
        sessions = self._load_sessions()
        key = str(chat_id)
        if key not in sessions:
            sessions[key] = {
                "chat_id": chat_id,
                "conversation_id": None,
                "turn_count": 0,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            }
            self._save_sessions(sessions)
        return sessions[key]

    def update_session(
        self,
        chat_id: int,
        conversation_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        turn_increment: int = 1,
    ):
        sessions = self._load_sessions()
        key = str(chat_id)
        sess = sessions.get(
            key,
            {
                "chat_id": chat_id,
                "conversation_id": None,
                "turn_count": 0,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            },
        )

        if conversation_id:
            sess["conversation_id"] = conversation_id
        sess["turn_count"] = sess.get("turn_count", 0) + turn_increment
        sess["last_active"] = datetime.now().isoformat()
        sess["total_input_tokens"] = sess.get("total_input_tokens", 0) + input_tokens
        sess["total_output_tokens"] = sess.get("total_output_tokens", 0) + output_tokens

        sessions[key] = sess
        self._save_sessions(sessions)

    def reset_session(self, chat_id: int):
        sessions = self._load_sessions()
        key = str(chat_id)
        if key in sessions:
            sessions[key]["conversation_id"] = None
            sessions[key]["turn_count"] = 0
            sessions[key]["last_active"] = datetime.now().isoformat()
            self._save_sessions(sessions)
            logger.info(f"Reset session conversation for chat_id={chat_id}")

    def get_archived_backlog(self) -> str:
        if self.backlog_archive_file.exists():
            return self.backlog_archive_file.read_text(encoding="utf-8")
        return ""

    def parse_backlog_items(self, content: Optional[str] = None) -> Dict[str, Any]:
        """
        Parses BACKLOG.md into structured components:
        - header: everything before the tasks section (including '## Active Tasks')
        - completed: list of completed task item blocks (including multiline sub-bullets)
        - active: list of active/uncompleted task item blocks
        - placeholders: list of placeholder item blocks (e.g. '(Active tasks will be tracked here)')
        - footer: footer sections (e.g. '## Operational Notes & Inquiries')
        """
        if content is None:
            content = self.get_backlog()

        lines = content.splitlines()
        header_lines = []
        task_blocks = []
        footer_lines = []

        state = "header"
        current_block = []

        for line in lines:
            if state == "header":
                header_lines.append(line)
                if line.strip().startswith("## Active Tasks"):
                    state = "tasks"
            elif state == "tasks":
                if line.strip().startswith("## "):
                    if current_block:
                        task_blocks.append("\n".join(current_block))
                        current_block = []
                    state = "footer"
                    footer_lines.append(line)
                else:
                    stripped = line.strip()
                    is_new_item = (
                        (line.startswith("- ") or line.startswith("* "))
                        and (
                            stripped.startswith("- [")
                            or stripped.startswith("* [")
                            or stripped.startswith("- (")
                            or stripped.startswith("* (")
                        )
                    )
                    if is_new_item:
                        if current_block:
                            task_blocks.append("\n".join(current_block))
                            current_block = []
                        current_block.append(line)
                    elif current_block and (line.startswith(" ") or line.startswith("\t") or not stripped):
                        current_block.append(line)
                    elif stripped:
                        if current_block:
                            task_blocks.append("\n".join(current_block))
                            current_block = []
                        current_block.append(line)
            elif state == "footer":
                footer_lines.append(line)

        if current_block:
            task_blocks.append("\n".join(current_block))

        completed = []
        active = []
        placeholders = []

        for block in task_blocks:
            first_line = block.strip().splitlines()[0] if block.strip() else ""
            if re.match(r"^[-*]\s*\[[xX]\]", first_line):
                completed.append(block)
            elif re.match(r"^[-*]\s*\[\s*\]", first_line):
                active.append(block)
            else:
                placeholders.append(block)

        return {
            "header": "\n".join(header_lines).rstrip(),
            "completed": completed,
            "active": active,
            "placeholders": placeholders,
            "footer": "\n".join(footer_lines).strip(),
        }

    def get_hot_backlog(self, max_recent_completed: int = 5) -> str:
        """
        Returns a high-signal hot context backlog slice:
        - Keeps ALL active items [ ]
        - Keeps only the last `max_recent_completed` completed tasks [x]
        - Mentions count of archived tasks if any exist
        """
        content = self.get_backlog().strip()
        if not content:
            return ""

        parsed = self.parse_backlog_items(content)
        completed = parsed["completed"]
        active = parsed["active"]
        placeholders = parsed["placeholders"]

        # Check total archived items on disk
        archived_text = self.get_archived_backlog()
        archived_count = len(re.findall(r"^[-*]\s*\[[xX]\]", archived_text, re.MULTILINE))

        # Check if completed items in BACKLOG.md exceed max_recent_completed
        if len(completed) > max_recent_completed:
            overflow_count = len(completed) - max_recent_completed
            retained_completed = completed[-max_recent_completed:]
            total_off_prompt = archived_count + overflow_count
        else:
            retained_completed = completed
            total_off_prompt = archived_count

        task_lines = []
        if active:
            task_lines.extend(active)
        elif not retained_completed and placeholders:
            task_lines.extend(placeholders)

        if retained_completed:
            task_lines.extend(retained_completed)

        if total_off_prompt > 0:
            task_lines.append(
                f"- *(+{total_off_prompt} older completed tasks archived in data/memory/archive/BACKLOG_ARCHIVE.md)*"
            )

        tasks_rendered = "\n".join(task_lines)
        header = parsed["header"]
        footer = parsed["footer"]

        parts = [header, tasks_rendered]
        if footer:
            parts.append(footer)
        return "\n\n".join(parts)

    def archive_completed_backlog(self, keep_recent: int = 5) -> Dict[str, Any]:
        """
        Physically migrates completed tasks older than `keep_recent` to BACKLOG_ARCHIVE.md.
        Keeps BACKLOG.md lean and hot context sharp.
        """
        content = self.get_backlog().strip()
        if not content:
            return {"status": "empty", "archived_count": 0, "retained_count": 0, "active_count": 0}

        parsed = self.parse_backlog_items(content)
        completed = parsed["completed"]
        active = parsed["active"]
        placeholders = parsed["placeholders"]
        header = parsed["header"]
        footer = parsed["footer"]

        if len(completed) <= keep_recent:
            return {
                "status": "noop",
                "archived_count": 0,
                "retained_count": len(completed),
                "active_count": len(active),
            }

        to_archive = completed[:-keep_recent]
        to_retain = completed[-keep_recent:]

        # Ensure archive file exists with header
        if not self.backlog_archive_file.exists():
            from gemini_hermes.memory.templates import DEFAULT_ARCHIVE_TEMPLATE
            self.backlog_archive_file.write_text(DEFAULT_ARCHIVE_TEMPLATE, encoding="utf-8")

        # Append to archive file
        existing_archive = self.backlog_archive_file.read_text(encoding="utf-8").rstrip()
        archive_block = "\n".join(to_archive)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_archive = f"{existing_archive}\n\n### Archived on {timestamp}\n{archive_block}\n"
        self.backlog_archive_file.write_text(new_archive, encoding="utf-8")

        # Rebuild BACKLOG.md
        rebuilt_tasks = []
        if active:
            rebuilt_tasks.extend(active)
        elif placeholders:
            rebuilt_tasks.extend(placeholders)

        if to_retain:
            rebuilt_tasks.extend(to_retain)

        rebuilt_body = "\n".join(rebuilt_tasks)
        parts = [header, rebuilt_body]
        if footer:
            parts.append(footer)

        new_backlog = "\n\n".join(parts) + "\n"
        self.backlog_file.write_text(new_backlog, encoding="utf-8")

        logger.info(
            f"Archived {len(to_archive)} completed tasks to {self.backlog_archive_file}. Retained {len(to_retain)}."
        )

        return {
            "status": "archived",
            "archived_count": len(to_archive),
            "retained_count": len(to_retain),
            "active_count": len(active),
            "archive_file": str(self.backlog_archive_file),
        }

    def get_memory_stats(self) -> Dict[str, Any]:
        """Calculates token and character metrics for all memory layers."""
        def file_stats(path: Path):
            if not path.exists():
                return {"chars": 0, "lines": 0, "tokens": 0}
            text = path.read_text(encoding="utf-8")
            chars = len(text)
            lines = len(text.splitlines())
            tokens = int(chars / 3.8)
            return {"chars": chars, "lines": lines, "tokens": tokens}

        mem_stat = file_stats(self.memory_file)
        usr_stat = file_stats(self.user_file)
        raw_backlog_stat = file_stats(self.backlog_file)
        hot_backlog = self.get_hot_backlog()
        hot_backlog_stat = {
            "chars": len(hot_backlog),
            "lines": len(hot_backlog.splitlines()),
            "tokens": int(len(hot_backlog) / 3.8),
        }
        refs_stat = file_stats(self.references_file)
        archive_stat = file_stats(self.backlog_archive_file)

        hot_tokens = mem_stat["tokens"] + usr_stat["tokens"] + hot_backlog_stat["tokens"] + refs_stat["tokens"]
        total_tokens = mem_stat["tokens"] + usr_stat["tokens"] + raw_backlog_stat["tokens"] + refs_stat["tokens"] + archive_stat["tokens"]

        return {
            "hot_tokens": hot_tokens,
            "total_tokens": total_tokens,
            "archived_tokens": archive_stat["tokens"],
            "files": {
                "MEMORY.md": mem_stat,
                "USER.md": usr_stat,
                "BACKLOG.md (raw)": raw_backlog_stat,
                "BACKLOG.md (hot)": hot_backlog_stat,
                "REFERENCES.md": refs_stat,
                "BACKLOG_ARCHIVE.md": archive_stat,
            },
        }

    def render_memory_context(self, max_recent_completed: int = 5) -> str:
        mem = self.get_long_term_memory().strip()
        usr = self.get_user_profile().strip()
        backlog = self.get_hot_backlog(max_recent_completed=max_recent_completed).strip()
        refs = self.get_references().strip()

        context_parts = []
        if mem:
            context_parts.append(f"<persistent_memory>\n{mem}\n</persistent_memory>")
        if usr:
            context_parts.append(f"<user_profile>\n{usr}\n</user_profile>")
        if backlog:
            context_parts.append(f"<active_backlog>\n{backlog}\n</active_backlog>")
        if refs:
            context_parts.append(f"<external_references>\n{refs}\n</external_references>")
        return "\n\n".join(context_parts)

