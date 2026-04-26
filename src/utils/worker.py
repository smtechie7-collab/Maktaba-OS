import sys
import traceback
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    - finished: Emitted when the job completes (success or failure)
    - error: Emitted on exception with tuple (exctype, value, traceback.format_exc())
    - result: Emitted on success with the object data returned from the processing function
    - progress: Emitted to update progress bars with an int percentage
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    """
    Worker thread setup for executing database queries and file I/O 
    in the background. This ensures the PyQt6 UI (Maktaba-OS Dashboard) 
    remains 100% responsive, conforming to the project Constitution.
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """
        Initializes the runner function with the passed arguments.
        """
        try:
            # Execute the targeted function
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()      # Signal that the thread is done