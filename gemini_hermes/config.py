import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = DATA_DIR / "memory"
SESSIONS_DIR = DATA_DIR / "sessions"
SKILLS_DIR = DATA_DIR / "skills"
PROJECTS_DIR = DATA_DIR / "projects"
STATE_DIR = DATA_DIR / "state"


def _load_env_file(filepath: Path):
    if not filepath.exists():
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key not in os.environ:
                    os.environ[key] = val


_load_env_file(BASE_DIR / ".env")


class Config(BaseModel):
    app_version: str = "1.7.3"

    bot_token: str = Field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    allowed_users: List[int] = Field(
        default_factory=lambda: [
            int(uid.strip())
            for uid in os.environ.get("TELEGRAM_ALLOWED_USERS", "").split(",")
            if uid.strip().isdigit()
        ]
    )
    agy_bin: str = Field(default_factory=lambda: os.environ.get("AGY_BIN", "/root/.local/bin/agy"))
    agy_token_file: str = Field(default_factory=lambda: os.environ.get("AGY_TOKEN_FILE", ""))
    agy_model: str = Field(default_factory=lambda: os.environ.get("AGY_MODEL", "gemini-3.7-flash"))
    reasoning_effort: str = Field(default_factory=lambda: os.environ.get("REASONING_EFFORT", "medium"))
    stream_updates: bool = Field(
        default_factory=lambda: os.environ.get("STREAM_UPDATES", "true").lower() in ("true", "1", "yes")
    )
    stream_edit_interval: float = Field(
        default_factory=lambda: float(os.environ.get("STREAM_EDIT_INTERVAL", "1.2"))
    )
    workspace_dir: str = Field(default_factory=lambda: os.environ.get("WORKSPACE_DIR", str(BASE_DIR)))
    dangerously_skip_permissions: bool = Field(
        default_factory=lambda: os.environ.get("DANGEROUSLY_SKIP_PERMISSIONS", "true").lower() in ("true", "1", "yes")
    )
    forwarder_timeout: float = Field(
        default_factory=lambda: float(os.environ.get("FORWARDER_TIMEOUT", "900.0"))
    )
    inactivity_timeout: float = Field(
        default_factory=lambda: float(os.environ.get("INACTIVITY_TIMEOUT", "300.0"))
    )
    status_notify_interval: float = Field(
        default_factory=lambda: float(os.environ.get("STATUS_NOTIFY_INTERVAL", "1.2"))
    )
    differential_prompts: bool = Field(
        default_factory=lambda: os.environ.get("DIFFERENTIAL_PROMPTS", "true").lower() in ("true", "1", "yes")
    )
    context_rotation_threshold_tokens: int = Field(
        default_factory=lambda: int(os.environ.get("CONTEXT_ROTATION_THRESHOLD_TOKENS", "50000"))
    )
    context_rotation_growth_tokens: int = Field(
        default_factory=lambda: int(os.environ.get("CONTEXT_ROTATION_GROWTH_TOKENS", "40000"))
    )
    context_rotation_turn_limit: int = Field(
        default_factory=lambda: int(os.environ.get("CONTEXT_ROTATION_TURN_LIMIT", "15"))
    )
    context_rotation_min_turns: int = Field(
        default_factory=lambda: int(os.environ.get("CONTEXT_ROTATION_MIN_TURNS", "2"))
    )
    context_rotation_hard_max_tokens: int = Field(
        default_factory=lambda: int(os.environ.get("CONTEXT_ROTATION_HARD_MAX_TOKENS", "120000"))
    )
    context_rotation_growth_ratio: float = Field(
        default_factory=lambda: float(os.environ.get("CONTEXT_ROTATION_GROWTH_RATIO", "2.0"))
    )
    autonomous_memory_pruning: bool = Field(
        default_factory=lambda: os.environ.get("AUTONOMOUS_MEMORY_PRUNING", "true").lower() in ("true", "1", "yes")
    )
    memory_pruning_backlog_keep: int = Field(
        default_factory=lambda: int(os.environ.get("MEMORY_PRUNING_BACKLOG_KEEP", "5"))
    )
    memory_pruning_notes_keep: int = Field(
        default_factory=lambda: int(os.environ.get("MEMORY_PRUNING_NOTES_KEEP", "10"))
    )
    jev_memory_pruning: bool = Field(
        default_factory=lambda: os.environ.get("JEV_MEMORY_PRUNING", "true").lower() in ("true", "1", "yes")
    )
    typesafe_api_key: str = Field(
        default_factory=lambda: os.environ.get("TYPESAFE_API_KEY", os.environ.get("JEV_API_KEY", ""))
    )
    typesafe_api_base: str = Field(
        default_factory=lambda: os.environ.get("TYPESAFE_API_BASE", "https://api.typesafe.ai")
    )
    typesafe_model: str = Field(
        default_factory=lambda: os.environ.get("TYPESAFE_MODEL", "jev-latest")
    )
    jev_enabled: bool = Field(
        default_factory=lambda: os.environ.get("JEV_ENABLED", "false").lower() in ("true", "1", "yes")
    )
    jev_confidence_threshold: float = Field(
        default_factory=lambda: float(os.environ.get("JEV_CONFIDENCE_THRESHOLD", "0.85"))
    )
    jev_dynamic_effort: bool = Field(
        default_factory=lambda: os.environ.get("JEV_DYNAMIC_EFFORT", "false").lower() in ("true", "1", "yes")
    )
    jev_dynamic_model: bool = Field(
        default_factory=lambda: os.environ.get("JEV_DYNAMIC_MODEL", "false").lower() in ("true", "1", "yes")
    )
    jev_jit_skills: bool = Field(
        default_factory=lambda: os.environ.get("JEV_JIT_SKILLS", "false").lower() in ("true", "1", "yes")
    )
    jev_timeout: float = Field(
        default_factory=lambda: float(os.environ.get("JEV_TIMEOUT", "3.0"))
    )
    jev_fast_path: bool = Field(
        default_factory=lambda: os.environ.get("JEV_FAST_PATH", "true").lower() in ("true", "1", "yes")
    )

    @property
    def has_typesafe(self) -> bool:
        return bool(self.typesafe_api_key.strip() and self.jev_enabled)

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token.strip())


config = Config()
