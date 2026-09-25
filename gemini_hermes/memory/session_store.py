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
                "lifetime_turns": 0,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "session_input_tokens": 0,
                "session_output_tokens": 0,
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
                "lifetime_turns": 0,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "session_input_tokens": 0,
                "session_output_tokens": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
            },
        )

        if conversation_id:
            sess["conversation_id"] = conversation_id
        sess["turn_count"] = sess.get("turn_count", 0) + turn_increment
        sess["lifetime_turns"] = sess.get("lifetime_turns", sess.get("turn_count", 0)) + turn_increment
        sess["last_active"] = datetime.now().isoformat()
        sess["session_input_tokens"] = sess.get("session_input_tokens", 0) + input_tokens
        sess["session_output_tokens"] = sess.get("session_output_tokens", 0) + output_tokens
        sess["total_input_tokens"] = sess.get("total_input_tokens", 0) + input_tokens
        sess["total_output_tokens"] = sess.get("total_output_tokens", 0) + output_tokens

        sess["last_turn_input_tokens"] = input_tokens
        if sess.get("session_baseline_tokens", 0) == 0 and input_tokens > 0:
            sess["session_baseline_tokens"] = input_tokens

        sessions[key] = sess
        self._save_sessions(sessions)

    def reset_session(self, chat_id: int):
        sessions = self._load_sessions()
        key = str(chat_id)
        if key in sessions:
            sessions[key]["conversation_id"] = None
            sessions[key]["turn_count"] = 0
            sessions[key]["session_input_tokens"] = 0
            sessions[key]["session_output_tokens"] = 0
            sessions[key]["session_baseline_tokens"] = 0
            sessions[key]["last_turn_input_tokens"] = 0
            sessions[key]["last_active"] = datetime.now().isoformat()
            sessions[key].pop("context_bridge", None)
            self._save_sessions(sessions)
            logger.info(f"Reset session conversation for chat_id={chat_id}")

    def should_rotate_session(
        self,
        chat_id: int,
        max_tokens: int = 50000,
        max_turns: int = 15,
        min_turns: int = 2,
        max_growth_tokens: int = 40000,
        growth_ratio: float = 2.0,
        hard_max_tokens: int = 120000,
    ) -> bool:
        """
        Determines whether the active session should rotate to a fresh conversation ID
        using dynamic relative growth calculations to prevent the rotation loop.

        Guarantees:
        - Never rotates on initial turns (< min_turns), breaking the single-turn rotation loop.
        - Rotates if context grows beyond relative growth threshold (+max_growth_tokens) from baseline.
        - Rotates if turn count reaches max_turns ceiling.
        - Rotates if hard ceiling (hard_max_tokens) is breached to prevent window overflow.
        """
        sess = self.get_session(chat_id)
        conv_id = sess.get("conversation_id")
        if not conv_id:
            return False

        turns = sess.get("turn_count", 0)
        in_tok = sess.get("session_input_tokens", 0)
        last_tok = sess.get("last_turn_input_tokens", 0)
        current_context = last_tok if last_tok > 0 else in_tok
        baseline = sess.get("session_baseline_tokens", 0)

        # 1. Hard ceiling safety check: if context exceeds hard_max_tokens, rotate immediately
        if hard_max_tokens and (current_context >= hard_max_tokens or in_tok >= hard_max_tokens * 2):
            logger.info(
                f"Session rotation triggered: Hard token ceiling ({current_context} >= {hard_max_tokens}) for chat_id={chat_id}"
            )
            return True

        # 2. Turn limit ceiling: if turn count reaches max_turns, rotate
        if max_turns and turns >= max_turns:
            logger.info(
                f"Session rotation triggered: Max turns reached ({turns} >= {max_turns}) for chat_id={chat_id}"
            )
            return True

        # 3. Minimum turns guardrail: do NOT rotate on initial turns (< min_turns)
        # This fundamentally breaks the single-turn Rotation Loop when base context is large!
        if turns < min_turns:
            return False

        # 4. Relative growth check (measured against initial session baseline)
        if baseline > 0:
            growth = max(0, current_context - baseline)
            if max_growth_tokens and growth >= max_growth_tokens:
                logger.info(
                    f"Session rotation triggered: Relative token growth ({growth} >= {max_growth_tokens}) for chat_id={chat_id}"
                )
                return True
            if (
                growth_ratio
                and (current_context / baseline) >= growth_ratio
                and (current_context >= max_tokens or in_tok >= max_tokens)
            ):
                logger.info(
                    f"Session rotation triggered: Growth ratio ({current_context / baseline:.2f} >= {growth_ratio}) for chat_id={chat_id}"
                )
                return True

        # 5. Standard fallback threshold (if baseline is 0 / unrecorded)
        if not baseline and max_tokens and (current_context >= max_tokens or in_tok >= max_tokens):
            logger.info(
                f"Session rotation triggered: Token ceiling ({current_context} >= {max_tokens}) for chat_id={chat_id}"
            )
            return True

        return False

    def rotate_session_with_bridge(
        self,
        chat_id: int,
        bridge_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rotates an active session to a fresh conversation ID, preserving lifetime token metrics
        and storing a context bridge summary for the subsequent Turn 1.
        """
        sessions = self._load_sessions()
        key = str(chat_id)
        sess = sessions.get(key, {})
        old_conv = sess.get("conversation_id")
        old_tokens = sess.get("session_input_tokens", 0)
        old_turns = sess.get("turn_count", 0)

        sess["conversation_id"] = None
        sess["turn_count"] = 0
        sess["session_input_tokens"] = 0
        sess["session_output_tokens"] = 0
        sess["session_baseline_tokens"] = 0
        sess["last_turn_input_tokens"] = 0
        sess["last_active"] = datetime.now().isoformat()
        if bridge_summary:
            sess["context_bridge"] = bridge_summary.strip()

        sessions[key] = sess
        self._save_sessions(sessions)
        logger.info(
            f"Rotated session for chat_id={chat_id} (old_conv={old_conv}, prior_tokens={old_tokens}, prior_turns={old_turns}). "
            f"Context bridge stored."
        )
        return sess

    def pop_context_bridge(self, chat_id: int) -> Optional[str]:
        """Retrieve and clear pending context bridge summary for a session."""
        sessions = self._load_sessions()
        key = str(chat_id)
        if key in sessions and "context_bridge" in sessions[key]:
            bridge = sessions[key].pop("context_bridge")
            self._save_sessions(sessions)
            return bridge
        return None

    def get_total_token_usage(self) -> Dict[str, Any]:
        """Calculates aggregate token usage and turn metrics across all tracked sessions."""
        sessions = self._load_sessions()
        total_in = sum(s.get("total_input_tokens", 0) for s in sessions.values())
        total_out = sum(s.get("total_output_tokens", 0) for s in sessions.values())
        total_turns = sum(s.get("lifetime_turns", s.get("turn_count", 0)) for s in sessions.values())
        return {
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "total_tokens": total_in + total_out,
            "total_turns": total_turns,
            "session_count": len(sessions),
        }

    def get_session_token_usage(self, chat_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves token usage for a specific chat session.
        If chat_id is None or not found, falls back to the most recently active session.
        """
        sessions = self._load_sessions()
        if not sessions:
            return {
                "chat_id": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "turn_count": 0,
            }

        target_sess = None
        if chat_id is not None and str(chat_id) in sessions:
            target_sess = sessions[str(chat_id)]
        else:
            # Fallback to most recently active session
            try:
                target_sess = max(sessions.values(), key=lambda s: s.get("last_active", ""))
            except Exception:
                target_sess = next(iter(sessions.values()))

        if target_sess:
            in_tok = target_sess.get("session_input_tokens", 0)
            out_tok = target_sess.get("session_output_tokens", 0)
            return {
                "chat_id": target_sess.get("chat_id"),
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
                "turn_count": target_sess.get("turn_count", 0),
            }

        return {
            "chat_id": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "turn_count": 0,
        }
