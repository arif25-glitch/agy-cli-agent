import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from gemini_hermes.config import MEMORY_DIR, SESSIONS_DIR
from gemini_hermes.memory.templates import (
    DEFAULT_MEMORY_TEMPLATE,
    DEFAULT_USER_TEMPLATE,
    DEFAULT_BACKLOG_TEMPLATE,
    DEFAULT_REFERENCES_TEMPLATE,
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
        self.sessions_file = self.sessions_dir / "sessions.json"

        self._init_defaults()

    def _init_defaults(self):
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

    def render_memory_context(self) -> str:
        mem = self.get_long_term_memory().strip()
        usr = self.get_user_profile().strip()
        backlog = self.get_backlog().strip()
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
