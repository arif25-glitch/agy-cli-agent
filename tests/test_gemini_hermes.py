import unittest
import tempfile
import shutil
import json
from pathlib import Path

from gemini_hermes.config import Config
from gemini_hermes.memory.store import MemoryStore
from gemini_hermes.skills.manager import SkillManager
from gemini_hermes.projects.manager import ProjectManager, Project
from gemini_hermes.persona.system_prompt import build_system_prompt
from gemini_hermes.brain.stream_parser import (
    parse_ndjson_line,
    TokenDelta,
    ThinkingDelta,
    ToolExecutionUpdate,
    ForwarderResult,
)
from gemini_hermes.gateway.formatter import (
    format_hermes_output,
    split_message,
    sanitize_streaming_markdown,
    humanize_error,
)


class TestConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = Config()
        self.assertEqual(cfg.app_version, "1.6.0")

        self.assertGreaterEqual(cfg.forwarder_timeout, 300.0)
        self.assertGreaterEqual(cfg.inactivity_timeout, 60.0)


class TestMemoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mem_dir = self.temp_dir / "memory"
        self.sess_dir = self.temp_dir / "sessions"
        self.store = MemoryStore(memory_dir=self.mem_dir, sessions_dir=self.sess_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization_all_domains(self):
        self.assertTrue((self.mem_dir / "MEMORY.md").exists())
        self.assertTrue((self.mem_dir / "USER.md").exists())
        self.assertTrue((self.mem_dir / "BACKLOG.md").exists())
        self.assertTrue((self.mem_dir / "REFERENCES.md").exists())
        self.assertTrue((self.sess_dir / "sessions.json").exists())

    def test_append_and_retrieve(self):
        self.store.append_to_memory("Test operational fact")
        mem = self.store.get_long_term_memory()
        self.assertIn("Test operational fact", mem)

    def test_update_user_profile(self):
        self.store.update_user_profile("User prefers TypeScript")
        usr = self.store.get_user_profile()
        self.assertIn("User prefers TypeScript", usr)

    def test_update_backlog(self):
        self.store.append_to_backlog("Implement OAuth flow")
        backlog = self.store.get_backlog()
        self.assertIn("Implement OAuth flow", backlog)

    def test_update_references(self):
        self.store.append_to_references("Google API Docs", "https://cloud.google.com")
        refs = self.store.get_references()
        self.assertIn("Google API Docs", refs)

    def test_session_lifecycle(self):
        chat_id = 999111
        sess = self.store.get_session(chat_id)
        self.assertEqual(sess["turn_count"], 0)
        self.assertIsNone(sess["conversation_id"])

        self.store.update_session(chat_id, conversation_id="conv-123", input_tokens=50, output_tokens=100)
        updated = self.store.get_session(chat_id)
        self.assertEqual(updated["conversation_id"], "conv-123")
        self.assertEqual(updated["turn_count"], 1)
        self.assertEqual(updated["total_input_tokens"], 50)
        self.assertEqual(updated["total_output_tokens"], 100)

        self.store.reset_session(chat_id)
        reset_sess = self.store.get_session(chat_id)
        self.assertEqual(reset_sess["turn_count"], 0)
        self.assertIsNone(reset_sess["conversation_id"])

    def test_prebuilt_templates_standards(self):
        usr = self.store.get_user_profile()
        self.assertIn("Slow is Smooth, Smooth is Fast", usr)
        self.assertIn("Testing & Verification Standard", usr)
        self.assertIn("Step-by-Step Skill Creation Protocol", usr)
        self.assertIn("NEVER LIE", usr)

        mem = self.store.get_long_term_memory()
        self.assertIn("Operational Standards", mem)
        self.assertIn("Memory Scaling & Retention Protocol", mem)
        self.assertIn("NEVER LIE", mem)





class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.custom_skills_dir = self.temp_dir / "custom_skills"
        self.manager = SkillManager(custom_skills_dir=self.custom_skills_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_builtin_skills_loading(self):
        skills = self.manager.get_all_skills()
        self.assertEqual(len(skills), 9)
        self.assertNotIn("manager_delegation", skills)
        self.assertIn("multi_step_researcher", skills)
        self.assertIn("auto_debugger", skills)
        self.assertIn("api_tester", skills)
        self.assertIn("system_monitor", skills)
        self.assertIn("task_scheduler", skills)
        self.assertIn("task_watcher", skills)
        self.assertIn("memory_keeper", skills)
        self.assertIn("shell_execution", skills)
        self.assertIn("skill_creator", skills)

    def test_create_custom_skill(self):
        skill = self.manager.create_or_update_skill(
            name="test_skill",
            description="A test skill procedure",
            instructions="Execute test steps cleanly.",
            tags=["test", "unit"],
        )
        self.assertEqual(skill.name, "test_skill")
        self.assertTrue(skill.file_path.exists())

        loaded = self.manager.get_skill("test_skill")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.description, "A test skill procedure")


class TestProjectManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = ProjectManager(projects_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bookmark_and_task_lifecycle(self):
        p = self.manager.bookmark_project(
            name="Demo Project",
            path="/tmp/demo",
            description="A demo project",
            tech_stack="Python, FastAPI",
        )
        self.assertEqual(p.id, "demo-project")

        self.manager.add_task("demo-project", "Write tests")
        p = self.manager.get_project("demo-project")
        self.assertIn("Write tests", p.active_tasks)

        self.manager.complete_task("demo-project", "Write tests")
        p = self.manager.get_project("demo-project")
        self.assertNotIn("Write tests", p.active_tasks)


class TestSystemPrompt(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mem_dir = self.temp_dir / "memory"
        self.sess_dir = self.temp_dir / "sessions"
        self.custom_skills_dir = self.temp_dir / "custom_skills"
        self.proj_dir = self.temp_dir / "projects"

        self.mem_store = MemoryStore(memory_dir=self.mem_dir, sessions_dir=self.sess_dir)
        self.skill_mgr = SkillManager(custom_skills_dir=self.custom_skills_dir)
        self.proj_mgr = ProjectManager(projects_dir=self.proj_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prompt_content(self):
        prompt = build_system_prompt(
            self.mem_store,
            self.skill_mgr,
            project_manager=self.proj_mgr,
            current_chat_id=12345,
        )
        self.assertIn("Direct Solo Execution", prompt)
        self.assertIn("Available Skills (Modular Procedures)", prompt)
        self.assertIn("Telegram Chat ID: 12345", prompt)
        self.assertIn("Deliberate Cadence & Rigorous Dual Verification", prompt)
        self.assertIn("Slow is Smooth, Smooth is Fast", prompt)
        self.assertIn("NEVER LIE", prompt)
        self.assertIn("Storage Location", prompt)
        self.assertNotIn("manager_delegation", prompt.lower())



class TestMemoryCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.mem_dir = self.temp_dir / "memory"
        self.sess_dir = self.temp_dir / "sessions"
        self.store = MemoryStore(memory_dir=self.mem_dir, sessions_dir=self.sess_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cli_actions(self):
        from unittest.mock import patch
        from gemini_hermes.cli import run_memory_cli

        class DummyArgs:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        with patch("gemini_hermes.cli.MemoryStore", return_value=self.store):
            # Test add-memory
            run_memory_cli(DummyArgs(mem_action="add-memory", note="CLI test note"))
            self.assertIn("CLI test note", self.store.get_long_term_memory())

            # Test add-user
            run_memory_cli(DummyArgs(mem_action="add-user", preference="CLI test user preference"))
            self.assertIn("CLI test user preference", self.store.get_user_profile())

            # Test add-task
            run_memory_cli(DummyArgs(mem_action="add-task", task="CLI test task"))
            self.assertIn("CLI test task", self.store.get_backlog())

            # Test add-ref
            run_memory_cli(DummyArgs(mem_action="add-ref", title="CLI Ref", url="https://test.com"))
            self.assertIn("CLI Ref", self.store.get_references())

            # Test show (should not raise)
            run_memory_cli(DummyArgs(mem_action="show"))



class TestStreamParser(unittest.TestCase):
    def test_token_delta(self):
        line = {"event": "step_update", "step_update": {"text_delta": "Hello world"}}
        event = parse_ndjson_line(line)
        self.assertIsInstance(event, TokenDelta)
        self.assertEqual(event.text, "Hello world")

    def test_thinking_delta(self):
        line = {"event": "step_update", "step_update": {"thinking_delta": "Analyzing requirements..."}}
        event = parse_ndjson_line(line)
        self.assertIsInstance(event, ThinkingDelta)
        self.assertEqual(event.thought, "Analyzing requirements...")

    def test_tool_execution(self):
        line = {
            "event": "step_update",
            "step_update": {
                "tool_name": "write_to_file",
                "tool_info": {"parameters": {"TargetFile": "/app/main.py"}},
            },
        }
        event = parse_ndjson_line(line)
        self.assertIsInstance(event, ToolExecutionUpdate)
        self.assertEqual(event.tool_name, "write_to_file")
        self.assertIn('creating a "main.py" file', event.action)

    def test_result_event(self):
        line = {
            "event": "result",
            "result": {
                "conversation_id": "conv-test",
                "status": "SUCCESS",
                "response": "Done.",
                "usage": {"input_tokens": 100, "output_tokens": 200, "thinking_tokens": 50},
                "duration_seconds": 1.5,
            },
        }
        event = parse_ndjson_line(line)
        self.assertIsInstance(event, ForwarderResult)
        self.assertEqual(event.conversation_id, "conv-test")
        self.assertEqual(event.status, "SUCCESS")
        self.assertEqual(event.input_tokens, 100)


class TestFormatter(unittest.TestCase):
    def test_format_headers_and_lists(self):
        raw = "### Architecture\n\n* First item\n* Second item\n\n**Bold Text**"
        formatted = format_hermes_output(raw)
        self.assertNotIn("###", formatted)
        self.assertIn("*Architecture*", formatted)
        self.assertIn("• First item", formatted)
        self.assertIn("*Bold Text*", formatted)

    def test_code_block_protection(self):
        raw = "Here is code:\n```python\n### Not a header\n**not bold**\n```"
        formatted = format_hermes_output(raw)
        self.assertIn("### Not a header", formatted)
        self.assertIn("**not bold**", formatted)

    def test_split_message(self):
        long_text = "A" * 5000
        chunks = split_message(long_text, max_length=2000)
        self.assertEqual(len(chunks), 3)
        self.assertEqual("".join(chunks), long_text)

    def test_humanize_error(self):
        err = humanize_error("Timeout occurred after 300 seconds", last_action="running tests")
        self.assertIn("Execution Timed Out", err)
        self.assertIn("running tests", err)


class TestZeroStatusSpam(unittest.IsolatedAsyncioTestCase):
    """
    Dual verification test suite for Zero Status Spam (In-Place Status Editing).
    Validates both Positive (single message edited across tool transitions)
    and Negative (graceful fallback to send_message when editMessageText fails).
    """

    async def test_positive_in_place_status_flow(self):
        from unittest.mock import AsyncMock, patch, MagicMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=101)
        bot.edit_message_text = AsyncMock(return_value=True)

        events = [
            ToolExecutionUpdate(tool_name="view_file", action="reading config.json file"),
            ToolExecutionUpdate(tool_name="run_command", action='running "npm run build"'),
            ForwarderResult(
                conversation_id="conv-123",
                status="SUCCESS",
                response="Build completed successfully!",
            ),
        ]

        async def fake_stream(*args, **kwargs):
            for ev in events:
                yield ev

        bot.forwarder.forward_stream = fake_stream
        bot.send_chat_action = AsyncMock()

        await bot.handle_chat_message(chat_id=888, user_id=999, user_text="build project")

        # In positive path:
        # 1 initial placeholder send_message
        self.assertEqual(bot.send_message.call_count, 1)
        # Multiple tool transitions and final result must all edit message 101 in-place
        self.assertGreaterEqual(bot.edit_message_text.call_count, 2)
        for call_args in bot.edit_message_text.call_args_list:
            # First two positional args: chat_id=888, message_id=101
            self.assertEqual(call_args[0][0], 888)
            self.assertEqual(call_args[0][1], 101)

    async def test_negative_fallback_when_edit_fails(self):
        from unittest.mock import AsyncMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        # Placeholder created successfully
        bot.send_message = AsyncMock(side_effect=[202, 203])
        # editMessageText fails (e.g. user deleted message or API rejected)
        bot.edit_message_text = AsyncMock(return_value=False)

        events = [
            ToolExecutionUpdate(tool_name="run_command", action="executing test"),
            ForwarderResult(
                conversation_id="conv-123",
                status="SUCCESS",
                response="Final output with edit failure fallback.",
            ),
        ]

        async def fake_stream(*args, **kwargs):
            for ev in events:
                yield ev

        bot.forwarder.forward_stream = fake_stream
        bot.send_chat_action = AsyncMock()

        await bot.handle_chat_message(chat_id=888, user_id=999, user_text="trigger failure fallback")

        # Negative path resilience:
        # When edit_message_text returns False, bot must fall back to send_message
        # ensuring the user is never left without the final answer
        self.assertEqual(bot.send_message.call_count, 2)
        sent_final_text = bot.send_message.call_args_list[-1][0][1]
        self.assertIn("Final output with edit failure fallback.", sent_final_text)


class TestBtwDualMode(unittest.IsolatedAsyncioTestCase):
    """
    Dual Verification Test Suite for /btw Dual-Mode (Live Telemetry, Ephemeral Q&A, and Task Queue).
    Tests Intent Classification, Positive Paths (Live telemetry, Ephemeral Q&A, Queued task),
    and Negative Paths (Query failure fallback, empty query, edit fallback).
    """

    def test_classify_btw_intent(self):
        from gemini_hermes.gateway.telegram_bot import TelegramBot
        bot = TelegramBot(token="12345:fake_token_for_test")

        # Live status
        intent, q = bot._classify_btw_intent("what are you doing now?")
        self.assertEqual(intent, "live_status")
        intent, q = bot._classify_btw_intent("where are you at?")
        self.assertEqual(intent, "live_status")
        intent, q = bot._classify_btw_intent("sedang apa")
        self.assertEqual(intent, "live_status")

        # Questions (general knowledge, absurd, technical)
        intent, q = bot._classify_btw_intent("why is the sky blue?")
        self.assertEqual(intent, "question")
        intent, q = bot._classify_btw_intent("who won the 1998 world cup?")
        self.assertEqual(intent, "question")
        intent, q = bot._classify_btw_intent("explain closures in javascript")
        self.assertEqual(intent, "question")
        intent, q = bot._classify_btw_intent("what is the port for PostgreSQL?")
        self.assertEqual(intent, "question")

        # Explicit Question Prefixes
        intent, q = bot._classify_btw_intent("? can dogs eat cheese")
        self.assertEqual(intent, "question")
        self.assertEqual(q, "can dogs eat cheese")
        intent, q = bot._classify_btw_intent("q: what is 42")
        self.assertEqual(intent, "question")
        self.assertEqual(q, "what is 42")

        # Tasks / Directives to queue
        intent, q = bot._classify_btw_intent("after this, write a comprehensive test suite")
        self.assertEqual(intent, "task")
        intent, q = bot._classify_btw_intent("run npm test")
        self.assertEqual(intent, "task")
        intent, q = bot._classify_btw_intent("build and deploy to vercel")
        self.assertEqual(intent, "task")

        # Explicit Task Prefixes
        intent, q = bot._classify_btw_intent("queue: refactor database models")
        self.assertEqual(intent, "task")
        self.assertEqual(q, "refactor database models")
        intent, q = bot._classify_btw_intent("task: add docstrings to telegram_bot.py")
        self.assertEqual(intent, "task")
        self.assertEqual(q, "add docstrings to telegram_bot.py")

    async def test_positive_live_telemetry_inquiry(self):
        from unittest.mock import AsyncMock, MagicMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=301)

        # Simulate active running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bot._active_tasks[777] = mock_task
        bot._active_task_info[777] = {
            "text": "Scaffold Next.js application with Tailwind",
            "last_action": "running 'npx create-next-app'",
            "start_time": 1000.0,
            "user_id": 999,
        }

        await bot.handle_btw(chat_id=777, user_id=999, text="what are you doing now?")

        bot.send_message.assert_called_once()
        msg_text = bot.send_message.call_args[0][1]
        self.assertIn("Side Query (Live Task Telemetry)", msg_text)
        self.assertIn("Scaffold Next.js", msg_text)
        self.assertIn("running 'npx create-next-app'", msg_text)
        self.assertIn("Actively executing in background", msg_text)
        # Task should remain active
        self.assertIn(777, bot._active_tasks)

    async def test_positive_ephemeral_side_question(self):
        from unittest.mock import AsyncMock, MagicMock
        import asyncio
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=401)
        bot.edit_message_text = AsyncMock(return_value=True)
        bot.forwarder.ask_quick = AsyncMock(return_value="The sky is blue due to Rayleigh scattering.")

        # Simulate active running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bot._active_tasks[777] = mock_task
        bot._active_task_info[777] = {
            "text": "Building production Docker image",
            "last_action": "docker build -t app:latest .",
            "start_time": 1000.0,
            "user_id": 999,
        }

        await bot.handle_btw(chat_id=777, user_id=999, text="why is the sky blue?")

        # Let the background ephemeral task finish
        await asyncio.sleep(0.05)

        bot.forwarder.ask_quick.assert_called_once()
        prompt_passed = bot.forwarder.ask_quick.call_args[0][0]
        self.assertIn("why is the sky blue?", prompt_passed)
        self.assertIn("Building production Docker image", prompt_passed)

        # Verified placeholder sent, then edited with answer
        bot.send_message.assert_called_once()
        bot.edit_message_text.assert_called_once()
        final_text = bot.edit_message_text.call_args[0][2]
        self.assertIn("Side Answer (/btw)", final_text)
        self.assertIn("Rayleigh scattering", final_text)
        self.assertIn("Primary task continues running in background", final_text)

        # Primary task is intact and no items in task queue
        self.assertEqual(len(bot._task_queues.get(777, [])), 0)
        self.assertIn(777, bot._active_tasks)

    async def test_positive_task_queueing(self):
        from unittest.mock import AsyncMock, MagicMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=501)

        # Simulate active running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bot._active_tasks[777] = mock_task
        bot._active_task_info[777] = {
            "text": "Compiling Rust binary",
            "last_action": "cargo build --release",
            "start_time": 1000.0,
            "user_id": 999,
        }

        await bot.handle_btw(chat_id=777, user_id=999, text="after this, write comprehensive unit tests")

        # Queued in _task_queues
        self.assertIn(777, bot._task_queues)
        self.assertEqual(len(bot._task_queues[777]), 1)
        self.assertEqual(bot._task_queues[777][0], "after this, write comprehensive unit tests")

        bot.send_message.assert_called_once()
        msg_text = bot.send_message.call_args[0][1]
        self.assertIn("Queued Task for Later Execution (/btw)", msg_text)
        self.assertIn("#1", msg_text)

    async def test_negative_ephemeral_query_failure_fallback(self):
        from unittest.mock import AsyncMock, MagicMock
        import asyncio
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=601)
        bot.edit_message_text = AsyncMock(return_value=True)
        # Mock engine failure / timeout returning empty string
        bot.forwarder.ask_quick = AsyncMock(return_value="")

        # Simulate active running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bot._active_tasks[777] = mock_task
        bot._active_task_info[777] = {
            "text": "Running migration scripts",
            "last_action": "alembic upgrade head",
            "start_time": 1000.0,
            "user_id": 999,
        }

        await bot.handle_btw(chat_id=777, user_id=999, text="who won the 1998 world cup?")
        await asyncio.sleep(0.05)

        # Fallback message sent, gracefully explaining engine timeout
        bot.edit_message_text.assert_called_once()
        final_text = bot.edit_message_text.call_args[0][2]
        self.assertIn("Unable to retrieve side answer at this moment", final_text)
        self.assertIn("The primary task continues running unaffected", final_text)
        # Active task was never interrupted
        self.assertIn(777, bot._active_tasks)

    async def test_negative_empty_query_help(self):
        from unittest.mock import AsyncMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=701)

        await bot.handle_btw(chat_id=777, user_id=999, text="   ")
        bot.send_message.assert_called_once()
        msg_text = bot.send_message.call_args[0][1]
        self.assertIn("Usage of `/btw`", msg_text)


class TestSteerCommand(unittest.IsolatedAsyncioTestCase):
    """
    Dual Verification Test Suite for /steer command.
    Covers Positive Paths (Mid-flight task interception, Idle steering) and
    Negative Paths (Empty directive guide, Steered cancellation race condition suppression).
    """

    async def test_positive_midflight_steering_interception(self):
        from unittest.mock import AsyncMock, MagicMock
        import asyncio
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=801)
        bot.handle_chat_message = AsyncMock()

        # Simulate active running task
        mock_task = MagicMock()
        mock_task.done.return_value = False
        bot._active_tasks[555] = mock_task
        bot._active_task_info[555] = {
            "text": "Generate database migrations with alembic",
            "last_action": "writing migration script 001_init.py",
            "start_time": 1000.0,
            "user_id": 999,
        }

        await bot.handle_steer(chat_id=555, user_id=999, text="Stop alembic, use Prisma schema migrations instead")

        # 1. Old task must be cancelled
        mock_task.cancel.assert_called_once()

        # 2. Confirmation message sent
        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args[0][1]
        self.assertIn("Course Correction (Steering Applied)", msg)
        self.assertIn("writing migration script 001_init.py", msg)
        self.assertIn("Stop alembic, use Prisma schema migrations instead", msg)

        # 3. New steered task started with structured steering directive
        bot.handle_chat_message.assert_called_once()
        steer_prompt = bot.handle_chat_message.call_args[0][2]
        self.assertIn("[USER STEERING DIRECTIVE]", steer_prompt)
        self.assertIn("Previous Objective: Generate database migrations with alembic", steer_prompt)
        self.assertIn("Status Before Steering: writing migration script 001_init.py", steer_prompt)
        self.assertIn("Stop alembic, use Prisma schema migrations instead", steer_prompt)

    async def test_positive_idle_steering(self):
        from unittest.mock import AsyncMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=802)
        bot.handle_chat_message = AsyncMock()

        # No active task running
        await bot.handle_steer(chat_id=555, user_id=999, text="Refactor the authentication module to JWT")

        # 1. Confirmation message sent
        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args[0][1]
        self.assertIn("Steering Directive Applied", msg)
        self.assertIn("Refactor the authentication module to JWT", msg)

        # 2. Steered task launched directly
        bot.handle_chat_message.assert_called_once()
        steer_prompt = bot.handle_chat_message.call_args[0][2]
        self.assertIn("[USER STEERING DIRECTIVE]", steer_prompt)
        self.assertIn("Refactor the authentication module to JWT", steer_prompt)

    async def test_negative_empty_directive_guidance(self):
        from unittest.mock import AsyncMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=803)
        bot.handle_chat_message = AsyncMock()

        await bot.handle_steer(chat_id=555, user_id=999, text="   ")

        # Should send usage guide and NOT launch any task
        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args[0][1]
        self.assertIn("Usage of `/steer`", msg)
        self.assertIn("Mid-Flight Intervention", msg)
        self.assertIn("Direct Guidance", msg)
        bot.handle_chat_message.assert_not_called()

    async def test_negative_steered_cancellation_suppresses_generic_cancel_and_queue_race(self):
        from unittest.mock import AsyncMock
        import asyncio
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.send_message = AsyncMock(return_value=804)
        bot.edit_message_text = AsyncMock(return_value=True)

        # Simulate a stream that blocks until cancelled
        async def hanging_stream(prompt, conv_id=None):
            await asyncio.sleep(10.0)
            yield None

        bot.forwarder.forward_stream = hanging_stream
        bot.send_chat_action = AsyncMock()

        # Pre-queue a task in _task_queues
        bot._task_queues[555] = ["queued task 1"]

        # Run task in background
        task = asyncio.create_task(bot.handle_chat_message(555, 999, "Long running build"))
        await asyncio.sleep(0.05)

        # Mark as steered before cancelling
        bot._active_task_info[555]["steered"] = True
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify:
        # 1. No generic "Operation Cancelled" was sent
        for call in bot.send_message.call_args_list:
            text = call[0][1]
            self.assertNotIn("🛑 *Operation Cancelled.*", text)

        # 2. Queued task was NOT popped or run prematurely
        self.assertEqual(len(bot._task_queues[555]), 1)
        self.assertEqual(bot._task_queues[555][0], "queued task 1")


class TestTieredQualityMemory(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.memory_dir = self.test_dir / "memory"
        self.sessions_dir = self.test_dir / "sessions"
        self.store = MemoryStore(memory_dir=self.memory_dir, sessions_dir=self.sessions_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_positive_hot_backlog_filtering(self):
        """Positive Path: Verify hot backlog keeps all active tasks and only max_recent_completed completed tasks."""
        backlog_content = (
            "# Active Task Backlog\n\n"
            "## Active Tasks\n"
            "- [x] Task 1: Setup repo\n"
            "- [x] Task 2: Install dependencies\n"
            "- [x] Task 3: Setup database\n"
            "- [x] Task 4: Add user model\n"
            "- [x] Task 5: Add auth routes\n"
            "- [x] Task 6: Add rate limiting\n"
            "- [ ] Task 7: Implement Stripe billing\n"
            "- [ ] Task 8: Deploy to production\n\n"
            "## Operational Notes & Inquiries\n"
            "- Database migration pending.\n"
        )
        self.store.backlog_file.write_text(backlog_content, encoding="utf-8")

        # Get hot backlog with max 3 completed tasks
        hot = self.store.get_hot_backlog(max_recent_completed=3)

        # Active tasks MUST both be present
        self.assertIn("Task 7: Implement Stripe billing", hot)
        self.assertIn("Task 8: Deploy to production", hot)

        # The last 3 completed tasks MUST be present
        self.assertIn("Task 4: Add user model", hot)
        self.assertIn("Task 5: Add auth routes", hot)
        self.assertIn("Task 6: Add rate limiting", hot)

        # The older completed tasks (1, 2, 3) must NOT be in hot backlog
        self.assertNotIn("Task 1: Setup repo", hot)
        self.assertNotIn("Task 2: Install dependencies", hot)
        self.assertNotIn("Task 3: Setup database", hot)

        # Archival note indicator must be present
        self.assertIn("3 older completed tasks archived", hot)

    def test_positive_archive_completed_tasks_multiline(self):
        """Positive Path: Archive completed tasks with nested multi-line sub-bullets to BACKLOG_ARCHIVE.md."""
        backlog_content = (
            "# Active Task Backlog\n\n"
            "## Active Tasks\n"
            "- [x] Task Alpha: Complex architecture\n"
            "  * Detail 1: Setup microservices\n"
            "  * Detail 2: Verified latency under 20ms\n"
            "- [x] Task Beta: Redis caching\n"
            "  * Cache hit ratio 99%\n"
            "- [x] Task Gamma: Docker build\n"
            "- [x] Task Delta: K8s manifests\n"
            "- [x] Task Epsilon: Prometheus metrics\n"
            "- [x] Task Zeta: Grafana dashboards\n"
            "- [ ] Task Eta: Alertmanager webhooks\n\n"
            "## Operational Notes & Inquiries\n"
            "- Operational facts here.\n"
        )
        self.store.backlog_file.write_text(backlog_content, encoding="utf-8")

        # Keep recent 2 completed tasks, archive older 4
        result = self.store.archive_completed_backlog(keep_recent=2)
        self.assertEqual(result["status"], "archived")
        self.assertEqual(result["archived_count"], 4)
        self.assertEqual(result["retained_count"], 2)
        self.assertEqual(result["active_count"], 1)

        # Verify BACKLOG_ARCHIVE.md on disk
        archive_text = self.store.get_archived_backlog()
        self.assertIn("Task Alpha: Complex architecture", archive_text)
        self.assertIn("Detail 1: Setup microservices", archive_text)
        self.assertIn("Detail 2: Verified latency under 20ms", archive_text)
        self.assertIn("Task Beta: Redis caching", archive_text)
        self.assertIn("Cache hit ratio 99%", archive_text)
        self.assertIn("Task Gamma: Docker build", archive_text)
        self.assertIn("Task Delta: K8s manifests", archive_text)

        # Verify BACKLOG.md retains only recent 2 + active task
        new_backlog = self.store.get_backlog()
        self.assertNotIn("Task Alpha", new_backlog)
        self.assertNotIn("Task Beta", new_backlog)
        self.assertNotIn("Task Gamma", new_backlog)
        self.assertNotIn("Task Delta", new_backlog)
        self.assertIn("Task Epsilon: Prometheus metrics", new_backlog)
        self.assertIn("Task Zeta: Grafana dashboards", new_backlog)
        self.assertIn("Task Eta: Alertmanager webhooks", new_backlog)

    def test_positive_memory_stats_metrics(self):
        """Positive Path: Verify get_memory_stats returns accurate token and file metrics."""
        stats = self.store.get_memory_stats()
        self.assertIn("hot_tokens", stats)
        self.assertIn("total_tokens", stats)
        self.assertIn("archived_tokens", stats)
        self.assertIn("files", stats)
        self.assertIn("MEMORY.md", stats["files"])
        self.assertIn("BACKLOG.md (hot)", stats["files"])

    async def test_positive_compact_command_flow(self):
        """Positive Path: Verify Telegram /compact command triggers archiving and sends telemetry summary."""
        from unittest.mock import AsyncMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        bot = TelegramBot(token="12345:fake_token_for_test")
        bot.memory_store = self.store
        bot.send_message = AsyncMock(return_value=901)

        backlog_content = (
            "# Active Task Backlog\n\n"
            "## Active Tasks\n"
            "- [x] 1. One\n- [x] 2. Two\n- [x] 3. Three\n- [x] 4. Four\n- [x] 5. Five\n- [x] 6. Six\n- [ ] 7. Seven\n"
        )
        self.store.backlog_file.write_text(backlog_content, encoding="utf-8")

        await bot.handle_compact(chat_id=777)

        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args[0][1]
        self.assertIn("Memory Compaction & Tiering Complete", msg)
        self.assertIn("Archived Completed Tasks", msg)
        self.assertIn("Recent Completed in Hot Context", msg)

    def test_negative_no_op_when_under_threshold(self):
        """Negative Path: Compaction is a clean no-op when completed tasks <= keep_recent."""
        backlog_content = (
            "# Active Task Backlog\n\n"
            "## Active Tasks\n"
            "- [x] Task 1\n"
            "- [x] Task 2\n"
            "- [ ] Task 3\n"
        )
        self.store.backlog_file.write_text(backlog_content, encoding="utf-8")
        orig_content = self.store.backlog_file.read_text(encoding="utf-8")

        result = self.store.archive_completed_backlog(keep_recent=5)
        self.assertEqual(result["status"], "noop")
        self.assertEqual(result["archived_count"], 0)
        self.assertEqual(self.store.backlog_file.read_text(encoding="utf-8"), orig_content)
        self.assertFalse(self.store.backlog_archive_file.exists())

    def test_negative_empty_or_malformed_backlog_graceful(self):
        """Negative Path: Empty or malformed backlog does not crash or lose content."""
        self.store.backlog_file.write_text("", encoding="utf-8")
        result = self.store.archive_completed_backlog(keep_recent=5)
        self.assertEqual(result["status"], "empty")
        self.assertEqual(result["archived_count"], 0)

        # Malformed markdown without sections
        self.store.backlog_file.write_text("random notes without headers\nsome unformatted lines", encoding="utf-8")
        hot = self.store.get_hot_backlog()
        self.assertIn("random notes without headers", hot)


class TestAutoChatQueue(unittest.IsolatedAsyncioTestCase):
    """
    Dual Verification Test Suite for Automatic Chat Queueing ("Zero Message Drop").
    Tests Positive Paths (Single chat, multiple sequential chats, image attachments) and
    Expanded Negative Paths (Capacity overflow, whitespace rejection, task crash recovery,
    cancel purge, reset purge, steer queue preservation).
    """

    def setUp(self):
        from unittest.mock import AsyncMock, MagicMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        self.bot = TelegramBot(token="12345:fake_token_for_test")
        self.bot.is_user_allowed = MagicMock(return_value=True)
        self.bot.send_message = AsyncMock(return_value=1001)
        self.bot.send_chat_action = AsyncMock(return_value=True)
        self.bot.edit_message_text = AsyncMock(return_value=True)
        self.bot.handle_chat_message = AsyncMock()

    async def test_positive_auto_queue_single_chat(self):
        """Positive Path 1: Non-slash message sent during active task is enqueued with position #1."""
        from unittest.mock import MagicMock

        chat_id = 1001
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task
        self.bot._active_task_info[chat_id] = {"text": "Primary task", "last_action": "running", "user_id": user_id}

        update = {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "text": "how's your day",
            },
        }

        await self.bot.process_update(update)

        # Verified queued
        self.assertIn(chat_id, self.bot._task_queues)
        self.assertEqual(len(self.bot._task_queues[chat_id]), 1)
        self.assertEqual(self.bot._task_queues[chat_id][0], "how's your day")

        # Verified confirmation dispatched
        self.bot.send_message.assert_called_once()
        sent_text = self.bot.send_message.call_args[0][1]
        self.assertIn("Message Queued", sent_text)
        self.assertIn("#1", sent_text)
        self.assertIn("how's your day", sent_text)

    async def test_positive_auto_queue_multiple_chats_sequential(self):
        """Positive Path 2: Multiple non-slash messages are queued in FIFO order and displayed in /queue."""
        from unittest.mock import MagicMock

        chat_id = 1002
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task
        self.bot._active_task_info[chat_id] = {"text": "Heavy build", "last_action": "compiling", "user_id": user_id}

        for i, text in enumerate(["first follow-up", "second follow-up", "third follow-up"], 1):
            update = {
                "update_id": i,
                "message": {
                    "message_id": 20 + i,
                    "chat": {"id": chat_id},
                    "from": {"id": user_id},
                    "text": text,
                },
            }
            await self.bot.process_update(update)

        # Verified 3 items in FIFO order
        self.assertEqual(len(self.bot._task_queues[chat_id]), 3)
        self.assertEqual(self.bot._task_queues[chat_id], ["first follow-up", "second follow-up", "third follow-up"])

        # Check /queue output
        self.bot.send_message.reset_mock()
        await self.bot.handle_queue(chat_id)
        queue_msg = self.bot.send_message.call_args[0][1]
        self.assertIn("Task Queue Status", queue_msg)
        self.assertIn("first follow-up", queue_msg)
        self.assertIn("second follow-up", queue_msg)
        self.assertIn("third follow-up", queue_msg)

    async def test_positive_queue_image_attachment(self):
        """Positive Path 3: Image attachments sent while task is running are parsed and enqueued."""
        from unittest.mock import AsyncMock, MagicMock

        chat_id = 1003
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task

        self.bot.get_file_path = AsyncMock(return_value="/tg/photo.jpg")
        self.bot.download_file_to = AsyncMock(return_value=True)

        update = {
            "update_id": 5,
            "message": {
                "message_id": 30,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "photo": [{"file_id": "file_abc_123"}],
                "caption": "analyze this chart",
            },
        }

        await self.bot.process_update(update)

        self.assertIn(chat_id, self.bot._task_queues)
        self.assertEqual(len(self.bot._task_queues[chat_id]), 1)
        queued_item = self.bot._task_queues[chat_id][0]
        self.assertIn("[Attached User Image:", queued_item)
        self.assertIn("analyze this chart", queued_item)

        # Confirmation received
        sent_text = self.bot.send_message.call_args[0][1]
        self.assertIn("Image Queued", sent_text)
        self.assertIn("#1", sent_text)

    async def test_negative_queue_capacity_overflow(self):
        """Negative Path 1: Queue capacity guard rejects excess items once limit is reached."""
        from unittest.mock import MagicMock

        chat_id = 1004
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task
        self.bot.max_queue_size = 3

        # Pre-fill queue to capacity
        self.bot._task_queues[chat_id] = ["msg 1", "msg 2", "msg 3"]

        # Attempt to enqueue 4th item
        update = {
            "update_id": 9,
            "message": {
                "message_id": 40,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "text": "msg 4 (should be rejected)",
            },
        }
        await self.bot.process_update(update)

        # Queue remained at capacity of 3
        self.assertEqual(len(self.bot._task_queues[chat_id]), 3)
        self.assertNotIn("msg 4 (should be rejected)", self.bot._task_queues[chat_id])

        # Polite queue-full warning dispatched
        sent_text = self.bot.send_message.call_args[0][1]
        self.assertIn("Task Queue Full", sent_text)
        self.assertIn("3/3", sent_text)

    async def test_negative_empty_or_whitespace_message_during_active_task(self):
        """Negative Path 2: Empty or pure whitespace messages during active tasks are rejected without queue pollution."""
        from unittest.mock import MagicMock

        chat_id = 1005
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task

        update = {
            "update_id": 11,
            "message": {
                "message_id": 50,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "text": "    \n\t   ",
            },
        }
        await self.bot.process_update(update)

        # Queue must remain empty
        self.assertEqual(len(self.bot._task_queues.get(chat_id, [])), 0)
        sent_text = self.bot.send_message.call_args[0][1]
        self.assertIn("Please send text queries", sent_text)

    async def test_negative_active_task_crash_resilience(self):
        """Negative Path 3: If active task crashes with an error, the queue recovers and processes the next item."""
        from unittest.mock import AsyncMock, patch

        chat_id = 1006
        user_id = 999

        # Queue a subsequent task
        self.bot._task_queues[chat_id] = ["resilient queued task after crash"]

        # Simulate forward_stream raising an unhandled exception
        async def mock_crashing_stream(*args, **kwargs):
            raise RuntimeError("Agy proxy engine connection severed")
            yield  # pragma: no cover

        self.bot.forwarder.forward_stream = mock_crashing_stream
        self.bot._run_queued_task = AsyncMock()

        # Run real handle_chat_message for primary task
        from gemini_hermes.gateway.telegram_bot import TelegramBot
        await TelegramBot.handle_chat_message(self.bot, chat_id, user_id, "task that will crash")
        import asyncio
        await asyncio.sleep(0.01)

        # Active task was cleared from active tasks dictionary
        self.assertNotIn(chat_id, self.bot._active_tasks)

        # Next queued item was automatically popped and triggered via _run_queued_task
        self.bot._run_queued_task.assert_called_once_with(chat_id, user_id, "resilient queued task after crash")
        self.assertEqual(len(self.bot._task_queues.get(chat_id, [])), 0)

    async def test_negative_cancel_aborts_active_and_purges_queue(self):
        """Negative Path 4: /cancel aborts ongoing task and flushes all automatically queued chat items."""
        from unittest.mock import MagicMock

        chat_id = 1007
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task
        self.bot._task_queues[chat_id] = ["queued 1", "queued 2", "queued 3"]

        update = {
            "update_id": 15,
            "message": {
                "message_id": 60,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "text": "/cancel",
            },
        }
        await self.bot.process_update(update)

        # Active task cancelled
        mock_task.cancel.assert_called_once()
        # Queue purged
        self.assertEqual(len(self.bot._task_queues.get(chat_id, [])), 0)

        # Cancellation message verified
        sent_text = self.bot.send_message.call_args[0][1]
        self.assertIn("Ongoing task cancelled and 3 queued item(s) cleared", sent_text)

    async def test_negative_reset_aborts_active_and_purges_queue(self):
        """Negative Path 5: /reset aborts active execution and clears task queues."""
        from unittest.mock import MagicMock

        chat_id = 1008
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task
        self.bot._task_queues[chat_id] = ["queued 1", "queued 2"]

        update = {
            "update_id": 16,
            "message": {
                "message_id": 70,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "text": "/reset",
            },
        }
        await self.bot.process_update(update)

        mock_task.cancel.assert_called_once()
        self.assertEqual(len(self.bot._task_queues.get(chat_id, [])), 0)
        sent_text = self.bot.send_message.call_args[0][1]
        self.assertIn("Conversation reset", sent_text)

    async def test_negative_steer_preserves_queue_without_premature_trigger(self):
        """Negative Path 6: /steer redirects active task without dropping or prematurely popping queued items."""
        from unittest.mock import MagicMock

        chat_id = 1009
        user_id = 999
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task
        self.bot._active_task_info[chat_id] = {
            "text": "Initial task",
            "last_action": "running",
            "user_id": user_id,
            "start_time": 100.0,
        }
        self.bot._task_queues[chat_id] = ["pending item A", "pending item B"]

        update = {
            "update_id": 17,
            "message": {
                "message_id": 80,
                "chat": {"id": chat_id},
                "from": {"id": user_id},
                "text": "/steer pivot now to new direction",
            },
        }
        await self.bot.process_update(update)

        # Active task was cancelled
        mock_task.cancel.assert_called_once()

        # The queued items were NOT popped during the steering handoff
        self.assertEqual(self.bot._task_queues[chat_id], ["pending item A", "pending item B"])


class TestChatReply(unittest.IsolatedAsyncioTestCase):
    """
    Dual Verification Test Suite for Targeted Telegram Message Quoting & Context Awareness:
    - Positive Path 1: Direct single chat message passes reply_to_message_id and reply_parameters to sendMessage API.
    - Positive Path 2: Queued tasks retain originating message_id and execute _run_queued_task quoting originating user messages.
    - Positive Path 3: Inbound Telegram reply quote (reply_to_message) extracts sender and quoted text into prompt context.
    - Positive Path 4: Inbound Telegram reply to media (photo, document) injects media description into prompt.
    - Negative Path 1: Deleted target message resilience - allow_sending_without_reply=True is set on all payloads (including fallback).
    - Negative Path 2: Graceful fallback when queue items are plain strings (legacy/test backward compatibility).
    """

    def setUp(self):
        from unittest.mock import AsyncMock, MagicMock
        from gemini_hermes.gateway.telegram_bot import TelegramBot

        self.bot = TelegramBot(token="12345:fake_token_for_test")
        self.bot.is_user_allowed = MagicMock(return_value=True)
        self.bot._api_call = AsyncMock(return_value={"ok": True, "result": {"message_id": 9999}})
        self.bot.send_chat_action = AsyncMock(return_value=True)
        self.bot.edit_message_text = AsyncMock(return_value=True)

    async def test_positive_direct_message_reply_payload(self):
        """Positive Path 1: Direct message reply passes reply_to_message_id and reply_parameters to Telegram sendMessage."""
        chat_id = 2001
        msg_id = 777

        # Call send_message directly with reply_to_message_id
        res = await self.bot.send_message(chat_id, "Direct reply test", reply_to_message_id=msg_id)
        self.assertEqual(res, 9999)

        call_args = self.bot._api_call.call_args[0]
        method = call_args[0]
        payload = call_args[1]

        self.assertEqual(method, "sendMessage")
        self.assertEqual(payload["chat_id"], chat_id)
        self.assertEqual(payload["text"], "Direct reply test")
        self.assertEqual(payload["reply_to_message_id"], msg_id)
        self.assertTrue(payload["allow_sending_without_reply"])
        self.assertEqual(
            payload["reply_parameters"],
            {"message_id": msg_id, "allow_sending_without_reply": True},
        )

    async def test_positive_queued_tasks_retain_message_id_and_reply(self):
        """Positive Path 2: Queued tasks retain originating message_id and _run_queued_task passes reply_to_message_id."""
        from unittest.mock import MagicMock, AsyncMock

        chat_id = 2002
        user_id = 888

        # Simulate active task running
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.bot._active_tasks[chat_id] = mock_task

        # Send consecutive messages
        updates = [
            {"update_id": 1, "message": {"message_id": 101, "chat": {"id": chat_id}, "from": {"id": user_id}, "text": "is"}},
            {"update_id": 2, "message": {"message_id": 102, "chat": {"id": chat_id}, "from": {"id": user_id}, "text": "just"}},
        ]

        for u in updates:
            await self.bot.process_update(u)

        # Verify queue contains QueuedTask with matching message_id
        self.assertEqual(len(self.bot._task_queues[chat_id]), 2)
        q1 = self.bot._task_queues[chat_id][0]
        q2 = self.bot._task_queues[chat_id][1]
        self.assertEqual(q1, "is")
        self.assertEqual(q1.message_id, 101)
        self.assertEqual(q2, "just")
        self.assertEqual(q2.message_id, 102)

        # Test _run_queued_task dispatching for q1
        self.bot.send_message = AsyncMock(return_value=5555)
        self.bot.handle_chat_message = AsyncMock()

        await self.bot._run_queued_task(chat_id, user_id, q1)

        # Notice message replies to 101
        self.bot.send_message.assert_called_once()
        self.assertEqual(self.bot.send_message.call_args[1].get("reply_to_message_id"), 101)

        # handle_chat_message received reply_to_message_id=101
        self.bot.handle_chat_message.assert_called_once_with(
            chat_id, user_id, q1, reply_to_message_id=101
        )

    async def test_positive_inbound_reply_to_message_context_injection(self):
        """Positive Path 3: Replying/quoting a Telegram message injects sender and quoted text into prompt."""
        from unittest.mock import AsyncMock

        chat_id = 2003
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        update = {
            "update_id": 5,
            "message": {
                "message_id": 301,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "Can you explain this part?",
                "reply_to_message": {
                    "message_id": 200,
                    "from": {"id": 12345, "first_name": "Gemini-Hermes"},
                    "text": "def compute_hash(): return sha256(data)",
                },
            },
        }

        await self.bot.process_update(update)

        self.bot.handle_chat_message.assert_called_once()
        prompt_arg = self.bot.handle_chat_message.call_args[0][2]
        reply_id_arg = self.bot.handle_chat_message.call_args[1].get("reply_to_message_id")

        self.assertEqual(reply_id_arg, 301)
        self.assertIn('[Replying to message from Gemini-Hermes: "def compute_hash(): return sha256(data)"]', prompt_arg)
        self.assertIn("Can you explain this part?", prompt_arg)

    async def test_positive_inbound_reply_to_media_context(self):
        """Positive Path 4: Replying to photo or document without text injects media description into prompt."""
        from unittest.mock import AsyncMock

        chat_id = 2004
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        # Reply to photo
        update_photo = {
            "update_id": 6,
            "message": {
                "message_id": 302,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "What does this show?",
                "reply_to_message": {
                    "message_id": 201,
                    "from": {"id": 888, "first_name": "Arif"},
                    "photo": [{"file_id": "photo_xyz"}],
                },
            },
        }
        await self.bot.process_update(update_photo)
        prompt_photo = self.bot.handle_chat_message.call_args[0][2]
        self.assertIn("[Replying to photo from Arif]", prompt_photo)

        # Reply to document
        self.bot.handle_chat_message.reset_mock()
        update_doc = {
            "update_id": 7,
            "message": {
                "message_id": 303,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "Summarize this PDF",
                "reply_to_message": {
                    "message_id": 202,
                    "from": {"id": 888, "first_name": "Arif"},
                    "document": {"file_id": "doc_xyz", "file_name": "proposal.pdf"},
                },
            },
        }
        await self.bot.process_update(update_doc)
        prompt_doc = self.bot.handle_chat_message.call_args[0][2]
        self.assertIn("[Replying to file (proposal.pdf) from Arif]", prompt_doc)

    async def test_negative_deleted_message_resilience_and_markdown_fallback(self):
        """Negative Path 1: Deleted message resilience and fallback payload retains reply_to_message_id and allow_sending_without_reply."""
        from unittest.mock import AsyncMock

        chat_id = 2005
        msg_id = 999

        # Simulate first call failing (e.g. markdown parse error) and fallback succeeding
        self.bot._api_call = AsyncMock(side_effect=[
            {"ok": False, "description": "Bad Request: can't parse entities"},
            {"ok": True, "result": {"message_id": 8888}},
        ])

        res = await self.bot.send_message(chat_id, "Unclosed *markdown", reply_to_message_id=msg_id)
        self.assertEqual(res, 8888)
        self.assertEqual(self.bot._api_call.call_count, 2)

        # Check fallback call payload
        fallback_call_args = self.bot._api_call.call_args_list[1][0]
        fallback_payload = fallback_call_args[1]

        self.assertEqual(fallback_payload["reply_to_message_id"], msg_id)
        self.assertTrue(fallback_payload["allow_sending_without_reply"])
        self.assertEqual(
            fallback_payload["reply_parameters"],
            {"message_id": msg_id, "allow_sending_without_reply": True},
        )

    async def test_negative_plain_string_queue_items_fallback_cleanly(self):
        """Negative Path 2: Plain string queue items (without message_id attribute) execute gracefully with None."""
        from unittest.mock import AsyncMock

        chat_id = 2006
        user_id = 888

        self.bot.send_message = AsyncMock(return_value=7777)
        self.bot.handle_chat_message = AsyncMock()

        # Pass a regular python string without message_id
        regular_string = "task from plain string"
        await self.bot._run_queued_task(chat_id, user_id, regular_string)

        self.bot.send_message.assert_called_once()
        self.assertIsNone(self.bot.send_message.call_args[1].get("reply_to_message_id"))
        self.bot.handle_chat_message.assert_called_once_with(
            chat_id, user_id, regular_string, reply_to_message_id=None
        )


    async def test_negative_secondary_fallback_without_reply_when_telegram_rejects_reply_parameters(self):
        """Negative Path 3: If Telegram rejects reply targeting on both attempts, send directly without reply params."""
        from unittest.mock import AsyncMock

        chat_id = 2007
        msg_id = 99999

        # Simulate:
        # Call 1 (with markdown + reply): 400 Bad Request
        # Call 2 (fallback without markdown + reply): 400 Bad Request: message to be replied not found
        # Call 3 (fallback without reply parameters): 200 OK
        self.bot._api_call = AsyncMock(side_effect=[
            {"ok": False, "description": "Bad Request: can't parse entities"},
            {"ok": False, "description": "Bad Request: message to be replied not found"},
            {"ok": True, "result": {"message_id": 99001}},
        ])

        res = await self.bot.send_message(chat_id, "Crucial alert *text*", reply_to_message_id=msg_id)
        self.assertEqual(res, 99001)
        self.assertEqual(self.bot._api_call.call_count, 3)

        # 3rd call should have completely stripped reply parameters
        final_call_args = self.bot._api_call.call_args_list[2][0]
        final_payload = final_call_args[1]
        self.assertNotIn("reply_to_message_id", final_payload)
        self.assertNotIn("reply_parameters", final_payload)
        self.assertEqual(final_payload["text"], "Crucial alert *text*")

    async def test_negative_malformed_non_dict_reply_to_message_resilience(self):
        """Negative Path 4: Malformed or non-dict reply_to_message in update does not cause crash or unhandled exception."""
        from unittest.mock import AsyncMock

        chat_id = 2008
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        # Update with non-dict reply_to_message (e.g. integer or string)
        malformed_updates = [
            {"update_id": 10, "message": {"message_id": 401, "chat": {"id": chat_id}, "from": {"id": user_id}, "text": "hello", "reply_to_message": "not_a_dict"}},
            {"update_id": 11, "message": {"message_id": 402, "chat": {"id": chat_id}, "from": {"id": user_id}, "text": "world", "reply_to_message": 12345}},
            {"update_id": 12, "message": {"message_id": 403, "chat": {"id": chat_id}, "from": {"id": user_id}, "text": "test", "reply_to_message": None}},
        ]

        for u in malformed_updates:
            await self.bot.process_update(u)

        self.assertEqual(self.bot.handle_chat_message.call_count, 3)

    async def test_negative_empty_or_whitespace_reply_text_sanitization(self):
        """Negative Path 5: Whitespace-only or empty reply text falls back cleanly without empty quotes."""
        from unittest.mock import AsyncMock

        chat_id = 2009
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        update = {
            "update_id": 13,
            "message": {
                "message_id": 404,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "What about this?",
                "reply_to_message": {
                    "message_id": 300,
                    "from": {"id": 123, "first_name": "Arif"},
                    "text": "   \n\t  ",
                },
            },
        }

        await self.bot.process_update(update)

        self.bot.handle_chat_message.assert_called_once()
        prompt = self.bot.handle_chat_message.call_args[0][2]
        self.assertNotIn('""', prompt)
        self.assertIn("[Replying to message from Arif]\n\nWhat about this?", prompt)

    async def test_negative_inbound_reply_to_diverse_media_types(self):
        """Negative Path 6: Replying to voice, audio, video, sticker, poll, location, or contact injects descriptive metadata."""
        from unittest.mock import AsyncMock

        chat_id = 2010
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        media_test_cases = [
            ({"voice": {"file_id": "v1"}}, "[Replying to voice message from Alice]"),
            ({"audio": {"title": "Podcast Ep 1"}}, "[Replying to audio (Podcast Ep 1) from Alice]"),
            ({"video": {"file_id": "vid1"}}, "[Replying to video from Alice]"),
            ({"sticker": {"emoji": "🚀"}}, "[Replying to sticker 🚀 from Alice]"),
            ({"sticker": {}}, "[Replying to sticker from Alice]"),
            ({"poll": {"question": "Deploy to prod?"}}, '[Replying to poll "Deploy to prod?" from Alice]'),
            ({"location": {"latitude": 12.34}}, "[Replying to shared location from Alice]"),
            ({"contact": {"first_name": "Bob"}}, "[Replying to shared contact (Bob) from Alice]"),
        ]

        for reply_dict, expected_context in media_test_cases:
            self.bot.handle_chat_message.reset_mock()
            reply_dict["from"] = {"first_name": "Alice"}
            update = {
                "update_id": 14,
                "message": {
                    "message_id": 405,
                    "chat": {"id": chat_id},
                    "from": {"id": user_id, "first_name": "Tester"},
                    "text": "Check this",
                    "reply_to_message": reply_dict,
                },
            }
            await self.bot.process_update(update)
            prompt = self.bot.handle_chat_message.call_args[0][2]
            self.assertIn(expected_context, prompt)

    async def test_negative_inbound_reply_from_anonymous_channel_sender(self):
        """Negative Path 7: Replying to channel message without 'from' uses sender_chat title or User fallback."""
        from unittest.mock import AsyncMock

        chat_id = 2011
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        # Channel message with sender_chat
        update_channel = {
            "update_id": 15,
            "message": {
                "message_id": 406,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Tester"},
                "text": "Explain this announcement",
                "reply_to_message": {
                    "message_id": 305,
                    "sender_chat": {"title": "Release Channel"},
                    "text": "v2.0 is out now",
                },
            },
        }
        await self.bot.process_update(update_channel)
        prompt = self.bot.handle_chat_message.call_args[0][2]
        self.assertIn('[Replying to message from Release Channel: "v2.0 is out now"]', prompt)

        # Neither from nor sender_chat present
        self.bot.handle_chat_message.reset_mock()
        update_no_sender = {
            "update_id": 16,
            "message": {
                "message_id": 407,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Tester"},
                "text": "What about this?",
                "reply_to_message": {
                    "message_id": 306,
                    "text": "Anonymous post",
                },
            },
        }
        await self.bot.process_update(update_no_sender)
        prompt_anon = self.bot.handle_chat_message.call_args[0][2]
        self.assertIn('[Replying to message from User: "Anonymous post"]', prompt_anon)

    async def test_negative_command_with_reply_context_preservation(self):
        """Negative Path 8: Commands (/btw and /steer) executed while quoting an earlier message preserve reply_context."""
        from unittest.mock import AsyncMock

        chat_id = 2012
        user_id = 888

        self.bot.handle_btw = AsyncMock()
        self.bot.handle_steer = AsyncMock()

        # /btw quoting a message
        update_btw = {
            "update_id": 17,
            "message": {
                "message_id": 408,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "/btw why is this logic needed?",
                "reply_to_message": {
                    "message_id": 250,
                    "from": {"first_name": "Gemini-Hermes"},
                    "text": "if not res.get('ok'): fallback()",
                },
            },
        }
        await self.bot.process_update(update_btw)
        self.bot.handle_btw.assert_called_once()
        btw_arg = self.bot.handle_btw.call_args[0][2]
        self.assertIn('[Replying to message from Gemini-Hermes: "if not res.get(\'ok\'): fallback()"]', btw_arg)
        self.assertIn("why is this logic needed?", btw_arg)

        # /steer quoting a message
        update_steer = {
            "update_id": 18,
            "message": {
                "message_id": 409,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "/steer simplify this approach",
                "reply_to_message": {
                    "message_id": 251,
                    "from": {"first_name": "Gemini-Hermes"},
                    "text": "complex multi-stage pipeline",
                },
            },
        }
        await self.bot.process_update(update_steer)
        self.bot.handle_steer.assert_called_once()
        steer_arg = self.bot.handle_steer.call_args[0][2]
        self.assertIn('[Replying to message from Gemini-Hermes: "complex multi-stage pipeline"]', steer_arg)
        self.assertIn("simplify this approach", steer_arg)

    async def test_negative_queued_image_with_reply_context_notice(self):
        """Negative Path 9: Queued image item with prepended reply context still emits image processing notice."""
        from unittest.mock import AsyncMock
        from gemini_hermes.gateway.telegram_bot import QueuedTask

        chat_id = 2013
        user_id = 888

        self.bot.send_message = AsyncMock(return_value=1234)
        self.bot.handle_chat_message = AsyncMock()

        # Task with reply context prepended before image marker
        queued_img_text = (
            '[Replying to message from Arif: "take a look at this"]\n\n'
            '[Attached User Image: /tmp/photo.jpg]\n'
            'Caption / Question: What does this chart show?'
        )
        task = QueuedTask(queued_img_text, message_id=501, item_type="image")

        await self.bot._run_queued_task(chat_id, user_id, task)

        self.bot.send_message.assert_called_once()
        notice_sent = self.bot.send_message.call_args[0][1]
        self.assertEqual(notice_sent, "⚡ *Processing queued image analysis...*")
        self.assertEqual(self.bot.send_message.call_args[1].get("reply_to_message_id"), 501)

    async def test_negative_reply_text_long_truncation(self):
        """Negative Path 10: Inbound quoted text exceeding 300 chars is cleanly truncated to prevent context bloat."""
        from unittest.mock import AsyncMock

        chat_id = 2014
        user_id = 888

        self.bot.handle_chat_message = AsyncMock()

        long_code = "A" * 500
        update = {
            "update_id": 19,
            "message": {
                "message_id": 410,
                "chat": {"id": chat_id},
                "from": {"id": user_id, "first_name": "Arif"},
                "text": "Refactor this snippet",
                "reply_to_message": {
                    "message_id": 260,
                    "from": {"first_name": "Arif"},
                    "text": long_code,
                },
            },
        }

        await self.bot.process_update(update)

        self.bot.handle_chat_message.assert_called_once()
        prompt = self.bot.handle_chat_message.call_args[0][2]
        expected_preview = "A" * 297 + "..."
        self.assertIn(f'[Replying to message from Arif: "{expected_preview}"]', prompt)


if __name__ == "__main__":
    unittest.main()



