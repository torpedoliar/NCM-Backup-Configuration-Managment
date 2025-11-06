"""Configuration module"""
import sys
import shutil
from pathlib import Path


def get_config_path() -> Path:
    """
    Get the correct path to appsettings.yaml that is writable.
    For PyInstaller builds, copies default config to app directory on first run.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        # Config should be in the same directory as the executable
        exe_dir = Path(sys.executable).parent
        user_config = exe_dir / "config" / "appsettings.yaml"
        
        # If user config doesn't exist, copy from bundled default
        if not user_config.exists():
            bundled_config = Path(sys._MEIPASS) / "app" / "config" / "appsettings.yaml"
            user_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_config, user_config)
        
        return user_config
    else:
        # Running from source - use the source config
        base_path = Path(__file__).parent.parent.parent
        return base_path / "app" / "config" / "appsettings.yaml"
