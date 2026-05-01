"""
InterlinearWidget for displaying word bundles in linguistic glossing format.
Implements interactive token blob alignment for user-friendly translation UI.
"""

from typing import List, Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QScrollArea, QFrame, QPushButton, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QFont, QDragEnterEvent, QDropEvent, QMouseEvent

from core.schema.document import InterlinearToken


class TokenBlob(QFrame):
    """Draggable token blob representing a single word/morpheme."""

    drag_started = pyqtSignal(object)  # Emits self when drag begins

    def __init__(self, token: InterlinearToken, parent=None):
        super().__init__(parent)
        self.token = token
        self.setFrameStyle(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet("""
            TokenBlob {
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: #ecf0f1;
                padding: 2px;
                margin: 1px;
            }
            TokenBlob:hover {
                background-color: #d5dbdb;
                border-color: #3498db;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(1)

        # Source text (L1)
        self.source_label = QLabel(token.source_l1)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.source_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.source_label)

        # Transliteration (L2)
        if token.transliteration_l2:
            self.translit_label = QLabel(token.transliteration_l2)
            self.translit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.translit_label.setStyleSheet("font-style: italic; color: #7f8c8d;")
            layout.addWidget(self.translit_label)

        # Translation (L3)
        if token.translation_l3:
            self.translation_label = QLabel(token.translation_l3)
            self.translation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.translation_label.setStyleSheet("color: #27ae60;")
            layout.addWidget(self.translation_label)

        self.setAcceptDrops(True)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit(self)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText() and event.mimeData().text() == "token_blob":
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        # Handle token reordering
        event.acceptProposedAction()


class InterlinearWidget(QWidget):
    """Main widget for displaying interlinear text with interactive alignment."""

    content_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tokens: List[InterlinearToken] = []
        self.dragged_token: Optional[TokenBlob] = None
        self.zoom_level = 1.0

        self.init_ui()

    def init_ui(self):
        """Initialize the interlinear display UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Interlinear Text")
        header_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(header_label)

        # Validation status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        # Zoom controls
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedSize(25, 25)
        zoom_out_btn.setToolTip("Zoom out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        header_layout.addWidget(zoom_out_btn)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("font-weight: bold; min-width: 40px; text-align: center;")
        header_layout.addWidget(self.zoom_label)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedSize(25, 25)
        zoom_in_btn.setToolTip("Zoom in")
        zoom_in_btn.clicked.connect(self.zoom_in)
        header_layout.addWidget(zoom_in_btn)

        header_layout.addStretch()

        self.add_token_btn = QPushButton("➕ Add Token")
        self.add_token_btn.clicked.connect(self.add_empty_token)
        header_layout.addWidget(self.add_token_btn)

        layout.addLayout(header_layout)

        # Scrollable token area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.token_container = QWidget()
        self.token_layout = QHBoxLayout(self.token_container)
        self.token_layout.setSpacing(5)
        self.token_layout.setContentsMargins(5, 5, 5, 5)

        scroll_area.setWidget(self.token_container)
        layout.addWidget(scroll_area)

        # Translation input area
        translation_layout = QHBoxLayout()

        translation_label = QLabel("Translation:")
        translation_layout.addWidget(translation_label)

        self.translation_edit = QTextEdit()
        self.translation_edit.setMaximumHeight(60)
        self.translation_edit.setPlaceholderText("Enter overall translation...")
        self.translation_edit.textChanged.connect(self.content_changed.emit)
        translation_layout.addWidget(self.translation_edit)

        layout.addLayout(translation_layout)

    def add_token(self, token: InterlinearToken):
        """Add a token blob to the display."""
        blob = TokenBlob(token)
        blob.drag_started.connect(self.on_token_drag_started)

        self.tokens.append(token)
        self.token_layout.addWidget(blob)

        self.content_changed.emit()
        self.update_validation_status()

    def add_empty_token(self):
        """Add an empty token for user input."""
        empty_token = InterlinearToken(
            source_l1="",
            transliteration_l2="",
            translation_l3=""
        )
        self.add_token(empty_token)

    def remove_token(self, token: InterlinearToken):
        """Remove a token from the display."""
        if token in self.tokens:
            self.tokens.remove(token)
            # Find and remove the corresponding widget
            for i in range(self.token_layout.count()):
                widget = self.token_layout.itemAt(i).widget()
                if isinstance(widget, TokenBlob) and widget.token == token:
                    widget.setParent(None)
                    widget.deleteLater()
                    break
            self.content_changed.emit()
            self.update_validation_status()

    def on_token_drag_started(self, token_blob: TokenBlob):
        """Handle the start of a token drag operation."""
        self.dragged_token = token_blob
        # TODO: Implement drag and drop reordering

    def get_tokens(self) -> List[InterlinearToken]:
        """Get the current list of tokens."""
        return self.tokens.copy()

    def set_tokens(self, tokens: List[InterlinearToken]):
        """Set the tokens to display."""
        # Clear existing tokens
        for i in reversed(range(self.token_layout.count())):
            widget = self.token_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.tokens = []
        for token in tokens:
            self.add_token(token)

    def get_translation(self) -> str:
        """Get the overall translation text."""
        return self.translation_edit.toPlainText()

    def set_translation(self, text: str):
        """Set the overall translation text."""
        self.translation_edit.setPlainText(text)

    def highlight_tajweed(self):
        """Apply Tajweed highlighting to Arabic tokens."""
        # Similar to WriteModeWidget highlighting
        tajweed_words = ["ٱللَّه", "رَبِّ", "ٱلرَّحْمَٰن"]

        for i in range(self.token_layout.count()):
            widget = self.token_layout.itemAt(i).widget()
            if isinstance(widget, TokenBlob):
                for word in tajweed_words:
                    if word in widget.token.source_l1:
                        widget.setStyleSheet("""
                            TokenBlob {
                                border: 2px solid #e74c3c;
                                background-color: #fadbd8;
                            }
                        """)
                        break

    def zoom_in(self):
        """Increase zoom level."""
        if self.zoom_level < 2.0:
            self.zoom_level += 0.25
            self.update_zoom()

    def zoom_out(self):
        """Decrease zoom level."""
        if self.zoom_level > 0.5:
            self.zoom_level -= 0.25
            self.update_zoom()

    def update_zoom(self):
        """Update the zoom level display and apply to all tokens."""
        self.zoom_label.setText(f"{int(self.zoom_level * 100)}%")

        # Apply zoom to all token blobs
        font_size = int(11 * self.zoom_level)
        for i in range(self.token_layout.count()):
            widget = self.token_layout.itemAt(i).widget()
            if isinstance(widget, TokenBlob):
                # Update font sizes
                font = widget.source_label.font()
                font.setPointSize(font_size)
                widget.source_label.setFont(font)

                if hasattr(widget, 'translit_label'):
                    widget.translit_label.setFont(font)
                if hasattr(widget, 'translation_label'):
                    widget.translation_label.setFont(font)

        # Update translation edit font
        trans_font = self.translation_edit.font()
        trans_font.setPointSize(int(11 * self.zoom_level))
        self.translation_edit.setFont(trans_font)

    def validate_tokens(self) -> List[str]:
        """Validate the current token alignments and return warnings."""
        warnings = []

        if not self.tokens:
            warnings.append("No tokens in interlinear text")
            return warnings

        empty_sources = sum(1 for t in self.tokens if not t.source_l1.strip())
        if empty_sources > 0:
            warnings.append(f"{empty_sources} tokens have empty source text")

        empty_translations = sum(1 for t in self.tokens if not t.translation_l3.strip())
        if empty_translations > len(self.tokens) * 0.5:  # More than 50% empty
            warnings.append("Many tokens have empty translations")

        # Check for potential alignment issues
        long_translations = [t for t in self.tokens if len(t.translation_l3.split()) > 3]
        if long_translations:
            warnings.append(f"{len(long_translations)} tokens have unusually long translations")

        # Check for Arabic tokens without transliteration
        arabic_without_translit = [t for t in self.tokens
                                  if any('\u0600' <= c <= '\u06ff' for c in t.source_l1)
                                  and not t.transliteration_l2.strip()]
        if arabic_without_translit:
            warnings.append(f"{len(arabic_without_translit)} Arabic tokens missing transliteration")

        return warnings

    def get_validation_status(self) -> str:
        """Get a summary of validation status."""
        warnings = self.validate_tokens()
        if not warnings:
            return "✓ All validations passed"
        else:
            return f"⚠ {len(warnings)} validation issues"

    def update_validation_status(self):
        """Update the validation status display."""
        status = self.get_validation_status()
        self.status_label.setText(status)

        # Update color based on status
        if "✓" in status:
            self.status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
        else:
            self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")