"""
Command history for undo/redo functionality.
"""

from typing import List, Optional
from core.commands.commands import Command, CommandResult


class CommandHistory:
    """Manages command history for undo/redo operations."""

    def __init__(self, max_history: int = 100):
        self._history: List[Command] = []
        self._current_index = -1
        self._max_history = max_history

    def execute_and_add(self, command: Command) -> CommandResult:
        """Execute a command and add it to history."""
        result = command.execute()
        if result.success and command.can_undo():
            self._add_to_history(command)
        return result

    def add_executed(self, command: Command):
        """Add an already executed undoable command to history."""
        if command.can_undo():
            self._add_to_history(command)

    def _add_to_history(self, command: Command):
        """Add command to history, removing any commands after current index."""
        # Remove commands after current index (for when undoing then doing new action)
        self._history = self._history[:self._current_index + 1]

        # Add new command
        self._history.append(command)
        self._current_index += 1

        # Limit history size
        if len(self._history) > self._max_history:
            self._history.pop(0)
            self._current_index -= 1

    def undo(self) -> Optional[CommandResult]:
        """Undo the last command."""
        if not self.can_undo():
            return None

        command = self._history[self._current_index]
        result = command.undo()
        if result.success:
            self._current_index -= 1
        return result

    def redo(self) -> Optional[CommandResult]:
        """Redo the next command."""
        if not self.can_redo():
            return None

        self._current_index += 1
        command = self._history[self._current_index]
        result = command.execute()
        if not result.success:
            self._current_index -= 1
        return result

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self._current_index >= 0

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self._current_index < len(self._history) - 1

    def clear(self):
        """Clear all history."""
        self._history.clear()
        self._current_index = -1
