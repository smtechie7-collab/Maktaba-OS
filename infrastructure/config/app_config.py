from dataclasses import dataclass
from pathlib import Path

from .paths import database_path, logs_dir, template_dir, fonts_dir

@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration state for the application environment."""
    db_path: Path
    log_dir: Path
    template_dir: Path
    fonts_dir: Path
    debug_mode: bool = False

def load_config() -> AppConfig:
    """Loads the core environment configuration."""
    return AppConfig(
        db_path=database_path(),
        log_dir=logs_dir(),
        template_dir=template_dir(),
        fonts_dir=fonts_dir(),
    )