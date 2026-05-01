"""
Main window for Maktaba-OS desktop application.
Implements the tri-mode interface using QStackedWidget.
"""

import sys
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
    QMenuBar, QStatusBar, QLabel, QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QAction

from infrastructure.config.app_config import load_config
from infrastructure.database.manager import DatabaseManager

from core.engine.document_engine import DocumentEngine
from core.commands.command_bus import CommandBus
from core.commands.command_history import CommandHistory
from core.commands.commands import ReplaceDocumentCommand, CreateBookCommand

from .write_mode import WriteModeWidget
from modules.interlinear import InterlinearWidget
from .sync_mode import SyncModeWidget
from .publish_mode import PublishModeWidget


class MainWindow(QMainWindow):
    """Main application window with tri-mode interface."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.db_manager = DatabaseManager(self.config.db_path)
        self.document_engine = DocumentEngine(self.db_manager)
        self.command_bus = CommandBus(self.document_engine)
        self.command_bus.start()
        self.command_history = CommandHistory()
        self.current_book_id: Optional[int] = None

        self.init_ui()
        self.setup_menus()
        self.setup_status_bar()

    def init_ui(self):
        """Initialize the main UI components."""
        self.setWindowTitle("Maktaba-OS Zen Studio")
        self.setGeometry(100, 100, 1200, 800)

        # Create central widget with stacked layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        # Create mode widgets
        self.write_mode = WriteModeWidget(self.command_bus)
        self.write_mode.command_runner = self.execute_write_command
        self.write_mode.setStyleSheet("background-color: #f8f9fa;")

        self.sync_mode = SyncModeWidget(self.command_bus)
        self.sync_mode.setStyleSheet("background-color: #e0e0e0;")

        self.publish_mode = QWidget()
        self.publish_mode.setStyleSheet("background-color: #d0d0d0;")
        publish_label = QLabel("Publish Mode - Coming Soon")
        publish_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        publish_layout = QVBoxLayout(self.publish_mode)
        publish_layout.addWidget(publish_label)
        self.publish_mode = PublishModeWidget(self.command_bus)
        self.publish_mode.setStyleSheet("background-color: #f5f6fa;")

        # Add modes to stack
        self.stacked_widget.addWidget(self.write_mode)    # Index 0
        self.stacked_widget.addWidget(self.sync_mode)     # Index 1
        self.stacked_widget.addWidget(self.publish_mode)  # Index 2

        # Start with Write mode
        self.stacked_widget.setCurrentIndex(0)

    def setup_menus(self):
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('&File')
        new_action = QAction('&New Book', self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self.create_new_book)
        file_menu.addAction(new_action)

        open_action = QAction('&Open Book', self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_book)
        file_menu.addAction(open_action)

        save_action = QAction('&Save', self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_book)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction('E&xit', self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu('&Edit')
        undo_action = QAction('&Undo', self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self.undo_command)
        undo_action.setEnabled(False)  # Initially disabled
        edit_menu.addAction(undo_action)

        redo_action = QAction('&Redo', self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self.redo_command)
        redo_action.setEnabled(False)  # Initially disabled
        edit_menu.addAction(redo_action)

        # Store actions for enabling/disabling
        self.undo_action = undo_action
        self.redo_action = redo_action

        # View menu
        view_menu = menubar.addMenu('&View')
        write_mode_action = QAction('&Write Mode', self)
        write_mode_action.setShortcut('Ctrl+1')
        write_mode_action.triggered.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        view_menu.addAction(write_mode_action)

        sync_mode_action = QAction('&Sync Mode', self)
        sync_mode_action.setShortcut('Ctrl+2')
        sync_mode_action.triggered.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        view_menu.addAction(sync_mode_action)

        publish_mode_action = QAction('&Publish Mode', self)
        publish_mode_action.setShortcut('Ctrl+3')
        publish_mode_action.triggered.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        view_menu.addAction(publish_mode_action)

    def setup_status_bar(self):
        """Setup the status bar."""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

        # Add mode indicator
        self.mode_label = QLabel("Write Mode")
        self.status_bar.addPermanentWidget(self.mode_label)

        self.book_label = QLabel("Book: None")
        self.status_bar.addPermanentWidget(self.book_label)

        # Connect stack changes to update status
        self.stacked_widget.currentChanged.connect(self.update_status_mode)

    def update_status_mode(self, index):
        """Update status bar when mode changes."""
        modes = ["Write Mode", "Sync Mode", "Publish Mode"]
        self.mode_label.setText(modes[index])

    def update_book_status(self):
        title = self.write_mode.title_edit.text().strip()
        if self.current_book_id is None:
            self.book_label.setText("Book: None")
        else:
            display_title = title or f"Book #{self.current_book_id}"
            self.book_label.setText(f"Book: {display_title}")

    def create_new_book(self):
        """Create a new book and reset the editor."""
        title, ok = QInputDialog.getText(self, "New Book", "Enter book title:")
        if not ok or not title.strip():
            return

        author, _ = QInputDialog.getText(self, "New Book", "Enter author name (optional):")

        # Adhere to LAW 3: UI sends commands, does not execute logic.
        create_book_cmd = CreateBookCommand(
            self.document_engine,
            title=title.strip(),
            author=author.strip() if author else None
        )
        create_result = self.command_bus.execute_command_sync(create_book_cmd)

        if not create_result.success:
            QMessageBox.critical(self, "New Book", f"Could not create book: {create_result.error_message}")
            return

        book_id = create_result.data['book_id']
        self.command_history.clear()
        self.command_history.add_executed(create_book_cmd) # Start history with creation

        # Initialize the book with a default chapter structure
        init_doc_cmd = ReplaceDocumentCommand(
            self.document_engine,
            book_id,
            {
                "type": "document",
                "children": [
                    {"type": "chapter", "title": title.strip(), "children": [
                        {"type": "multilingual_block", "block_type": "paragraph",
                         "ar": "", "ur": "", "gu": "", "en": ""}
                    ]}
                ],
            },
        )
        init_result = self.command_bus.execute_command_sync(init_doc_cmd)
        if not init_result.success:
            QMessageBox.critical(self, "New Book", f"Could not initialize book: {init_result.error_message}")
            return

        self.current_book_id = book_id
        self.write_mode.current_book_id = book_id
        self.reload_current_book()
        self.update_undo_redo_state()
        self.update_book_status()
        QMessageBox.information(self, "New Book", f"Created new book '{title.strip()}' with ID {book_id}.")

    def open_book(self):
        """Open an existing book from the database."""
        # Adhere to LAW 4: No direct UI->DB coupling. Go through the engine.
        books = self.document_engine.list_books()
        if not books:
            QMessageBox.information(self, "Open Book", "No books found in the database.")
            return

        items = [f"{book['id']}: {book['title']} ({book.get('author', 'N/A')})" for book in books]
        selection, ok = QInputDialog.getItem(self, "Open Book", "Select a book:", items, 0, False)
        if not ok or not selection:
            return

        book_id = int(selection.split(":")[0])
        document = self.document_engine.load_document(book_id)
        if document is None or not document.children:
            QMessageBox.warning(self, "Open Book", "Selected book has no valid chapter content.")
            return

        chapter = document.children[0]
        chapter_data = {
            'title': chapter.title,
            'blocks': []
        }
        for child in chapter.children:
            if child.type == 'multilingual_block':
                chapter_data['blocks'].append({
                    'type': child.block_type,
                    'content': {
                        'ar': getattr(child, 'ar', ''),
                        'ur': getattr(child, 'ur', ''),
                        'gu': getattr(child, 'gu', ''),
                        'en': getattr(child, 'en', ''),
                    }
                })
            elif child.type == 'paragraph':
                chapter_data['blocks'].append({
                    'type': 'paragraph',
                    'content': {'en': getattr(child, 'text', '')}
                })
            elif child.type == 'footnote':
                chapter_data['blocks'].append({
                    'type': 'footnote',
                    'content': {'en': getattr(child, 'content', '')}
                })

        self.current_book_id = book_id
        self.command_history.clear()
        self.write_mode.load_chapter(book_id, chapter_data)
        self.sync_mode.load_book(book_id)
        self.publish_mode.load_book(book_id)
        self.update_undo_redo_state()
        self.update_book_status()

    def save_book(self):
        """Save the current document back to the database."""
        if self.current_book_id is None:
            QMessageBox.warning(self, "Save", "Please create or open a book first.")
            return

        command = ReplaceDocumentCommand(
            self.document_engine,
            self.current_book_id,
            self.write_mode.get_document_dict(),
        )
        result = self.command_bus.execute_command_sync(command)
        if result.success:
            self.command_history.add_executed(command)
            self.update_undo_redo_state()
            QMessageBox.information(self, "Save", "Book saved successfully.")
        else:
            QMessageBox.critical(self, "Save Failed", f"Could not save book: {result.error_message}")

    def undo_command(self):
        """Handle undo action."""
        result = self.command_history.undo()
        if result and result.success:
            self.reload_current_book()
            self.update_undo_redo_state()
        elif result:
            QMessageBox.critical(self, "Undo Failed", result.error_message or "Could not undo command.")

    def redo_command(self):
        """Handle redo action."""
        result = self.command_history.redo()
        if result and result.success:
            self.reload_current_book()
            self.update_undo_redo_state()
        elif result:
            QMessageBox.critical(self, "Redo Failed", result.error_message or "Could not redo command.")

    def update_undo_redo_state(self):
        """Update the enabled state of undo/redo actions."""
        self.undo_action.setEnabled(self.command_history.can_undo())
        self.redo_action.setEnabled(self.command_history.can_redo())

    def show_error(self, title: str, message: str):
        """Show an error message dialog."""
        QMessageBox.critical(self, title, message)

    def execute_write_command(self, command):
        """Execute a Write Mode command, record it, and refresh the editor."""
        result = self.command_bus.execute_command_sync(command)
        if result.success:
            self.command_history.add_executed(command)
            self.reload_current_book()
            self.update_undo_redo_state()
        else:
            QMessageBox.critical(self, "Command Failed", result.error_message or "Could not complete command.")
        return result

    def reload_current_book(self):
        """Reload the active book from persistence into the write mode."""
        if self.current_book_id is None:
            return

        document = self.document_engine.load_document(self.current_book_id)
        if document is None or not document.children:
            return

        chapter = document.children[0]
        chapter_data = {
            'title': chapter.title,
            'blocks': []
        }
        for child in chapter.children:
            if child.type == 'multilingual_block':
                chapter_data['blocks'].append({
                    'type': child.block_type,
                    'content': {
                        'ar': getattr(child, 'ar', ''),
                        'ur': getattr(child, 'ur', ''),
                        'gu': getattr(child, 'gu', ''),
                        'en': getattr(child, 'en', ''),
                    }
                })

        self.write_mode.load_chapter(self.current_book_id, chapter_data)
        self.sync_mode.load_book(self.current_book_id)
        self.publish_mode.load_book(self.current_book_id)
        self.update_book_status()

    def closeEvent(self, event):
        self.command_bus.stop()
        super().closeEvent(event)


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Maktaba-OS")
    app.setApplicationVersion("5.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
