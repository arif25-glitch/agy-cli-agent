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
    env_file = BASE_DIR / ".env"
    env_file.write_text(env_content, encoding="utf-8")
    print(f"\n✅ Configuration written successfully to {env_file}!")
    print("\nYou can now start the agent by running:")
    print("  ./run.sh start")
    print("or:")
    print("  python3 -m gemini_hermes.cli start\n")


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
    print(f"   ✅ MEMORY.md loaded ({len(mem)} bytes)")
    print(f"   ✅ USER.md loaded ({len(usr)} bytes)")

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

    print("\nDiagnostics complete!\n")


async def start_bot():
    if not config.bot_token:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set.")
        print("Please run setup first: python3 -m gemini_hermes.cli setup")
        sys.exit(1)

    if not has_valid_token_session():
        if sys.stdin.isatty():
            print("⚠️ No active Antigravity CLI login token session found.")
            if not ensure_login_token_session(interactive=True, agy_bin=config.agy_bin):
                print("❌ Error: Valid login token session is required to start Gemini-Hermes.")
                sys.exit(1)
        else:
            token_path = get_default_token_path()
            print(f"❌ Error: No active Antigravity CLI login token session found at {token_path}.")
            print("Please run setup first: ./run.sh setup (or run ./run.sh start interactively).")
            sys.exit(1)

    bot = TelegramBot()
    await bot.run()


def main():
    parser = argparse.ArgumentParser(description="Gemini-Hermes AI Agent Runner")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("start", help="Start the Gemini-Hermes Telegram Gateway")
    subparsers.add_parser("setup", help="Run interactive setup wizard")
    subparsers.add_parser("test", help="Run diagnostic health checks")

    args = parser.parse_args()

    cmd = args.command or "start"

    if cmd == "setup":
        asyncio.run(run_setup())
    elif cmd == "test":
        asyncio.run(run_diagnostics())
    elif cmd == "start":
        asyncio.run(start_bot())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
