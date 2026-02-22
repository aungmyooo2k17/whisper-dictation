"""
Transcription history stored as JSONL.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class HistoryEntry:
    timestamp: str
    text: str
    model: str = ""
    device: str = ""
    duration: float = 0.0


class TranscriptionHistory:
    """Manages transcription history in a JSONL file."""

    def __init__(self, path: str = "~/.local/share/whisper-dictation/history.jsonl",
                 max_entries: int = 10000):
        self.path = Path(os.path.expanduser(path))
        self.max_entries = max_entries

    def save(self, entry: HistoryEntry) -> None:
        """Append an entry to the history file.

        Creates the parent directory if needed.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

        # Prune if over max
        self._prune_if_needed()

    def get_recent(self, n: int = 10) -> list:
        """Get the N most recent history entries.

        Returns:
            List of HistoryEntry objects, newest first.
        """
        if not self.path.exists():
            return []

        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(HistoryEntry(**json.loads(line)))
                    except (json.JSONDecodeError, TypeError):
                        continue

        return list(reversed(entries[-n:]))

    def search(self, query: str) -> list:
        """Search history entries by text content.

        Args:
            query: Search string (case-insensitive).

        Returns:
            List of matching HistoryEntry objects, newest first.
        """
        if not self.path.exists():
            return []

        query_lower = query.lower()
        matches = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if query_lower in data.get("text", "").lower():
                        matches.append(HistoryEntry(**data))
                except (json.JSONDecodeError, TypeError):
                    continue

        return list(reversed(matches))

    def _prune_if_needed(self) -> None:
        """Prune history file if it exceeds max_entries."""
        if not self.path.exists():
            return

        lines = self.path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= self.max_entries:
            return

        # Keep only the most recent entries
        keep = lines[-self.max_entries:]
        self.path.write_text("\n".join(keep) + "\n", encoding="utf-8")
