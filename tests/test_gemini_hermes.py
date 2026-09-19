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
        self.assertEqual(cfg.app_version, "1.4.0")
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

        mem = self.store.get_long_term_memory()
        self.assertIn("Operational Standards", mem)
        self.assertIn("Memory Scaling & Retention Protocol", mem)



class TestSkillManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.custom_skills_dir = self.temp_dir / "custom_skills"
        self.manager = SkillManager(custom_skills_dir=self.custom_skills_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_builtin_skills_loading(self):
        skills = self.manager.get_all_skills()
        self.assertEqual(len(skills), 8)
        self.assertNotIn("manager_delegation", skills)
        self.assertIn("multi_step_researcher", skills)
        self.assertIn("auto_debugger", skills)
        self.assertIn("api_tester", skills)
        self.assertIn("system_monitor", skills)
        self.assertIn("task_scheduler", skills)
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
        self.assertNotIn("manager_delegation", prompt.lower())


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


if __name__ == "__main__":
    unittest.main()
