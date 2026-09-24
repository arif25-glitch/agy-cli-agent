"""
Persistent modular memory store coordinator for Gemini-Hermes.
Coordinates markdown memory files, user preferences, active backlog, and sessions.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from gemini_hermes.config import MEMORY_DIR, SESSIONS_DIR
from gemini_hermes.memory.templates import (
    DEFAULT_MEMORY_TEMPLATE,
    DEFAULT_USER_TEMPLATE,
    DEFAULT_BACKLOG_TEMPLATE,
    DEFAULT_REFERENCES_TEMPLATE,
)
from gemini_hermes.memory.session_store import SessionStore
from gemini_hermes.memory.archiver import BacklogArchiver

logger = logging.getLogger("gemini-hermes.memory")


class MemoryStore:
    """
    Facade managing long-term operational memory, user profiles,
    task backlogs, reference registries, and session persistence.
    """

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

        self.session_store = SessionStore(sessions_dir=self.sessions_dir)
        self.sessions_file = self.session_store.sessions_file

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

    # -------------------------------------------------------------------------
    # Core Markdown Document Accessors
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Session Persistence (Delegated to SessionStore)
    # -------------------------------------------------------------------------
    def _load_sessions(self) -> Dict[str, Any]:
        return self.session_store._load_sessions()

    def _save_sessions(self, data: Dict[str, Any]):
        self.session_store._save_sessions(data)

    def get_session(self, chat_id: int) -> Dict[str, Any]:
        return self.session_store.get_session(chat_id)

    def update_session(
        self,
        chat_id: int,
        conversation_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        turn_increment: int = 1,
    ):
        self.session_store.update_session(
            chat_id,
            conversation_id=conversation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            turn_increment=turn_increment,
        )

    def reset_session(self, chat_id: int):
        self.session_store.reset_session(chat_id)

    # -------------------------------------------------------------------------
    # Backlog Archiving & Hot Context (Delegated to BacklogArchiver)
    # -------------------------------------------------------------------------
    def get_archived_backlog(self) -> str:
        if self.backlog_archive_file.exists():
            return self.backlog_archive_file.read_text(encoding="utf-8")
        return ""

    def parse_backlog_items(self, content: Optional[str] = None) -> Dict[str, Any]:
        raw = content if content is not None else self.get_backlog()
        return BacklogArchiver.parse_backlog_items(raw)

    def get_hot_backlog(self, max_recent_completed: int = 5) -> str:
        return BacklogArchiver.get_hot_backlog(
            self.get_backlog(),
            self.get_archived_backlog(),
            max_recent_completed=max_recent_completed,
        )

    def archive_completed_backlog(self, keep_recent: int = 5) -> Dict[str, Any]:
        return BacklogArchiver.archive_completed_backlog(
            self.backlog_file,
            self.backlog_archive_file,
            keep_recent=keep_recent,
        )

    # -------------------------------------------------------------------------
    # Metrics & Context Rendering
    # -------------------------------------------------------------------------
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
