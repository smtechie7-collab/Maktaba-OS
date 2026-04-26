from pathlib import Path

from src.core.paths import resource_path


def load_stylesheet(name: str) -> str:
    path = resource_path("src", "ui", "styles", name)
    return Path(path).read_text(encoding="utf-8")
