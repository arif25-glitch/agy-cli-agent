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
        self.assertEqual(cfg.app_version, "1.4.3")

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


if __name__ == "__main__":
    unittest.main()


