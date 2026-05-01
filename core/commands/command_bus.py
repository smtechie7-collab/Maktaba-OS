"""
Command Bus for routing commands to the appropriate handlers.
Maintains separation between UI and core engine.
"""

from typing import Dict, Type, Any, Optional, Optional
from queue import Queue, Empty
import threading
import time

from core.commands.commands import Command, CommandResult
from core.engine.document_engine import DocumentEngine


class CommandBus:
    """Central command routing system."""

    def __init__(self, document_engine: DocumentEngine):
        self.document_engine = document_engine
        self._command_queue: Queue = Queue()
        self._result_callbacks: Dict[str, callable] = {}
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the command processing thread."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._process_commands, daemon=True)
        self._worker_thread.start()

    def stop(self):
        """Stop the command processing."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1.0)

    def execute_command(self, command: Command, callback: Optional[callable] = None) -> str:
        """
        Execute a command asynchronously.

        Args:
            command: The command to execute
            callback: Optional callback for result (result: CommandResult)

        Returns:
            Command ID for tracking
        """
        command_id = f"cmd_{int(time.time() * 1000000)}"
        if callback:
            self._result_callbacks[command_id] = callback

        self._command_queue.put((command_id, command))
        return command_id

    def execute_command_sync(self, command: Command) -> CommandResult:
        """
        Execute a command synchronously.

        Args:
            command: The command to execute

        Returns:
            CommandResult
        """
        return command.execute()

    def _process_commands(self):
        """Background thread for processing commands."""
        while self._running:
            try:
                # Non-blocking queue get with timeout
                if not self._command_queue.empty():
                    item = self._command_queue.get_nowait()
                    if item:
                        command_id, command = item
                        result = command.execute()

                        # Call callback if registered
                        if command_id in self._result_callbacks:
                            try:
                                self._result_callbacks[command_id](result)
                            except Exception as e:
                                print(f"Error in command callback: {e}")
                            finally:
                                del self._result_callbacks[command_id]

                        self._command_queue.task_done()
                else:
                    time.sleep(0.1)  # Sleep briefly when queue is empty

            except Exception as e:
                print(f"Error processing command: {e}")
                import traceback
                traceback.print_exc()
                continue

    def get_queue_size(self) -> int:
        """Get the number of pending commands."""
        return self._command_queue.qsize()

    def clear_pending_commands(self):
        """Clear all pending commands."""
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
                self._command_queue.task_done()
            except:
                break