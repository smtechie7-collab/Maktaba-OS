import os
import sys
from pathlib import Path


APP_NAME = "Maktaba-OS"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return project_root().joinpath(*parts)


def user_data_dir() -> Path:
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
    return ensure_dir(user_data_dir()) / "maktaba_production.db"


def logs_dir() -> Path:
    override = os.environ.get("MAKTABA_LOG_DIR")
    if override:
        return ensure_dir(Path(override).expanduser().resolve())
    return ensure_dir(user_data_dir() / "logs")


def output_dir() -> Path:
    override = os.environ.get("MAKTABA_OUTPUT_DIR")
    if override:
        return ensure_dir(Path(override).expanduser().resolve())
    return ensure_dir(user_data_dir() / "output")


def template_dir() -> Path:
    return resource_path("src", "layout", "templates")


def binary_path(name: str) -> Path:
    return resource_path("bin", name)
