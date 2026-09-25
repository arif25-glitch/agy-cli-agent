import re
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from gemini_hermes.config import SKILLS_DIR

logger = logging.getLogger("gemini-hermes.skills")
BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent / "builtin"


class Skill(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    instructions: str
    file_path: Path

    def render_prompt(self) -> str:
        return f"### Skill: {self.name}\n**Description**: {self.description}\n\n{self.instructions}"


class SkillManager:
    def __init__(self, custom_skills_dir: Path = SKILLS_DIR, builtin_skills_dir: Path = BUILTIN_SKILLS_DIR):
        self.custom_skills_dir = custom_skills_dir
        self.builtin_skills_dir = builtin_skills_dir
        self.custom_skills_dir.mkdir(parents=True, exist_ok=True)
        self.builtin_skills_dir.mkdir(parents=True, exist_ok=True)

    def _parse_skill_file(self, path: Path) -> Optional[Skill]:
        if not path.exists():
            return None
        try:
            content = path.read_text(encoding="utf-8")
            pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                fm_text, instructions = match.group(1), match.group(2).strip()
                metadata = yaml.safe_load(fm_text) or {}
                name = metadata.get("name", path.parent.name if path.name == "SKILL.md" else path.stem)
                description = metadata.get("description", "No description provided.")
                version = str(metadata.get("version", "1.0.0"))
                tags = metadata.get("tags", [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",")]
                return Skill(
                    name=name,
                    description=description,
                    version=version,
                    tags=tags,
                    instructions=instructions,
                    file_path=path,
                )
            else:
                # No frontmatter, treat whole file as instructions
                name = path.parent.name if path.name == "SKILL.md" else path.stem
                return Skill(
                    name=name,
                    description="Custom procedure skill",
                    version="1.0.0",
                    tags=[],
                    instructions=content.strip(),
                    file_path=path,
                )
        except Exception as e:
            logger.error(f"Failed to parse skill file {path}: {e}")
            return None

    def get_all_skills(self) -> Dict[str, Skill]:
        skills: Dict[str, Skill] = {}

        # First load builtin skills
        for item in self.builtin_skills_dir.glob("**/SKILL.md"):
            s = self._parse_skill_file(item)
            if s:
                skills[s.name] = s

        # Then load custom / learned skills (overriding builtins if same name)
        for item in self.custom_skills_dir.glob("**/SKILL.md"):
            s = self._parse_skill_file(item)
            if s:
                skills[s.name] = s
        for item in self.custom_skills_dir.glob("*.md"):
            s = self._parse_skill_file(item)
            if s:
                skills[s.name] = s

        return skills

    def get_skill(self, name: str) -> Optional[Skill]:
        skills = self.get_all_skills()
        return skills.get(name)

    def create_or_update_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        tags: Optional[List[str]] = None,
        version: str = "1.0.0",
    ) -> Skill:
        clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip().lower())
        skill_dir = self.custom_skills_dir / clean_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        file_path = skill_dir / "SKILL.md"

        frontmatter = {
            "name": clean_name,
            "description": description.strip(),
            "version": version,
            "tags": tags or ["custom", "learned"],
        }
        fm_str = yaml.dump(frontmatter, sort_keys=False).strip()
        full_content = f"---\n{fm_str}\n---\n\n{instructions.strip()}\n"

        file_path.write_text(full_content, encoding="utf-8")
        logger.info(f"Saved skill {clean_name} to {file_path}")

        return Skill(
            name=clean_name,
            description=description.strip(),
            version=version,
            tags=tags or ["custom", "learned"],
            instructions=instructions.strip(),
            file_path=file_path,
        )

    def render_skills_summary(self, skills_subset: Optional[List[str]] = None) -> str:
        skills = self.get_all_skills()
        if not skills:
            return "No skills currently registered."

        if skills_subset is not None:
            if not skills_subset:
                return ""  # Explicitly empty subset means 0 skills injected
            skills = {k: v for k, v in skills.items() if k in skills_subset}
            if not skills:
                return ""

        lines = ["## Available Skills (Modular Procedures)"]
        for s in skills.values():
            tag_str = f" [{', '.join(s.tags)}]" if s.tags else ""
            lines.append(f"- **{s.name}**{tag_str}: {s.description}")
        return "\n".join(lines)
