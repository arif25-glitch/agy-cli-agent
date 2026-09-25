"""
Jev AI Smart Autonomous Memory Pruner & Archiver.
Evaluates memory entries semantically (transient vs evergreen),
migrating obsolete/ephemeral notes and completed tasks to warm disk storage
while keeping hot base context sharp, lean, and signal-dense.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from gemini_hermes.jev.client import JevClient
from gemini_hermes.memory.archiver import BacklogArchiver, MemoryNotesArchiver

logger = logging.getLogger("gemini-hermes.jev.memory_pruner")

try:
    from typesafe_sdk import Choice
    HAS_TYPESAFE_SDK = True
except ImportError:  # pragma: no cover
    Choice = None
    HAS_TYPESAFE_SDK = False


class JevMemoryPruner:
    """
    Evaluates memory notes and backlog tasks using Jev System-One Choice primitive
    to classify entries into evergreen directives vs transient operational notes,
    ensuring smart semantic archival with zero context loss.
    """

    def __init__(self, client: JevClient, min_confidence: float = 0.70):
        self.client = client
        self.min_confidence = min_confidence

    async def evaluate_notes_for_pruning(
        self,
        notes: List[str],
        max_notes: int = 10,
        timeout: Optional[float] = None,
    ) -> Optional[List[str]]:
        """
        Semantically evaluates note blocks using Jev Choice.
        Returns a list of note blocks that should be archived.
        Returns None on timeout/failure/inavailability to trigger fallback.
        """
        if not self.client.is_available or not HAS_TYPESAFE_SDK:
            return None

        if len(notes) <= max_notes:
            return []

        questions = {
            "retention_type": Choice(
                instructions=(
                    "Classify this operational memory entry: should it be archived as transient "
                    "or retained in hot context as an evergreen rule/lesson?"
                ),
                criteria={
                    "transient": (
                        "Ephemeral debug log, one-off test fact, temporary session state, "
                        "or obsolete historical note suitable for cold/warm archive."
                    ),
                    "evergreen": (
                        "Fundamental operational directive, permanent architecture standard, "
                        "critical user rule, or timeless lesson to retain in base context."
                    ),
                },
            )
        }

        transient_notes: List[str] = []
        evergreen_notes: List[str] = []

        try:
            # Evaluate excess notes
            # To keep latency minimal, evaluate candidates starting from the older entries
            candidates = notes[max_notes // 2:]
            for note in candidates:
                sample_text = note[:250].strip()
                decision = await self.client.evaluate_reflex(
                    sample_text, custom_questions=questions, timeout=timeout
                )
                if decision and "retention_type" in decision.raw_answers:
                    ans = decision.raw_answers["retention_type"]
                    choice = getattr(ans, "choice", None)
                    conf = float(getattr(ans, "confidence", 0.0))
                    if choice == "transient" and conf >= self.min_confidence:
                        transient_notes.append(note)
                    else:
                        evergreen_notes.append(note)
                else:
                    transient_notes.append(note)

            # If transient notes alone don't bring notes under max_notes, archive oldest excess
            to_archive = list(transient_notes)
            remaining_count = len(notes) - len(to_archive)
            if remaining_count > max_notes:
                # Need to archive more
                for note in notes:
                    if note not in to_archive and len(to_archive) < (len(notes) - max_notes):
                        to_archive.append(note)

            return to_archive

        except Exception as e:
            logger.debug(f"Jev semantic note evaluation error: {e}. Falling back gracefully.")
            return None

    async def prune_memory_smart(
        self,
        memory_file: Path,
        memory_archive: Path,
        backlog_file: Path,
        backlog_archive: Path,
        keep_recent_backlog: int = 5,
        max_notes: int = 10,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes smart autonomous memory pruning using Jev AI.
        Returns structured results if successful, or None if Jev is unavailable/failed.
        """
        if not self.client.is_available or not HAS_TYPESAFE_SDK:
            return None

        try:
            # 1. Backlog archiving
            backlog_res = BacklogArchiver.archive_completed_backlog(
                backlog_file, backlog_archive, keep_recent=keep_recent_backlog
            )

            # 2. Smart notes evaluation
            notes_res = {"status": "noop", "archived_count": 0, "retained_count": 0}
            if memory_file.exists():
                mem_content = memory_file.read_text(encoding="utf-8")
                parsed = MemoryNotesArchiver.parse_memory_notes(mem_content)
                notes = parsed["notes"]
                if len(notes) > max_notes:
                    notes_to_archive = await self.evaluate_notes_for_pruning(
                        notes, max_notes=max_notes, timeout=timeout
                    )
                    if notes_to_archive is not None:
                        notes_res = MemoryNotesArchiver.archive_notes(
                            memory_file,
                            memory_archive,
                            notes_to_archive=notes_to_archive,
                        )
                    else:
                        # Fallback for notes specifically
                        notes_res = MemoryNotesArchiver.archive_notes(
                            memory_file,
                            memory_archive,
                            keep_recent=max_notes,
                        )
                else:
                    notes_res = {"status": "noop", "archived_count": 0, "retained_count": len(notes)}

            total_archived = backlog_res.get("archived_count", 0) + notes_res.get("archived_count", 0)
            status = "archived" if total_archived > 0 else "noop"

            summary_parts = []
            if backlog_res.get("archived_count", 0) > 0:
                summary_parts.append(f"{backlog_res['archived_count']} completed tasks")
            if notes_res.get("archived_count", 0) > 0:
                summary_parts.append(f"{notes_res['archived_count']} transient memory notes (semantic)")

            summary = (
                f"Smart archived {', '.join(summary_parts)} to warm disk storage."
                if summary_parts
                else "Memory already compact and lean."
            )

            return {
                "status": status,
                "total_archived": total_archived,
                "backlog": backlog_res,
                "notes": notes_res,
                "summary": summary,
                "mode": "jev_smart",
            }
        except Exception as e:
            logger.debug(f"Jev smart memory pruning error: {e}. Falling back gracefully.")
            return None
