import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QFormLayout, QComboBox, 
                             QTextEdit, QSpinBox, QGroupBox, QFileDialog)
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
        self.pub_input = QLineEdit()
        self.cat_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        
        # --- NAYA: Physical Book Properties ---
        self.size_input = QComboBox()
        self.size_input.addItems(["A5 (Standard Book - 148x210mm)", "A4 (Large - 210x297mm)", "US Trade (6x9 inches)", "Pocket Book (4.25x6.87 inches)"])
        
        self.cover_layout = QHBoxLayout()
        self.cover_input = QLineEdit()
        self.cover_input.setPlaceholderText("No cover selected...")
        self.cover_btn = QPushButton("Browse Image")
        self.cover_btn.clicked.connect(self.browse_cover)
        self.cover_layout.addWidget(self.cover_input)
        self.cover_layout.addWidget(self.cover_btn)

        self.layout.addRow("Book Title:", self.title_input)
        self.layout.addRow("Author:", self.author_input)
        self.layout.addRow("Primary Language:", self.lang_input)
        self.layout.addRow("Physical Size:", self.size_input)
        self.layout.addRow("Cover Design:", self.cover_layout)
        self.layout.addRow("Publisher:", self.pub_input)
        self.layout.addRow("Category:", self.cat_input)
        self.layout.addRow("Notes:", self.notes_input)
        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Create & Initialize Studio")
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
            self.pub_input.setText(book_data.get("publisher") or "")
            self.cat_input.setText(book_data.get("category") or "")
            self.notes_input.setPlainText(book_data.get("notes") or "")
            
            # Load metadata if exists
            metadata = book_data.get("metadata")
            if metadata:
                if isinstance(metadata, str):
                    import json
                    metadata = json.loads(metadata)
                self.size_input.setCurrentText(metadata.get("book_size", "A5 (Standard Book - 148x210mm)"))
                self.cover_input.setText(metadata.get("cover_image", ""))
                
            for label, value in self.LANGUAGE_OPTIONS.items():
                if value == language:
                    self.lang_input.setCurrentText(label)
                    break

    def browse_cover(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Cover Image", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.cover_input.setText(file_path)

    def get_data(self):
        return {
            "title": self.title_input.text(), 
            "author": self.author_input.text(),
            "language": self.LANGUAGE_OPTIONS[self.lang_input.currentText()],
            "publisher": self.pub_input.text(),
            "category": self.cat_input.text(),
            "notes": self.notes_input.toPlainText(),
            "metadata": {
                "book_size": self.size_input.currentText(),
                "cover_image": self.cover_input.text()
            }
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
        self.setWindowTitle("Smart Paste & Auto-Split Document")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(700)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<b>Distraction-Free Smart Parser:</b> Paste your entire document below. It will auto-detect languages and split them into blocks."))
        self.raw_text = QTextEdit()
        self.raw_text.setPlaceholderText("Paste your entire raw document here...\n\nLeave an empty line between paragraphs. Maktaba will automatically split them into distinct blocks and map the languages (Arabic, Urdu, English, Gujarati).")
        self.raw_text.setStyleSheet("font-size: 16px; padding: 15px; line-height: 1.6;")
        self.layout.addWidget(self.raw_text)

        config_group = QGroupBox("Advanced Block Metadata (Optional)")
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
        self.import_btn = QPushButton("⚡ Auto-Split & Import to Chapter")
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
