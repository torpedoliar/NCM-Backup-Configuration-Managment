from __future__ import annotations

import difflib
from pathlib import Path

from app_v4.core.config import Settings


class DiffService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def unified_diff(self, text1: str, text2: str, label1: str = "Before", label2: str = "After") -> str:
        diff = difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile=label1,
            tofile=label2,
            lineterm="",
            n=self.settings.diff_context_lines,
        )
        return "\n".join(diff)

    def get_diff_stats(self, text1: str, text2: str) -> dict[str, int]:
        matcher = difflib.SequenceMatcher(None, text1.splitlines(), text2.splitlines())
        added = 0
        removed = 0
        changed = 0
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == "delete":
                removed += i2 - i1
            elif opcode == "insert":
                added += j2 - j1
            elif opcode == "replace":
                old_count = i2 - i1
                new_count = j2 - j1
                changed += min(old_count, new_count)
                if new_count > old_count:
                    added += new_count - old_count
                elif old_count > new_count:
                    removed += old_count - new_count
        return {
            "added_lines": added,
            "removed_lines": removed,
            "changed_lines": changed,
            "total_changes": added + removed + changed,
        }

    def export_diff(self, diff_text: str, file_path: Path) -> None:
        file_path.write_text(diff_text, encoding="utf-8")
