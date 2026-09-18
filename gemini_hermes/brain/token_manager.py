import base64
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from gemini_hermes.config import config

logger = logging.getLogger("gemini-hermes.auth")


def get_default_token_path() -> Path:
    """Return the resolved path where the agy OAuth token session is stored."""
    if getattr(config, "agy_token_file", None):
        return Path(config.agy_token_file).expanduser().resolve()
    env_token = os.environ.get("AGY_TOKEN_FILE")
    if env_token:
        return Path(env_token).expanduser().resolve()
    return (Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token").resolve()


def validate_token_content(raw_content: str) -> Optional[Dict[str, Any]]:
    """Validate whether raw string content constitutes a valid agy token session."""
    raw_content = raw_content.strip()
    if not raw_content:
        return None

    # Try direct JSON parsing
    try:
        data = json.loads(raw_content)
        if isinstance(data, dict):
            # Check for standard OAuth structure
            if "token" in data or "access_token" in data or "refresh_token" in data or "auth_method" in data:
                return data
    except Exception:
        pass

    # Try base64 decoded JSON parsing
    try:
        decoded = base64.b64decode(raw_content).decode("utf-8")
        data = json.loads(decoded)
        if isinstance(data, dict):
            if "token" in data or "access_token" in data or "refresh_token" in data or "auth_method" in data:
                return data
    except Exception:
        pass

    return None


def has_valid_token_session() -> bool:
    """Check if an active, readable login token session file exists."""
    token_path = get_default_token_path()

    # 1. Primary path check
    if token_path.exists() and token_path.is_file():
        try:
            content = token_path.read_text(encoding="utf-8")
            if validate_token_content(content) is not None:
                return True
        except Exception as e:
            logger.debug(f"Error reading primary token path {token_path}: {e}")

    # 2. Fallback check: look for readable token in known alternative paths
    candidate_paths = [
        Path("/root/.gemini/antigravity-cli/antigravity-oauth-token"),
        Path.home() / ".config" / "antigravity-cli" / "antigravity-oauth-token",
    ]

    for alt_path in candidate_paths:
        if alt_path != token_path and alt_path.exists() and alt_path.is_file():
            try:
                content = alt_path.read_text(encoding="utf-8")
                valid_dict = validate_token_content(content)
                if valid_dict is not None:
                    # Auto-copy to current user's target token path
                    token_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    token_path.write_text(json.dumps(valid_dict, indent=2), encoding="utf-8")
                    token_path.chmod(0o600)
                    logger.info(f"Auto-imported active login token session from {alt_path} to {token_path}")
                    return True
            except Exception as e:
                logger.debug(f"Could not read alternative token path {alt_path}: {e}")

    return False


def save_token_session(raw_input: str, target_path: Optional[Path] = None) -> bool:
    """Save user-provided token session data to disk securely."""
    target_path = target_path or get_default_token_path()
    raw_input = raw_input.strip()

    # Handle file path input
    candidate_file = Path(raw_input).expanduser()
    if candidate_file.exists() and candidate_file.is_file():
        try:
            raw_input = candidate_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read token file {candidate_file}: {e}")
            return False

    valid_dict = validate_token_content(raw_input)
    if not valid_dict:
        return False

    try:
        target_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target_path.write_text(json.dumps(valid_dict, indent=2), encoding="utf-8")
        target_path.chmod(0o600)
        return True
    except Exception as e:
        logger.error(f"Failed to write token file to {target_path}: {e}")
        return False


def ensure_login_token_session(interactive: bool = True, agy_bin: Optional[str] = None) -> bool:
    """Ensure an active login token session is present. If missing, prompt user."""
    if has_valid_token_session():
        return True

    token_path = get_default_token_path()

    if not interactive or not sys.stdin.isatty():
        logger.warning(
            f"No active Antigravity CLI login token session found at {token_path} and terminal is non-interactive."
        )
        return False

    print("\n" + "=" * 62)
    print("      🔑 ANTIGRAVITY CLI (AGY) LOGIN SESSION REQUIRED")
    print("=" * 62)
    print("No active login token session was detected for the Antigravity CLI.")
    print(f"Target file: {token_path}\n")
    print("You can provide your login token session in any of these ways:")
    print("  1. Paste full JSON token session (e.g. {\"token\": ...})")
    print("  2. Enter the file path to an existing 'antigravity-oauth-token'")
    print("  3. Press [Enter] to launch interactive Google OAuth browser login")
    print("=" * 62)

    for attempt in range(1, 4):
        try:
            user_input = input("\nEnter token JSON, file path, or press [Enter] to login: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Setup aborted by user.")
            return False

        if not user_input or user_input.lower() == "login":
            bin_path = agy_bin or getattr(config, "agy_bin", None) or shutil.which("agy") or "agy"
            print(f"\n🚀 Launching Antigravity CLI ({bin_path}) interactive login...")
            try:
                subprocess.run([bin_path, "-p", "ping", "--effort", "low"], check=False)
            except Exception as e:
                print(f"❌ Failed to run {bin_path}: {e}")

            if has_valid_token_session():
                print(f"✅ Login token session successfully established at {token_path}!")
                return True
            else:
                print("⚠️ Authentication was not completed. Please try again.")
        else:
            if save_token_session(user_input, target_path=token_path):
                print(f"✅ Login token session successfully validated and saved to {token_path}!")
                return True
            else:
                print("❌ Invalid token session format. Input must be valid JSON or a readable file path.")

    print("❌ Failed to establish an active login token session after 3 attempts.")
    return False
