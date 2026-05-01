"""
Write Mode widget for Maktaba-OS authoring interface.
Implements vertically stacked multilingual editing.
"""

from typing import Any, Callable, Dict, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.commands.command_bus import CommandBus
from core.commands.commands import (
    DeleteNodeCommand,
    InsertNodeCommand,
    MoveNodeCommand,
    ReplaceDocumentCommand,
    ReplaceTextCommand,
)


class LanguageField(QFrame):
    """A collapsible text field for a specific language."""

    def __init__(self, language_name: str, language_code: str, parent=None):
        super().__init__(parent)
        self.language_name = language_name
        self.language_code = language_code
        self.is_expanded = True
        self.init_ui()

    def init_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        header_layout = QHBoxLayout()
        self.label = QLabel(f"{self.language_name} ({self.language_code})")
        self.label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(self.label)
        header_layout.addStretch()

        self.toggle_btn = QPushButton("-")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.clicked.connect(self.toggle_expansion)
        header_layout.addWidget(self.toggle_btn)
        layout.addLayout(header_layout)

        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(60)
        self.text_edit.setMaximumHeight(200)

        font = QFont()
        if self.language_code in ["ar", "ur"]:
            font.setFamily("Arial Unicode MS")
            self.text_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        else:
            font.setFamily("Segoe UI")
        font.setPointSize(11)
        self.text_edit.setFont(font)

        layout.addWidget(self.text_edit)

    def toggle_expansion(self):
        self.is_expanded = not self.is_expanded
        self.text_edit.setVisible(self.is_expanded)
        self.toggle_btn.setText("+" if not self.is_expanded else "-")
        self.text_edit.setMaximumHeight(200 if self.is_expanded else 0)

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def highlight_word(self, word: str, color: QColor = QColor("#ffeb3b")):
        document = self.text_edit.document()
        cursor = QTextCursor(document)

        while word:
            cursor = document.find(word, cursor)
            if cursor.isNull():
                break

            format_highlight = QTextCharFormat()
            format_highlight.setBackground(color)
            cursor.mergeCharFormat(format_highlight)


class ContentBlock(QFrame):
    """A content block containing multilingual fields."""

    content_changed = pyqtSignal()

    def __init__(self, block_type: str = "paragraph", parent=None):
        super().__init__(parent)
        self.block_type = block_type
        self.fields: Dict[str, LanguageField] = {}
        self.drag_start_pos = None
        self.init_ui()

    def init_ui(self):
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(2)
        self.setStyleSheet("QFrame { border: 2px solid #bdc3c7; border-radius: 5px; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header_layout = QHBoxLayout()
        # Add drag handle
        self.drag_handle = QLabel("⋮⋮")
        self.drag_handle.setStyleSheet("font-size: 12px; color: #7f8c8d; padding: 0 5px;")
        self.drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)
        header_layout.addWidget(self.drag_handle)

        self.type_label = QLabel(f"{self.block_type.title()} Block")
        self.type_label.setStyleSheet("font-weight: bold; color: #34495e;")
        header_layout.addWidget(self.type_label)
        header_layout.addStretch()

        self.move_up_btn = QPushButton("Up")
        self.move_up_btn.setFixedSize(44, 25)
        self.move_up_btn.setToolTip("Move block up")
        self.move_up_btn.clicked.connect(self._on_move_up)
        header_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("Down")
        self.move_down_btn.setFixedSize(56, 25)
        self.move_down_btn.setToolTip("Move block down")
        self.move_down_btn.clicked.connect(self._on_move_down)
        header_layout.addWidget(self.move_down_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedSize(64, 25)
        self.delete_btn.setToolTip("Delete block")
        header_layout.addWidget(self.delete_btn)
        layout.addLayout(header_layout)

        self.fields_layout = QVBoxLayout()
        layout.addLayout(self.fields_layout)

        self.add_language_field("Arabic", "ar")
        self.add_language_field("Urdu", "ur")
        self.add_language_field("Gujarati", "gu")
        self.add_language_field("English", "en")

        # Enable drag and drop
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos and (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance():
            # Start drag
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText("content_block")
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.MoveAction)
            self.drag_start_pos = None
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() == "content_block":
            event.acceptProposedAction()
            self.setStyleSheet("QFrame { border: 2px solid #3498db; border-radius: 5px; background-color: #ecf0f1; }")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("QFrame { border: 2px solid #bdc3c7; border-radius: 5px; }")

    def dropEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() == "content_block":
            event.acceptProposedAction()
            # Find the dragged block and move it
            parent = self.parent()
            if hasattr(parent, 'move_block_to_position'):
                dragged_block = event.source()
                if isinstance(dragged_block, ContentBlock):
                    parent.move_block_to_position(dragged_block, self)
        self.setStyleSheet("QFrame { border: 2px solid #bdc3c7; border-radius: 5px; }")

    def add_language_field(self, name: str, code: str):
        field = LanguageField(name, code)
        field.text_edit.textChanged.connect(self.content_changed.emit)
        self.fields[code] = field
        self.fields_layout.addWidget(field)

        if getattr(self, "_last_text_edit", None) is not None:
            self.setTabOrder(self._last_text_edit, field.text_edit)
        self._last_text_edit = field.text_edit

        if not field.get_text().strip():
            field.toggle_expansion()

    def _on_move_up(self):
        if hasattr(self, "move_up_callback") and callable(self.move_up_callback):
            self.move_up_callback()

    def _on_move_down(self):
        if hasattr(self, "move_down_callback") and callable(self.move_down_callback):
            self.move_down_callback()

    def get_content(self) -> Dict[str, str]:
        return {code: field.get_text() for code, field in self.fields.items()}

    def set_content(self, content: Dict[str, str]):
        for code, text in content.items():
            if code in self.fields:
                field = self.fields[code]
                field.set_text(text)
                if text.strip() and not field.is_expanded:
                    field.toggle_expansion()

    def highlight_tajweed(self):
        tajweed_words = ["الله", "رب", "الرحمن"]
        for field in self.fields.values():
            if field.language_code in ["ar", "ur"]:
                for word in tajweed_words:
                    field.highlight_word(word)

    def search_text(self, query: str) -> bool:
        found = False
        for field in self.fields.values():
            if query and query.lower() in field.get_text().lower():
                field.highlight_word(query, QColor("#ffff66"))
                found = True
        return found

    def replace_text(self, query: str, replacement: str) -> int:
        count = 0
        if not query:
            return count

        for field in self.fields.values():
            text = field.get_text()
            next_text = text.replace(query, replacement)
            if next_text != text:
                count += text.count(query)
                field.set_text(next_text)
        return count


class WriteModeWidget(QWidget):
    """Main widget for Write Mode authoring."""

    def __init__(self, command_bus: CommandBus, parent=None):
        super().__init__(parent)
        self.command_bus = command_bus
        self.command_runner: Optional[Callable] = None
        self.current_book_id: Optional[int] = None
        self.blocks: list[ContentBlock] = []
        self._loading = False
        self.is_dirty = False

        self.init_ui()
        self.setup_auto_save()
        self.is_dirty = False

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title_layout = QHBoxLayout()
        title_label = QLabel("Chapter Title:")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        title_layout.addWidget(title_label)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Enter chapter title...")
        self.title_edit.textChanged.connect(self.on_content_changed)
        self.title_edit.setStyleSheet(
            """
            QLineEdit {
                font-size: 16px;
                padding: 8px;
                border: 2px solid #3498db;
                border-radius: 5px;
            }
            """
        )
        title_layout.addWidget(self.title_edit)
        layout.addLayout(title_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)

        scroll_area.setWidget(self.content_widget)
        layout.addWidget(scroll_area)

        toolbar_layout = QHBoxLayout()

        self.add_paragraph_btn = QPushButton("Add Paragraph")
        self.add_paragraph_btn.clicked.connect(self.add_paragraph_block)
        toolbar_layout.addWidget(self.add_paragraph_btn)

        self.add_footnote_btn = QPushButton("Add Footnote")
        self.add_footnote_btn.clicked.connect(self.add_footnote_block)
        toolbar_layout.addWidget(self.add_footnote_btn)

        toolbar_layout.addStretch()

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.show_search_dialog)
        toolbar_layout.addWidget(self.search_btn)

        self.replace_btn = QPushButton("Replace")
        self.replace_btn.clicked.connect(self.show_replace_dialog)
        toolbar_layout.addWidget(self.replace_btn)

        layout.addLayout(toolbar_layout)
        self.add_paragraph_block()

    def setup_auto_save(self):
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(30000)

    def add_paragraph_block(self):
        self.add_block("paragraph")

    def add_footnote_block(self):
        self.add_block("footnote")

    def add_block(self, block_type: str, content: Optional[Dict[str, str]] = None):
        if self._can_run_document_command() and not self._loading:
            command = InsertNodeCommand(
                self.command_bus.document_engine,
                self.current_book_id,
                self._block_to_node_data(block_type, content or {}),
                "root/0",
                index=len(self.blocks),
            )
            self.command_runner(command)
            return

        self._add_block_widget(block_type, content)

    def _add_block_widget(self, block_type: str, content: Optional[Dict[str, str]] = None):
        block = ContentBlock(block_type)
        if content:
            block.set_content(content)
        block.delete_btn.clicked.connect(lambda: self.remove_block(block))
        block.move_up_callback = lambda: self.move_block(block, -1)
        block.move_down_callback = lambda: self.move_block(block, 1)
        block.content_changed.connect(self.on_content_changed)
        self.blocks.append(block)
        self.content_layout.addWidget(block)
        block.highlight_tajweed()
        self.on_content_changed()

    def remove_block(self, block: ContentBlock):
        if block in self.blocks:
            if self._can_run_document_command() and not self._loading:
                index = self.blocks.index(block)
                command = DeleteNodeCommand(
                    self.command_bus.document_engine,
                    self.current_book_id,
                    f"root/0/{index}",
                )
                self.command_runner(command)
                return

            self.blocks.remove(block)
            block.setParent(None)
            block.deleteLater()
            self.on_content_changed()

    def move_block(self, block: ContentBlock, direction: int):
        if block not in self.blocks:
            return

        index = self.blocks.index(block)
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.blocks):
            return

        if self._can_run_document_command() and not self._loading:
            command = MoveNodeCommand(
                self.command_bus.document_engine,
                self.current_book_id,
                "root/0",
                index,
                new_index,
            )
            self.command_runner(command)
            return

        self.blocks.pop(index)
        self.blocks.insert(new_index, block)
        self.content_layout.removeWidget(block)
        self.content_layout.insertWidget(new_index, block)
        self.on_content_changed()

    def move_block_to_position(self, dragged_block: ContentBlock, target_block: ContentBlock):
        """Move a dragged block to the position of the target block."""
        if dragged_block not in self.blocks or target_block not in self.blocks or dragged_block == target_block:
            return

        dragged_index = self.blocks.index(dragged_block)
        target_index = self.blocks.index(target_block)

        if self._can_run_document_command() and not self._loading:
            command = MoveNodeCommand(
                self.command_bus.document_engine,
                self.current_book_id,
                "root/0",
                dragged_index,
                target_index,
            )
            self.command_runner(command)
            return

        self.blocks.pop(dragged_index)
        self.blocks.insert(target_index, dragged_block)
        self.content_layout.removeWidget(dragged_block)
        self.content_layout.insertWidget(target_index, dragged_block)
        self.on_content_changed()

    def on_content_changed(self):
        if not self._loading:
            self.is_dirty = True

    def show_search_dialog(self):
        query, ok = QInputDialog.getText(self, "Search", "Enter search phrase:")
        if not ok or not query.strip():
            return

        found_any = any(block.search_text(query) for block in self.blocks)
        if not found_any:
            QMessageBox.information(self, "Search", f"No matches found for '{query}'.")

    def show_replace_dialog(self):
        query, ok = QInputDialog.getText(self, "Replace", "Find:")
        if not ok or not query:
            return

        replacement, ok = QInputDialog.getText(self, "Replace", "Replace with:")
        if not ok:
            return

        replaced = self.replace_text(query, replacement)
        QMessageBox.information(self, "Replace", f"Replaced {replaced} occurrence(s).")

    def replace_text(self, query: str, replacement: str) -> int:
        if self._can_run_document_command() and not self._loading:
            command = ReplaceTextCommand(
                self.command_bus.document_engine,
                self.current_book_id,
                query,
                replacement,
                "root/0",
            )
            result = self.command_runner(command)
            if result and result.success:
                return result.data.get("replacements", 0)
            return 0

        # LAW 3 WARNING: Fallback mutates UI state without CommandBus. 
        # Acceptable only during initialization/loading phases.
        replaced = sum(block.replace_text(query, replacement) for block in self.blocks)
        if replaced:
            self.on_content_changed()
        return replaced

    def load_chapter(self, book_id: int, chapter_data: Dict[str, Any]):
        self._loading = True
        try:
            self.current_book_id = book_id
            self.title_edit.setText(chapter_data.get("title", ""))

            for block in self.blocks[:]:
                self.remove_block(block)

            for block_data in chapter_data.get("blocks", []):
                if block_data["type"] in ("paragraph", "footnote"):
                    self._add_block_widget(block_data["type"], block_data.get("content", {}))
        finally:
            self._loading = False
            self.is_dirty = False

    def get_chapter_data(self) -> Dict[str, Any]:
        return {
            "title": self.title_edit.text(),
            "blocks": [
                {"type": block.block_type, "content": block.get_content()}
                for block in self.blocks
            ],
        }

    def get_document_dict(self) -> Dict[str, Any]:
        chapter_children = []
        for block in self.blocks:
            block_content = block.get_content()
            chapter_children.append(
                {
                    "type": "multilingual_block",
                    "block_type": block.block_type,
                    "ar": block_content.get("ar", ""),
                    "ur": block_content.get("ur", ""),
                    "gu": block_content.get("gu", ""),
                    "en": block_content.get("en", ""),
                }
            )

        return {
            "type": "document",
            "children": [
                {
                    "type": "chapter",
                    "title": self.title_edit.text(),
                    "children": chapter_children,
                }
            ],
        }

    def save_current_book(self, book_id: int) -> Tuple[bool, Optional[str]]:
        command = ReplaceDocumentCommand(
            self.command_bus.document_engine,
            book_id,
            self.get_document_dict(),
        )
        result = self.command_bus.execute_command_sync(command)
        if result.success:
            self.is_dirty = False
        return result.success, result.error_message

    def _can_run_document_command(self) -> bool:
        return self.current_book_id is not None and self.command_runner is not None

    def _block_to_node_data(self, block_type: str, content: Dict[str, str]) -> Dict[str, str]:
        return {
            "type": "multilingual_block",
            "block_type": block_type,
            "ar": content.get("ar", ""),
            "ur": content.get("ur", ""),
            "gu": content.get("gu", ""),
            "en": content.get("en", ""),
        }

    def auto_save(self):
        """Perform automatic save if content is dirty."""
        if self.is_dirty and self.current_book_id is not None:
            success, error = self.save_current_book(self.current_book_id)
            if not success:
                print(f"Auto-save failed: {error}")  # Could show a status message instead
