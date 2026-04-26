from PyQt6.QtCore import QThread, pyqtSignal
from typing import Callable, Any

class DbWorker(QThread):
    """
    A reusable QThread worker for running database operations off the main UI thread.
    This prevents the UI from freezing during heavy queries or bulk mutations.
    """
    # Emits the result of the database operation on success
    finished = pyqtSignal(object)
    # Emits an exception message if the operation fails
    error = pyqtSignal(str)

    def __init__(self, func: Callable, *args, **kwargs):
        """
        Args:
            func: The database function to execute (e.g., db.get_book_content)
            args: Positional arguments to pass to the function
            kwargs: Keyword arguments to pass to the function
        """
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Execute the passed database function
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))