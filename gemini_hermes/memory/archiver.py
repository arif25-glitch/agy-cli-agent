"""
Task backlog parser, hot context slice builder, and completed task archiver.
"""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from gemini_hermes.memory.templates import DEFAULT_ARCHIVE_TEMPLATE

logger = logging.getLogger("gemini-hermes.memory.archiver")


class BacklogArchiver:
    """
    Parses and manages long-term task retention, separating active hot tasks
    from completed historical tasks into warm disk archives.
    """

    @staticmethod
    def parse_backlog_items(content: str) -> Dict[str, Any]:
        """
        Parses BACKLOG.md into structured components:
        - header: everything before the tasks section (including '## Active Tasks')
        - completed: list of completed task item blocks (including multiline sub-bullets)
        - active: list of active/uncompleted task item blocks
        - placeholders: list of placeholder item blocks
        - footer: footer sections
        """
        lines = content.splitlines()
        header_lines = []
        task_blocks = []
        footer_lines = []

        state = "header"
        current_block = []

        for line in lines:
            if state == "header":
                header_lines.append(line)
                if line.strip().startswith("## Active Tasks"):
                    state = "tasks"
            elif state == "tasks":
                if line.strip().startswith("## "):
                    if current_block:
                        task_blocks.append("\n".join(current_block))
                        current_block = []
                    state = "footer"
                    footer_lines.append(line)
                else:
                    stripped = line.strip()
                    is_new_item = (
                        (line.startswith("- ") or line.startswith("* "))
                        and (
                            stripped.startswith("- [")
                            or stripped.startswith("* [")
                            or stripped.startswith("- (")
                            or stripped.startswith("* (")
                        )
                    )
                    if is_new_item:
                        if current_block:
                            task_blocks.append("\n".join(current_block))
                            current_block = []
                        current_block.append(line)
                    elif current_block and (line.startswith(" ") or line.startswith("\t") or not stripped):
                        current_block.append(line)
                    elif stripped:
                        if current_block:
                            task_blocks.append("\n".join(current_block))
                            current_block = []
                        current_block.append(line)
            elif state == "footer":
                footer_lines.append(line)

        if current_block:
            task_blocks.append("\n".join(current_block))

        completed = []
        active = []
        placeholders = []

        for block in task_blocks:
            first_line = block.strip().splitlines()[0] if block.strip() else ""
            if re.match(r"^[-*]\s*\[[xX]\]", first_line):
                completed.append(block)
            elif re.match(r"^[-*]\s*\[\s*\]", first_line):
                active.append(block)
            else:
                placeholders.append(block)

        return {
            "header": "\n".join(header_lines).rstrip(),
            "completed": completed,
            "active": active,
            "placeholders": placeholders,
            "footer": "\n".join(footer_lines).strip(),
        }

    @classmethod
    def get_hot_backlog(
        cls,
        backlog_content: str,
        archived_content: str,
        max_recent_completed: int = 5,
    ) -> str:
        """
        Returns a high-signal hot context backlog slice:
        - Keeps ALL active items [ ]
        - Keeps only the last `max_recent_completed` completed tasks [x]
        - Mentions count of archived tasks if any exist
        """
        content = backlog_content.strip()
        if not content:
            return ""

        parsed = cls.parse_backlog_items(content)
        completed = parsed["completed"]
        active = parsed["active"]
        placeholders = parsed["placeholders"]

        # Check total archived items on disk
        archived_count = len(re.findall(r"^[-*]\s*\[[xX]\]", archived_content, re.MULTILINE))

        # Check if completed items in BACKLOG.md exceed max_recent_completed
        if len(completed) > max_recent_completed:
            overflow_count = len(completed) - max_recent_completed
            retained_completed = completed[-max_recent_completed:]
            total_off_prompt = archived_count + overflow_count
        else:
            retained_completed = completed
            total_off_prompt = archived_count

        task_lines = []
        if active:
            task_lines.extend(active)
        elif not retained_completed and placeholders:
            task_lines.extend(placeholders)

        if retained_completed:
            task_lines.extend(retained_completed)

        if total_off_prompt > 0:
            task_lines.append(
                f"- *(+{total_off_prompt} older completed tasks archived in data/memory/archive/BACKLOG_ARCHIVE.md)*"
            )

        tasks_rendered = "\n".join(task_lines)
        header = parsed["header"]
        footer = parsed["footer"]

        parts = [header, tasks_rendered]
        if footer:
            parts.append(footer)
        return "\n\n".join(parts)

    @classmethod
    def archive_completed_backlog(
        cls,
        backlog_file: Path,
        archive_file: Path,
        keep_recent: int = 5,
    ) -> Dict[str, Any]:
        """
        Physically migrates completed tasks older than `keep_recent` to BACKLOG_ARCHIVE.md.
        """
        if not backlog_file.exists():
            return {"status": "empty", "archived_count": 0, "retained_count": 0, "active_count": 0}

        content = backlog_file.read_text(encoding="utf-8").strip()
        if not content:
            return {"status": "empty", "archived_count": 0, "retained_count": 0, "active_count": 0}

        parsed = cls.parse_backlog_items(content)
        completed = parsed["completed"]
        active = parsed["active"]
        placeholders = parsed["placeholders"]
        header = parsed["header"]
        footer = parsed["footer"]

        if len(completed) <= keep_recent:
            return {
                "status": "noop",
                "archived_count": 0,
                "retained_count": len(completed),
                "active_count": len(active),
            }

        to_archive = completed[:-keep_recent]
        to_retain = completed[-keep_recent:]

        archive_file.parent.mkdir(parents=True, exist_ok=True)
        if not archive_file.exists():
            archive_file.write_text(DEFAULT_ARCHIVE_TEMPLATE, encoding="utf-8")

        existing_archive = archive_file.read_text(encoding="utf-8").rstrip()
        archive_block = "\n".join(to_archive)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_archive = f"{existing_archive}\n\n### Archived on {timestamp}\n{archive_block}\n"
        archive_file.write_text(new_archive, encoding="utf-8")

        rebuilt_tasks = []
        if active:
            rebuilt_tasks.extend(active)
        elif placeholders:
            rebuilt_tasks.extend(placeholders)

        if to_retain:
            rebuilt_tasks.extend(to_retain)

        rebuilt_body = "\n".join(rebuilt_tasks)
        parts = [header, rebuilt_body]
        if footer:
            parts.append(footer)

        new_backlog = "\n\n".join(parts) + "\n"
        backlog_file.write_text(new_backlog, encoding="utf-8")

        logger.info(
            f"Archived {len(to_archive)} completed tasks to {archive_file}. Retained {len(to_retain)}."
        )

        return {
            "status": "archived",
            "archived_count": len(to_archive),
            "retained_count": len(to_retain),
            "active_count": len(active),
            "archive_file": str(archive_file),
        }
