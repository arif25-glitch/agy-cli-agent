import argparse
import asyncio
import os
import sys
import logging
from pathlib import Path

from gemini_hermes.config import BASE_DIR, config
from gemini_hermes.brain.agy_forwarder import AgyForwarder
from gemini_hermes.brain.token_manager import (
    has_valid_token_session,
    ensure_login_token_session,
    get_default_token_path,
)
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.skills.manager import SkillManager
from gemini_hermes.gateway.telegram_bot import TelegramBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "gemini-hermes.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("gemini-hermes.cli")


async def run_setup():
    print("=" * 60)
    print("      GEMINI-HERMES INTERACTIVE SETUP WIZARD")
    print("=" * 60)
    print("This wizard will configure your Gemini-Hermes AI Agent,")
    print("powered by the Antigravity CLI (agy) and Telegram Gateway.\n")

    current_token = config.bot_token or ""
    current_users = ",".join(str(u) for u in config.allowed_users)

    token_prompt = f"Enter your Telegram Bot Token from @BotFather [{current_token[:8]}...]: " if current_token else "Enter your Telegram Bot Token from @BotFather: "
    token_input = input(token_prompt).strip()
    bot_token = token_input if token_input else current_token

    if not bot_token:
        print("❌ Error: Bot token cannot be empty.")
        return

    # Verify bot token with Telegram
    print("\n🔍 Validating Telegram Bot Token...")
    test_bot = TelegramBot(token=bot_token)
    info = await test_bot.get_me()
    if not info:
        print("❌ Error: Invalid Telegram Bot Token or cannot connect to Telegram API.")
        retry = input("Do you want to save anyway? (y/N): ").strip().lower()
        if retry != "y":
            return
    else:
        print(f"✅ Bot connected successfully! Username: @{info.get('username')} (Name: {info.get('first_name')})")

    users_prompt = f"Enter allowed Telegram User ID(s) (comma-separated) [{current_users}]: " if current_users else "Enter your Telegram User ID (e.g. from @userinfobot): "
    users_input = input(users_prompt).strip()
    allowed_users = users_input if users_input else current_users

    # Verify agy forwarder & login token session
    print("\n🔍 Checking Antigravity CLI (agy) login token session...")
    token_path = get_default_token_path()
    if not has_valid_token_session():
        print("⚠️ No active Antigravity CLI login token session found.")
        ensure_login_token_session(interactive=True, agy_bin=config.agy_bin)
    else:
        print(f"✅ Active Antigravity CLI login token session found: {token_path}")

    print("\n🔍 Verifying Antigravity CLI (agy) model engine...")
    forwarder = AgyForwarder()
    health = await forwarder.check_health()
    if health.get("ok"):
        print(f"✅ Antigravity CLI (agy) verified! Engine response: {health.get('sample_response')}")
    elif health.get("auth_required"):
        print(f"⚠️ {health.get('error')}")
        retry = input("Would you like to provide your login token session now? (Y/n): ").strip().lower()
        if retry != "n":
            if ensure_login_token_session(interactive=True, agy_bin=config.agy_bin):
                health = await forwarder.check_health()
                if health.get("ok"):
                    print(f"✅ Antigravity CLI (agy) verified! Engine response: {health.get('sample_response')}")
    else:
        print(f"⚠️ Warning: agy check issue: {health.get('error')}")

    # Write .env file
    env_content = f"""# Gemini-Hermes Configuration
TELEGRAM_BOT_TOKEN={bot_token}
TELEGRAM_ALLOWED_USERS={allowed_users}
AGY_BIN={config.agy_bin}
REASONING_EFFORT={config.reasoning_effort}
STREAM_UPDATES={str(config.stream_updates).lower()}
STREAM_EDIT_INTERVAL={config.stream_edit_interval}
WORKSPACE_DIR={config.workspace_dir}
DANGEROUSLY_SKIP_PERMISSIONS={str(config.dangerously_skip_permissions).lower()}
"""
    if config.typesafe_api_key:
        env_content += f"""TYPESAFE_API_KEY={config.typesafe_api_key}
TYPESAFE_MODEL={config.typesafe_model}
TYPESAFE_API_BASE={config.typesafe_api_base}
JEV_ENABLED={str(config.jev_enabled).lower()}
JEV_CONFIDENCE_THRESHOLD={config.jev_confidence_threshold}
"""
    env_file = BASE_DIR / ".env"
    env_file.write_text(env_content, encoding="utf-8")
    print(f"\n✅ Configuration written successfully to {env_file}!")
    print("\nYou can now start the agent by running:")
    print("  ./run.sh start")
    print("or:")
    print("  python3 -m gemini_hermes.cli start\n")


def run_config():
    print("=" * 60)
    print("      TYPESAFE AI (JEV) CONFIGURATION WIZARD")
    print("=" * 60)
    print("Configure your TypeSafe AI (Jev) System-One decision engine.")
    print("API keys can be retrieved from: https://console.typesafe.ai/keys\n")

    current_key = config.typesafe_api_key or ""
    current_model = config.typesafe_model or "jev-latest"
    current_base = config.typesafe_api_base or "https://api.typesafe.ai"
    current_enabled = "true" if config.jev_enabled else "false"
    current_threshold = str(config.jev_confidence_threshold)

    key_preview = f"[{current_key[:10]}...{current_key[-4:]}]" if len(current_key) > 14 else (f"[{current_key[:6]}...]" if current_key else "")

    key_prompt = f"Enter your TypeSafe API Key {key_preview}: " if key_preview else "Enter your TypeSafe API Key (from console.typesafe.ai): "
    key_input = input(key_prompt).strip()
    typesafe_api_key = key_input if key_input else current_key

    if not typesafe_api_key:
        print("\n⚠️ Note: No TypeSafe API key provided. Jev decision engine will remain disabled.")
        enable_prompt = f"Enable Jev AI decision engine? (y/N) [default: {current_enabled}]: "
    else:
        enable_prompt = f"Enable Jev AI decision engine? (Y/n) [default: y]: "

    enable_input = input(enable_prompt).strip().lower()
    if enable_input in ("y", "yes"):
        jev_enabled = "true"
    elif enable_input in ("n", "no"):
        jev_enabled = "false"
    else:
        jev_enabled = "true" if typesafe_api_key else current_enabled

    model_prompt = f"Enter TypeSafe model [{current_model}] (press Enter for default): "
    model_input = input(model_prompt).strip()
    typesafe_model = model_input if model_input else current_model

    threshold_prompt = f"Enter confidence threshold (0.0 - 1.0) [{current_threshold}] (press Enter for default): "
    threshold_input = input(threshold_prompt).strip()
    try:
        confidence_threshold = float(threshold_input) if threshold_input else float(current_threshold)
        if not (0.0 <= confidence_threshold <= 1.0):
            confidence_threshold = 0.85
    except ValueError:
        confidence_threshold = 0.85

    # Read existing .env file lines safely
    env_file = BASE_DIR / ".env"
    existing_lines = []
    existing_keys = set()
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    new_values = {
        "TYPESAFE_API_KEY": typesafe_api_key,
        "TYPESAFE_MODEL": typesafe_model,
        "TYPESAFE_API_BASE": current_base,
        "JEV_ENABLED": jev_enabled,
        "JEV_CONFIDENCE_THRESHOLD": str(confidence_threshold),
    }

    updated_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in new_values:
                updated_lines.append(f"{k}={new_values[k]}\n")
                existing_keys.add(k)
                continue
        updated_lines.append(line)

    for k, v in new_values.items():
        if k not in existing_keys:
            updated_lines.append(f"{k}={v}\n")

    env_file.write_text("".join(updated_lines), encoding="utf-8")
    print(f"\n✅ TypeSafe AI (Jev) configuration updated in {env_file}!")
    print("=" * 60)
    print("Configuration Summary:")
    print(f"  • TypeSafe API Key: {'Configured (' + typesafe_api_key[:10] + '...)' if typesafe_api_key else 'None'}")
    print(f"  • Jev Enabled: {jev_enabled}")
    print(f"  • Model: {typesafe_model}")
    print(f"  • Confidence Threshold: {confidence_threshold}")
    print("=" * 60 + "\n")


async def run_diagnostics():
    print("=" * 60)
    print("      GEMINI-HERMES SYSTEM DIAGNOSTICS")
    print("=" * 60)

    print("\n1. [BRAIN] Testing Antigravity CLI (agy) Proxy Forwarder...")
    token_path = get_default_token_path()
    if has_valid_token_session():
        print(f"   ✅ Active login token session verified: {token_path}")
    else:
        print(f"   ❌ No active login token session found at: {token_path}")
        print(f"      Run './run.sh setup' or './run.sh start' to authenticate.")

    forwarder = AgyForwarder()
    health = await forwarder.check_health()
    if health.get("ok"):
        print(f"   ✅ agy binary reachable: {forwarder.agy_bin}")
        print(f"   ✅ Test prompt succeeded. Result: '{health.get('sample_response')}'")
    elif health.get("auth_required"):
        print(f"   ❌ Authentication required: {health.get('error')}")
        print(f"      Run './run.sh setup' or './run.sh start' to provide your login token session.")
    else:
        print(f"   ❌ agy forwarder failed: {health.get('error')}")

    print("\n2. [MEMORY] Testing Persistent Memory Layer...")
    mem_store = MemoryStore()
    mem = mem_store.get_long_term_memory()
    usr = mem_store.get_user_profile()
    backlog = mem_store.get_backlog()
    refs = mem_store.get_references()
    print(f"   ✅ MEMORY.md loaded ({len(mem)} bytes)")
    print(f"   ✅ USER.md loaded ({len(usr)} bytes)")
    print(f"   ✅ BACKLOG.md loaded ({len(backlog)} bytes)")
    print(f"   ✅ REFERENCES.md loaded ({len(refs)} bytes)")

    print("\n3. [SKILLS] Testing Hermes Skills System (agentskills.io)...")
    skills_mgr = SkillManager()
    skills = skills_mgr.get_all_skills()
    print(f"   ✅ {len(skills)} skills detected:")
    for s in skills.values():
        print(f"      - {s.name} (v{s.version}): {s.description[:60]}")

    print("\n4. [GATEWAY] Testing Telegram Bot Gateway...")
    if not config.bot_token:
        print("   ⚠️ TELEGRAM_BOT_TOKEN not configured in .env.")
    else:
        bot = TelegramBot()
        info = await bot.get_me()
        if info:
            print(f"   ✅ Connected to Telegram as @{info.get('username')}")
            print(f"   ✅ Allowed User IDs: {config.allowed_users or 'ALL (Open)'}")
        else:
            print("   ❌ Failed to connect to Telegram. Check token or internet.")

    print("\n5. [OPTIONAL: TYPESAFE AI] Inspecting TypeSafe AI (Jev) Setup...")
    try:
        import typesafe_sdk
        print(f"   ℹ️ typesafe-sdk library detected (v{typesafe_sdk.__version__})")
        if config.typesafe_api_key and config.jev_enabled:
            masked = config.typesafe_api_key[:10] + "..." + config.typesafe_api_key[-4:] if len(config.typesafe_api_key) > 14 else config.typesafe_api_key[:6] + "..."
            print(f"   🟢 Enabled with key: {masked}")
            print(f"   Model: {config.typesafe_model}")
        elif config.typesafe_api_key:
            print("   ⚪ Configured but JEV_ENABLED=false (Dormant).")
        else:
            print("   ⚪ Optional: No API key set. (Gemini-Hermes runs normally)")
            print("      Run './run.sh config' if you want to configure TypeSafe AI.")
    except ImportError:
        print("   ⚪ Optional: typesafe-sdk is not installed. (Gemini-Hermes runs normally)")

    print("\nDiagnostics complete!\n")


PID_FILE = BASE_DIR / "gemini-hermes.pid"


def acquire_pid_lock() -> bool:
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != os.getpid():
                os.kill(old_pid, 0)
                print(f"❌ Error: Another instance of Gemini-Hermes is already running (PID {old_pid}).")
                logger.error(f"Duplicate instance rejected: PID {old_pid} is active.")
                return False
        except (OSError, ValueError):
            pass
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not write PID file: {e}")
    return True


def release_pid_lock():
    try:
        if PID_FILE.exists():
            current_pid = int(PID_FILE.read_text().strip())
            if current_pid == os.getpid():
                PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


async def start_bot():
    if not config.bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set.")
        print("Please run setup first: python3 -m gemini_hermes.cli setup")
        sys.exit(1)

    if not acquire_pid_lock():
        sys.exit(1)

    if not has_valid_token_session():
        if sys.stdin.isatty():
            print("⚠️ No active Antigravity CLI login token session found.")
            if not ensure_login_token_session(interactive=True, agy_bin=config.agy_bin):
                print("❌ Error: Valid login token session is required to start Gemini-Hermes.")
                release_pid_lock()
                sys.exit(1)
        else:
            token_path = get_default_token_path()
            print(f"❌ Error: No active Antigravity CLI login token session found at {token_path}.")
            print("Please run setup first: ./run.sh setup (or run ./run.sh start interactively).")
            release_pid_lock()
            sys.exit(1)

    try:
        bot = TelegramBot()
        await bot.run()
    finally:
        release_pid_lock()


def run_memory_cli(args):
    store = MemoryStore()
    action = getattr(args, "mem_action", "show") or "show"
    if action == "show":
        print("=" * 60)
        print("          GEMINI-HERMES PERSISTENT MEMORY")
        print("=" * 60)
        print(f"\n[Storage Directory]: {store.memory_dir}\n")
        print("--- USER.md ---")
        print(store.get_user_profile().strip())
        print("\n--- MEMORY.md ---")
        print(store.get_long_term_memory().strip())
        print("\n--- BACKLOG.md ---")
        print(store.get_backlog().strip())
        print("\n--- REFERENCES.md ---")
        print(store.get_references().strip())
    elif action == "add-memory":
        store.append_to_memory(args.note)
        print(f"✅ Appended to MEMORY.md: {args.note}")
    elif action == "add-user":
        store.update_user_profile(args.preference)
        print(f"✅ Appended to USER.md: {args.preference}")
    elif action == "add-task":
        store.append_to_backlog(args.task)
        print(f"✅ Appended to BACKLOG.md: {args.task}")
    elif action == "add-ref":
        store.append_to_references(args.title, args.url)
        print(f"✅ Appended to REFERENCES.md: {args.title} -> {args.url}")


def main():
    parser = argparse.ArgumentParser(description="Gemini-Hermes AI Agent Runner")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("start", help="Start the Gemini-Hermes Telegram Gateway")
    subparsers.add_parser("setup", help="Run interactive setup wizard")
    subparsers.add_parser("config", help="Configure TypeSafe AI (Jev) API key & decision settings")
    subparsers.add_parser("test", help="Run diagnostic health checks")

    mem_parser = subparsers.add_parser("memory", help="Inspect or update persistent memory files")
    mem_sub = mem_parser.add_subparsers(dest="mem_action", help="Memory action")
    mem_sub.add_parser("show", help="Show current persistent memory")
    add_mem = mem_sub.add_parser("add-memory", help="Append note to MEMORY.md")
    add_mem.add_argument("note", help="Note text to append")
    add_usr = mem_sub.add_parser("add-user", help="Append preference to USER.md")
    add_usr.add_argument("preference", help="User preference text to append")
    add_task = mem_sub.add_parser("add-task", help="Append task to BACKLOG.md")
    add_task.add_argument("task", help="Task description to append")
    add_ref = mem_sub.add_parser("add-ref", help="Append reference to REFERENCES.md")
    add_ref.add_argument("title", help="Title of reference")
    add_ref.add_argument("url", help="URL of reference")

    args = parser.parse_args()

    cmd = args.command or "start"

    if cmd == "config":
        run_config()
    elif cmd == "setup":
        asyncio.run(run_setup())
    elif cmd == "test":
        asyncio.run(run_diagnostics())
    elif cmd == "memory":
        run_memory_cli(args)
    elif cmd == "start":
        asyncio.run(start_bot())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

