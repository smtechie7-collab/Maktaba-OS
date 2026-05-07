"""
Main window for Maktaba-OS desktop application.
Implements the tri-mode interface using QStackedWidget.
"""

import asyncio
import logging
import os
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

from modules.ai import create_voice_synthesis_agent
from modules.ai import create_content_intelligence_agent
from .write_mode import WriteModeWidget
from modules.interlinear import InterlinearWidget
from .sync_mode import SyncModeWidget
from .publish_mode import PublishModeWidget


logger = logging.getLogger(__name__)


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
        self.voice_agent = self._initialize_voice_agent()
        self.content_agent = self._initialize_content_agent()

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
        self.write_mode = WriteModeWidget(self.command_bus, voice_agent=self.voice_agent, content_agent=self.content_agent)
        self.write_mode.command_runner = self.execute_write_command
        self.write_mode.setStyleSheet("background-color: #f8f9fa;")

        self.sync_mode = SyncModeWidget(self.command_bus)
        self.sync_mode.setStyleSheet("background-color: #e0e0e0;")

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

        # AI menu
        ai_menu = menubar.addMenu('&AI')
        
        footnote_action = QAction('&Add Footnote', self)
        footnote_action.setShortcut('Ctrl+F')
        footnote_action.triggered.connect(self.add_footnote)
        footnote_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(footnote_action)

        citation_action = QAction('&Add Citation', self)
        citation_action.setShortcut('Ctrl+Shift+C')
        citation_action.triggered.connect(self.add_citation)
        citation_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(citation_action)

        outline_action = QAction('&Generate Outline', self)
        outline_action.setShortcut('Ctrl+O')
        outline_action.triggered.connect(self.generate_outline)
        outline_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(outline_action)

        expand_action = QAction('&Expand Content', self)
        expand_action.setShortcut('Ctrl+E')
        expand_action.triggered.connect(self.expand_content)
        expand_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(expand_action)

        summarize_action = QAction('&Summarize Content', self)
        summarize_action.setShortcut('Ctrl+Shift+S')
        summarize_action.triggered.connect(self.summarize_content)
        summarize_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(summarize_action)

        collaborate_action = QAction('&Collaborate', self)
        collaborate_action.setShortcut('Ctrl+L')
        collaborate_action.triggered.connect(self.collaborate)
        collaborate_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(collaborate_action)

        brainstorm_action = QAction('&Brainstorm', self)
        brainstorm_action.setShortcut('Ctrl+B')
        brainstorm_action.triggered.connect(self.brainstorm)
        brainstorm_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(brainstorm_action)

        rewrite_action = QAction('&Rewrite Content', self)
        rewrite_action.setShortcut('Ctrl+R')
        rewrite_action.triggered.connect(self.rewrite_content)
        rewrite_action.setEnabled(False)  # Initially disabled until book is loaded
        ai_menu.addAction(rewrite_action)

        # Store AI actions for enabling/disabling
        self.ai_actions = [footnote_action, citation_action, outline_action, expand_action, summarize_action, collaborate_action, brainstorm_action, rewrite_action]

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
        self.update_ai_actions_state()
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
        self.update_ai_actions_state()

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

    def _initialize_voice_agent(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found; voice synthesis disabled.")
            return None

        try:
            agent = create_voice_synthesis_agent(api_key=api_key)
            asyncio.run(agent.initialize())
            logger.info("Voice synthesis agent initialized successfully")
            return agent
        except Exception as exc:
            logger.warning(f"Voice synthesis agent initialization failed: {exc}")
            return None

    def _initialize_content_agent(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found; AI content features disabled.")
            return None

        try:
            agent = create_content_intelligence_agent(api_key=api_key)
            asyncio.run(agent.initialize())
            logger.info("Content intelligence agent initialized successfully")
            return agent
        except Exception as exc:
            logger.warning(f"Content intelligence agent initialization failed: {exc}")
            return None

    def add_footnote(self):
        """Add a footnote using AI assistance."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.add_ai_footnote()

    def add_citation(self):
        """Add a citation using AI assistance."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.add_ai_citation()

    def generate_outline(self):
        """Generate an outline using AI assistance."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.generate_ai_outline()

    def expand_content(self):
        """Expand content using AI assistance."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.expand_ai_content()

    def summarize_content(self):
        """Summarize content using AI assistance."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.summarize_ai_content()

    def collaborate(self):
        """Start collaborative writing session."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.ai_collaborate()

    def brainstorm(self):
        """Start brainstorming session."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.ai_brainstorm()

    def rewrite_content(self):
        """Rewrite content in a different style."""
        if self.content_agent is None:
            QMessageBox.warning(self, "AI Features", "AI content features are not configured.")
            return
        if self.current_book_id is None:
            QMessageBox.warning(self, "AI Features", "Please open or create a book first.")
            return
        self.write_mode.rewrite_ai_content()

    def update_ai_actions_state(self):
        """Enable/disable AI actions based on book state."""
        enabled = self.current_book_id is not None and self.content_agent is not None
        for action in getattr(self, 'ai_actions', []):
            action.setEnabled(enabled)


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
