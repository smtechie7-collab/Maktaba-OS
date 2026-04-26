from dataclasses import dataclass
from pathlib import Path

from src.core.paths import database_path, logs_dir, output_dir, template_dir


@dataclass(frozen=True)
class AppConfig:
    db_path: Path
    log_dir: Path
    output_dir: Path
    template_dir: Path


def load_config() -> AppConfig:
    return AppConfig(
        db_path=database_path(),
        log_dir=logs_dir(),
        output_dir=output_dir(),
        template_dir=template_dir(),
    )
