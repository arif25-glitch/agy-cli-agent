import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from gemini_hermes.config import PROJECTS_DIR

logger = logging.getLogger("gemini-hermes.projects")


class Project(BaseModel):
    id: str
    name: str
    path: str
    description: str = ""
    tech_stack: str = ""
    status: str = "active"  # active, paused, completed, shelved
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_worked_on: str = Field(default_factory=lambda: datetime.now().isoformat())
    active_tasks: List[str] = Field(default_factory=list)
    notes: str = ""

    def to_summary(self) -> str:
        status_icons = {
            "active": "🟢",
            "paused": "🟡",
            "completed": "✅",
            "shelved": "📦",
        }
        icon = status_icons.get(self.status, "📁")
        tasks_count = len(self.active_tasks)
        task_str = f" ({tasks_count} open task{'s' if tasks_count != 1 else ''})" if tasks_count else ""
        return f"{icon} *{self.name}* (`{self.id}`)\n  • Path: `{self.path}`\n  • Stack: `{self.tech_stack or 'General'}`\n  • Status: `{self.status}`{task_str}\n  • Notes: _{self.description or self.notes or 'No description'}_"


class ProjectManager:
    def __init__(self, projects_dir: Path = PROJECTS_DIR):
        self.projects_dir = projects_dir
        self.projects_file = self.projects_dir / "projects.json"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not self.projects_file.exists():
            default_projects = {
                "gemini-hermes": {
                    "id": "gemini-hermes",
                    "name": "Gemini-Hermes Autonomous Agent",
                    "path": "/gemini-hermes",
                    "description": "Autonomous AI agent colleague combining Nous Hermes cognitive architecture with Google Antigravity proxy engine.",
                    "tech_stack": "Python 3.12, Antigravity CLI (agy), Asyncio, Telegram Bot API",
                    "status": "active",
                    "created_at": "2026-09-17T21:18:39",
                    "last_worked_on": datetime.now().isoformat(),
                    "active_tasks": [
                        "Proactive Self-Verification & Sanity Checking",
                        "Project State Indexing",
                        "Modular Skills & Execution Arsenal",
                        "Smarter Multi-Agent Delegation Templates",
                    ],
                    "notes": "Primary agent daemon repository and orchestration core.",
                },
                "cashflow-subscription": {
                    "id": "cashflow-subscription",
                    "name": "Next.js Cashflow Subscription System",
                    "path": "/root/.gemini/antigravity-cli/scratch/cashflow-subscription",
                    "description": "Full-function Next.js 14 web app with subscription tiers, billing cycles, cashflow income/expense tracking, and zero-dependency atomic JSON persistence.",
                    "tech_stack": "Next.js 14, React, Tailwind CSS, TypeScript, Atomic JSON DB",
                    "status": "completed",
                    "created_at": "2026-09-18T06:22:00",
                    "last_worked_on": "2026-09-18T06:49:56",
                    "active_tasks": [],
                    "notes": "Verified production build (exit code 0) across all 9 pages and REST API routes.",
                },
            }
            self.save_projects(default_projects)

    def load_projects(self) -> Dict[str, Project]:
        if not self.projects_file.exists():
            return {}
        try:
            with open(self.projects_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {pid: Project(**data) for pid, data in raw.items()}
        except Exception as e:
            logger.error(f"Failed to load projects from {self.projects_file}: {e}")
            return {}

    def save_projects(self, projects: Dict[str, Any]):
        try:
            serializable = {}
            for pid, p in projects.items():
                if isinstance(p, Project):
                    serializable[pid] = p.model_dump()
                elif isinstance(p, dict):
                    serializable[pid] = p
            with open(self.projects_file, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save projects to {self.projects_file}: {e}")

    def list_projects(self) -> List[Project]:
        projects = self.load_projects()
        return sorted(projects.values(), key=lambda p: p.last_worked_on, reverse=True)

    def get_project(self, identifier: str) -> Optional[Project]:
        projects = self.load_projects()
        target = identifier.strip().lower()
        if target in projects:
            return projects[target]
        # Match by name or path
        for p in projects.values():
            if p.name.lower() == target or p.path.lower() == target or target in p.name.lower():
                return p
        return None

    def bookmark_project(
        self,
        name: str,
        path: str,
        description: str = "",
        tech_stack: str = "",
        status: str = "active",
        notes: str = "",
        tasks: Optional[List[str]] = None,
    ) -> Project:
        projects = self.load_projects()
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "-", name.strip().lower()).strip("-")
        now = datetime.now().isoformat()

        existing = projects.get(slug)
        created_at = existing.created_at if existing else now

        project = Project(
            id=slug,
            name=name.strip(),
            path=str(Path(path).resolve()),
            description=description.strip() or (existing.description if existing else ""),
            tech_stack=tech_stack.strip() or (existing.tech_stack if existing else ""),
            status=status,
            created_at=created_at,
            last_worked_on=now,
            active_tasks=tasks if tasks is not None else (existing.active_tasks if existing else []),
            notes=notes.strip() or (existing.notes if existing else ""),
        )
        projects[slug] = project
        self.save_projects(projects)
        logger.info(f"Bookmarked project: {slug} at {path}")
        return project

    def update_project_status(self, identifier: str, status: str) -> Optional[Project]:
        project = self.get_project(identifier)
        if not project:
            return None
        project.status = status
        project.last_worked_on = datetime.now().isoformat()
        projects = self.load_projects()
        projects[project.id] = project
        self.save_projects(projects)
        return project

    def add_task(self, identifier: str, task: str) -> Optional[Project]:
        project = self.get_project(identifier)
        if not project:
            return None
        if task not in project.active_tasks:
            project.active_tasks.append(task.strip())
            project.last_worked_on = datetime.now().isoformat()
            projects = self.load_projects()
            projects[project.id] = project
            self.save_projects(projects)
        return project

    def complete_task(self, identifier: str, task_index_or_name: str) -> Optional[Project]:
        project = self.get_project(identifier)
        if not project:
            return None
        target = task_index_or_name.strip()
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(project.active_tasks):
                project.active_tasks.pop(idx)
        else:
            project.active_tasks = [t for t in project.active_tasks if target.lower() not in t.lower()]
        project.last_worked_on = datetime.now().isoformat()
        projects = self.load_projects()
        projects[project.id] = project
        self.save_projects(projects)
        return project

    def render_projects_summary(self) -> str:
        projects = self.list_projects()
        if not projects:
            return "No projects currently indexed."
        lines = ["## Indexed Active Projects (Persistent State)"]
        for p in projects:
            lines.append(
                f"- **{p.name}** (`{p.id}`): [{p.status.upper()}] Path: `{p.path}` | Stack: `{p.tech_stack}`"
            )
            if p.active_tasks:
                lines.append(f"  * Pending Tasks: {', '.join(p.active_tasks[:3])}")
        return "\n".join(lines)
