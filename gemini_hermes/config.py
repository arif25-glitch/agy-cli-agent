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
    app_version: str = "1.4.1"

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

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token.strip())


config = Config()
