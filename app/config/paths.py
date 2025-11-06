from pathlib import Path
import sys
import os


def _sanitize_path_value(value: str) -> str:
    return value.strip().strip('"').strip("'")


def get_base_dir() -> Path:
    override = os.environ.get('ATBM_BASE_DIR')
    if override:
        p = _sanitize_path_value(override)
        if p:
            return Path(p)
    try:
        program_data = os.environ.get('PROGRAMDATA') or r"C:\\ProgramData"
        override_file = Path(program_data) / "ATBM" / "base_dir.txt"
        if override_file.exists():
            p = _sanitize_path_value(override_file.read_text(encoding='utf-8'))
            if p:
                candidate = Path(p)
                if getattr(sys, 'frozen', False):
                    return Path(sys.executable).parent
                return candidate
    except Exception:
        pass
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent
