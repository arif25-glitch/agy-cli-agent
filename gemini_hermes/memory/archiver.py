"""
Task backlog parser, hot context slice builder, and completed task archiver.
"""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

from gemini_hermes.memory.templates import DEFAULT_ARCHIVE_TEMPLATE, DEFAULT_MEMORY_ARCHIVE_TEMPLATE

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


class MemoryNotesArchiver:
    """
    Parses and manages long-term memory notes under dynamic sections
    like '## Key Facts & Lessons', separating hot recent notes from
    older or transient entries into warm disk archives (MEMORY_ARCHIVE.md).
    """

    @staticmethod
    def parse_memory_notes(content: str, section: str = "Key Facts & Lessons") -> Dict[str, Any]:
        """
        Parses MEMORY.md into before_section, section_header, individual note blocks, and after_section.
        Preserves all root directives (Directives, Standards, Protocols) untouched.
        """
        lines = content.splitlines()
        before_lines = []
        section_lines = []
        after_lines = []

        state = "before"
        target_header = f"## {section}"

        for line in lines:
            if state == "before":
                if line.strip().startswith(target_header):
                    state = "in_section"
                else:
                    before_lines.append(line)
            elif state == "in_section":
                if line.strip().startswith("## ") and not line.strip().startswith(target_header):
                    state = "after"
                    after_lines.append(line)
                else:
                    section_lines.append(line)
            elif state == "after":
                after_lines.append(line)

        if state == "before":
            return {
                "before": content.rstrip(),
                "section_header": "",
                "notes": [],
                "after": "",
            }

        note_blocks = []
        current_block = []

        for line in section_lines:
            stripped = line.strip()
            # A new bullet at root indentation starts a new block
            is_new_note = (
                (line.startswith("- ") or line.startswith("* "))
                and not (line.startswith("  ") or line.startswith("\t"))
            )
            if is_new_note:
                if current_block:
                    note_blocks.append("\n".join(current_block))
                    current_block = []
                current_block.append(line)
            elif current_block and (line.startswith(" ") or line.startswith("\t") or not stripped):
                current_block.append(line)
            elif stripped:
                if current_block:
                    note_blocks.append("\n".join(current_block))
                    current_block = []
                current_block.append(line)

        if current_block:
            note_blocks.append("\n".join(current_block))

        return {
            "before": "\n".join(before_lines).rstrip(),
            "section_header": target_header,
            "notes": note_blocks,
            "after": "\n".join(after_lines).strip(),
        }

    @classmethod
    def archive_notes(
        cls,
        memory_file: Path,
        archive_file: Path,
        keep_recent: int = 10,
        notes_to_archive: Optional[List[str]] = None,
        section: str = "Key Facts & Lessons",
    ) -> Dict[str, Any]:
        """
        Migrates excess or designated notes from MEMORY.md to MEMORY_ARCHIVE.md.
        """
        if not memory_file.exists():
            return {"status": "empty", "archived_count": 0, "retained_count": 0}

        content = memory_file.read_text(encoding="utf-8").strip()
        if not content:
            return {"status": "empty", "archived_count": 0, "retained_count": 0}

        parsed = cls.parse_memory_notes(content, section=section)
        notes = parsed["notes"]
        if not notes:
            return {"status": "noop", "archived_count": 0, "retained_count": 0}

        if notes_to_archive is not None:
            # Explicit selection (e.g. from semantic classifier)
            to_archive = [n for n in notes if n in notes_to_archive]
            to_retain = [n for n in notes if n not in notes_to_archive]
        else:
            if len(notes) <= keep_recent:
                return {
                    "status": "noop",
                    "archived_count": 0,
                    "retained_count": len(notes),
                }
            # Notes are listed chronologically or reverse chronologically.
            # In append_to_memory, newer notes are prepended at the top of the section.
            # So notes[0] is newest, notes[-1] is oldest!
            to_retain = notes[:keep_recent]
            to_archive = notes[keep_recent:]

        if not to_archive:
            return {
                "status": "noop",
                "archived_count": 0,
                "retained_count": len(notes),
            }

        archive_file.parent.mkdir(parents=True, exist_ok=True)
        if not archive_file.exists():
            archive_file.write_text(DEFAULT_MEMORY_ARCHIVE_TEMPLATE, encoding="utf-8")

        existing_archive = archive_file.read_text(encoding="utf-8").rstrip()
        archive_block = "\n".join(to_archive)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_archive = f"{existing_archive}\n\n### Archived on {timestamp}\n{archive_block}\n"
        archive_file.write_text(new_archive, encoding="utf-8")

        # Reconstruct MEMORY.md
        parts = []
        if parsed["before"]:
            parts.append(parsed["before"])

        if parsed["section_header"]:
            rebuilt_section = parsed["section_header"]
            if to_retain:
                rebuilt_section += "\n" + "\n".join(to_retain)
            parts.append(rebuilt_section)

        if parsed["after"]:
            parts.append(parsed["after"])

        new_memory = "\n\n".join(parts) + "\n"
        memory_file.write_text(new_memory, encoding="utf-8")

        logger.info(
            f"Archived {len(to_archive)} memory notes to {archive_file}. Retained {len(to_retain)}."
        )

        return {
            "status": "archived",
            "archived_count": len(to_archive),
            "retained_count": len(to_retain),
            "archive_file": str(archive_file),
        }


class MemoryPruner:
    """
    Unified coordinator for autonomous memory compaction and pruning.
    Executes both task backlog archiving and memory notes retention management.
    """

    @classmethod
    def prune_all_pure(
        cls,
        backlog_file: Path,
        backlog_archive: Path,
        memory_file: Path,
        memory_archive: Path,
        keep_recent_backlog: int = 5,
        max_notes: int = 10,
    ) -> Dict[str, Any]:
        """
        Pure Core deterministic pruning:
        - Migrates completed tasks older than keep_recent_backlog to BACKLOG_ARCHIVE.md
        - Migrates facts/lessons older than max_notes to MEMORY_ARCHIVE.md
        Zero external calls, 0ms overhead, 100% deterministic.
        """
        backlog_res = BacklogArchiver.archive_completed_backlog(
            backlog_file, backlog_archive, keep_recent=keep_recent_backlog
        )
        notes_res = MemoryNotesArchiver.archive_notes(
            memory_file, memory_archive, keep_recent=max_notes
        )

        total_archived = backlog_res.get("archived_count", 0) + notes_res.get("archived_count", 0)
        status = "archived" if total_archived > 0 else "noop"

        summary_parts = []
        if backlog_res.get("archived_count", 0) > 0:
            summary_parts.append(f"{backlog_res['archived_count']} completed tasks")
        if notes_res.get("archived_count", 0) > 0:
            summary_parts.append(f"{notes_res['archived_count']} stale memory notes")

        summary = (
            f"Archived {', '.join(summary_parts)} to warm disk storage."
            if summary_parts
            else "Memory already compact and lean."
        )

        return {
            "status": status,
            "total_archived": total_archived,
            "backlog": backlog_res,
            "notes": notes_res,
            "summary": summary,
            "mode": "pure_core",
        }

