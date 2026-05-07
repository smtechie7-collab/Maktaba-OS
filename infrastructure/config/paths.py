import os
import sys
from pathlib import Path
from typing import Optional

APP_NAME = "Maktaba-OS"

def is_frozen() -> bool:
    """Check if the application is running as a bundled executable."""
    return bool(getattr(sys, "frozen", False))

def project_root() -> Path:
    """Return the absolute path to the project root directory."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    # Resolves from infrastructure/config/paths.py up to the root maktaba-os/
    return Path(__file__).resolve().parents[2]

def _get_env_path(env_var: str) -> Optional[Path]:
    """Helper to safely fetch and resolve paths from environment variables."""
    override = os.environ.get(env_var)
    return Path(override).expanduser().resolve() if override else None

def user_data_dir() -> Path:
    """Return the base directory for storing user data (DBs, logs)."""
    if override := _get_env_path("MAKTABA_DATA_DIR"):
        return override

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def database_path() -> Path:
    if override := _get_env_path("MAKTABA_DB_PATH"):
        return override
    return ensure_dir(user_data_dir()) / "maktaba_store.db"

def logs_dir() -> Path:
    if override := _get_env_path("MAKTABA_LOG_DIR"):
        return ensure_dir(override)
    return ensure_dir(user_data_dir() / "logs")

def template_dir() -> Path:
    """Points to the new assets/templates directory."""
    return project_root() / "assets" / "templates"

def fonts_dir() -> Path:
    """Points to the new assets/fonts directory."""
    return project_root() / "assets" / "fonts"