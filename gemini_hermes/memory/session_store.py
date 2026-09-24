"""
Session state persistence and token tracking store for Gemini-Hermes.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("gemini-hermes.memory.session")


class SessionStore:
    """
    Manages atomic persistence of active user sessions, conversation IDs,
    turn counts, and token usage metrics in sessions.json.
    """

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_file = self.sessions_dir / "sessions.json"
        if not self.sessions_file.exists():
            self._save_sessions({})

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
