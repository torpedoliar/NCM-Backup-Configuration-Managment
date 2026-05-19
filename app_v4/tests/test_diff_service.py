from app_v4.core.config import Settings
from app_v4.service.diff_service import DiffService


def test_unified_diff_reports_changes():
    service = DiffService(Settings(diff_context_lines=1))

    diff = service.unified_diff("a\nb\nc\n", "a\nB\nc\n", label1="old", label2="new")

    assert "--- old" in diff
    assert "+++ new" in diff
    assert "-b" in diff
    assert "+B" in diff


def test_diff_stats_counts_replace_as_changed():
    service = DiffService(Settings())

    stats = service.get_diff_stats("a\nb\n", "a\nB\nc\n")

    assert stats == {
        "added_lines": 1,
        "removed_lines": 0,
        "changed_lines": 1,
        "total_changes": 2,
    }
