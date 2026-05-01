import os
import sys
from pathlib import Path

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

def user_data_dir() -> Path:
    """Return the base directory for storing user data (DBs, logs)."""
    override = os.environ.get("MAKTABA_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def database_path() -> Path:
    override = os.environ.get("MAKTABA_DB_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return ensure_dir(user_data_dir()) / "maktaba_store.db"

def logs_dir() -> Path:
    override = os.environ.get("MAKTABA_LOG_DIR")
    if override:
        return ensure_dir(Path(override).expanduser().resolve())
    return ensure_dir(user_data_dir() / "logs")

def template_dir() -> Path:
    """Points to the new assets/templates directory."""
    return project_root() / "assets" / "templates"

def fonts_dir() -> Path:
    """Points to the new assets/fonts directory."""
    return project_root() / "assets" / "fonts"