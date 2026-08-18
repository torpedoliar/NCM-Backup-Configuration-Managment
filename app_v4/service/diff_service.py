from __future__ import annotations

import difflib
from pathlib import Path

from app_v4.core.config import Settings


SideBySideRow = tuple[int, int, str, str, str]


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

    def side_by_side_diff(self, text1: str, text2: str) -> list[SideBySideRow]:
        """Pair-wise side-by-side diff. Each row: (lineno_a, lineno_b, line_a, line_b, opcode).

        Opcodes: equal | delete | insert | replace. lineno is 0 when the line is absent on that side.
        """
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        result: list[SideBySideRow] = []
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == "equal":
                for k in range(i2 - i1):
                    result.append((i1 + k + 1, j1 + k + 1, lines1[i1 + k], lines2[j1 + k], "equal"))
            elif opcode == "delete":
                for k in range(i2 - i1):
                    result.append((i1 + k + 1, 0, lines1[i1 + k], "", "delete"))
            elif opcode == "insert":
                for k in range(j2 - j1):
                    result.append((0, j1 + k + 1, "", lines2[j1 + k], "insert"))
            elif opcode == "replace":
                span = max(i2 - i1, j2 - j1)
                for k in range(span):
                    a = lines1[i1 + k] if i1 + k < i2 else ""
                    b = lines2[j1 + k] if j1 + k < j2 else ""
                    la = i1 + k + 1 if i1 + k < i2 else 0
                    lb = j1 + k + 1 if j1 + k < j2 else 0
                    result.append((la, lb, a, b, "replace"))
        return result

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
