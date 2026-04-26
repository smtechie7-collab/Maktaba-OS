import sys
import traceback

from src.core.paths import logs_dir
from src.utils.logger import setup_logger


logger = setup_logger("CrashHandler")


def install_global_exception_handler() -> None:
    sys.excepthook = handle_uncaught_exception


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    trace = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical("Uncaught application error:\n%s", trace)
    _show_crash_dialog(str(exc_value))


def _show_crash_dialog(message: str) -> None:
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return

        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle("Maktaba-OS Error")
        dialog.setText("Something went wrong, but the error was logged.")
        dialog.setInformativeText(f"{message}\n\nLog folder:\n{logs_dir()}")
        dialog.exec()
    except Exception:
        sys.__stderr__.write(f"Fatal error: {message}\n")
