import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QFormLayout, QComboBox, 
                             QTextEdit, QSpinBox, QGroupBox)
from PyQt6.QtCore import Qt
from src.ui.styles.style_loader import load_stylesheet

DIALOG_STYLE = load_stylesheet("dialogs.qss")

class BookDialog(QDialog):
    LANGUAGE_OPTIONS = {
        "Arabic": "ar",
        "Urdu": "ur",
        "English": "en",
        "Multilingual": "multi",
    }

    def __init__(self, parent=None, book_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Book" if book_data else "Add New Book")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QFormLayout(self)
        self.title_input = QLineEdit()
        self.author_input = QLineEdit()
        self.lang_input = QComboBox()
        self.lang_input.addItems(list(self.LANGUAGE_OPTIONS.keys()))
        self.layout.addRow("Book Title:", self.title_input)
        self.layout.addRow("Author:", self.author_input)
        self.layout.addRow("Primary Language:", self.lang_input)
        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save Book")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)
        if book_data:
            self.title_input.setText(book_data.get("title") or "")
            self.author_input.setText(book_data.get("author") or "")
            language = book_data.get("language") or "en"
            for label, value in self.LANGUAGE_OPTIONS.items():
                if value == language:
                    self.lang_input.setCurrentText(label)
                    break

    def get_data(self):
        return {
            "title": self.title_input.text(), "author": self.author_input.text(),
            "language": self.LANGUAGE_OPTIONS[self.lang_input.currentText()]
        }

class ChapterDialog(QDialog):
    def __init__(self, parent=None, chapter_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Book Element" if chapter_data else "Add Book Element")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QFormLayout(self)
        
        # NAYA DROPDOWN: Book Anatomy Type
        self.type_input = QComboBox()
        self.type_input.addItems(["Content Chapter", "Cover Page", "Title Page", "Muqaddama (Preface)", "Back Cover"])

        self.title_input = QLineEdit()
        self.seq_input = QSpinBox()
        self.seq_input.setMinimum(1)
        self.seq_input.setMaximum(1000)

        self.layout.addRow("Element Type:", self.type_input)
        self.layout.addRow("Element Title:", self.title_input)
        self.layout.addRow("Sequence (Order):", self.seq_input)

        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Add Element")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)
        if chapter_data:
            self.type_input.setCurrentText(chapter_data.get("chapter_type") or "Content Chapter")
            self.title_input.setText(chapter_data.get("title") or "")
            self.seq_input.setValue(int(chapter_data.get("sequence_number") or 1))

    def get_data(self):
        return {
            "title": self.title_input.text(), 
            "sequence": self.seq_input.value(),
            "type": self.type_input.currentText()
        }

class BulkImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import - Smart Text Converter")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<b>Smart Parser:</b> Auto-detects Arabic, Urdu, Gujarati, and English."))
        self.raw_text = QTextEdit()
        self.raw_text.setPlaceholderText("Paste Dalail text here... (Leave an empty line between blocks)")
        self.layout.addWidget(self.raw_text)

        config_group = QGroupBox("Import Configuration")
        config_layout = QFormLayout()
        self.separator_input = QLineEdit("\\n\\n")
        self.day_combo = QComboBox()
        self.day_combo.addItems(["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        self.track_combo = QComboBox()
        self.track_combo.addItems(["T1 (Daily Base)", "T2 (Dua Iftitah)", "T3 (Monday Hizb)", "T10 (Shajra)"])
        self.section_combo = QComboBox()
        self.section_combo.addItems(["General", "Muqaddama", "Asma-ul-Husna", "Dua-e-Iftitah", "Hizb", "Shajra"])
        
        config_layout.addRow("Block Separator:", self.separator_input)
        config_layout.addRow("Assign Day:", self.day_combo)
        config_layout.addRow("Assign Track:", self.track_combo)
        config_layout.addRow("Assign Section:", self.section_combo)
        config_group.setLayout(config_layout)
        self.layout.addWidget(config_group)

        self.buttons = QHBoxLayout()
        self.import_btn = QPushButton("🚀 Start Smart Import")
        self.import_btn.setObjectName("primaryBtn")
        self.import_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.import_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addLayout(self.buttons)

    def get_data(self):
        return {
            "text": self.raw_text.toPlainText(),
            "separator": self.separator_input.text(),
            "metadata": {
                "day": self.day_combo.currentText(),
                "track": self.track_combo.currentText().split(" ")[0],
                "section": self.section_combo.currentText()
            }
        }
