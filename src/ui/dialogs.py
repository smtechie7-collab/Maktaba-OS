import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QFormLayout, QComboBox, 
                             QTextEdit, QSpinBox, QGroupBox, QFileDialog, QCheckBox)
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
    def __init__(self, parent=None, plugins=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Paste & Auto-Split Document")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(700)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("<b>Distraction-Free Smart Parser:</b> Paste your document below or select a file for custom plugins."))
        
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Optional: Select a document file (.docx, .xml) for custom plugin parsing...")
        self.file_btn = QPushButton("Browse File")
        self.file_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(self.file_btn)
        self.layout.addLayout(file_layout)

        self.raw_text = QTextEdit()
        self.raw_text.setPlaceholderText("Paste your entire raw document here...\n\nLeave an empty line between paragraphs. Maktaba will automatically split them into distinct blocks and map the languages (Arabic, Urdu, English, Gujarati).")
        self.raw_text.setStyleSheet("font-size: 16px; padding: 15px; line-height: 1.6;")
        self.layout.addWidget(self.raw_text)

        config_group = QGroupBox("Advanced Block Metadata (Optional)")
        config_layout = QFormLayout()
        self.separator_input = QLineEdit("\\n\\n")
        
        self.format_combo = QComboBox()
        self.format_combo.addItem("Default (Smart Parse)", None)
        if plugins:
            for name, mod in plugins.items():
                self.format_combo.addItem(f"Plugin: {name.replace('_', ' ').title()}", mod)
                
        self.day_combo = QComboBox()
        self.day_combo.addItems(["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        self.track_combo = QComboBox()
        self.track_combo.addItems(["T1 (Daily Base)", "T2 (Dua Iftitah)", "T3 (Monday Hizb)", "T10 (Shajra)"])
        self.section_combo = QComboBox()
        self.section_combo.addItems(["General", "Muqaddama", "Asma-ul-Husna", "Dua-e-Iftitah", "Hizb", "Shajra"])
        
        config_layout.addRow("Import Format:", self.format_combo)
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

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Document", "", "Word Documents (*.docx);;All Files (*.*)")
        if file_path:
            self.file_input.setText(file_path)

    def get_data(self):
        file_path = getattr(self, 'file_input', QLineEdit()).text().strip()
        return {
            "text": self.raw_text.toPlainText(),
            "file_path": file_path,
            "separator": self.separator_input.text(),
            "format": self.format_combo.currentData(),
            "metadata": {
                "day": self.day_combo.currentText(),
                "track": self.track_combo.currentText().split(" ")[0],
                "section": self.section_combo.currentText(),
                "file_path": file_path
            }
        }

class TemplateBuilderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Template Builder")
        self.setMinimumWidth(500)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QVBoxLayout(self)

        self.layout.addWidget(QLabel("<b>Create Custom Book Theme</b><br><span style='color:#666; font-size:12px;'>Design and export a reusable layout theme for the PDF Print Engine.</span>"))

        form = QFormLayout()
        self.theme_name = QLineEdit("My Custom Theme")
        self.primary_color = QLineEdit("#176B87")
        self.bg_color = QLineEdit("#FFFFFF")
        self.text_color = QLineEdit("#0F172A")
        
        self.arabic_font = QComboBox()
        self.arabic_font.addItems(["Amiri", "Scheherazade New", "Lateef", "Traditional Arabic"])
        self.english_font = QComboBox()
        self.english_font.addItems(["sans-serif", "serif", "Georgia", "Times New Roman"])

        form.addRow("Theme Name:", self.theme_name)
        form.addRow("Primary Color (Hex):", self.primary_color)
        form.addRow("Background Color:", self.bg_color)
        form.addRow("Text Color:", self.text_color)
        form.addRow("Arabic Font:", self.arabic_font)
        form.addRow("English Font:", self.english_font)
        self.layout.addLayout(form)

        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Export Theme")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addLayout(self.buttons)

    def get_theme_data(self):
        return {
            "name": self.theme_name.text().strip(),
            "primary_color": self.primary_color.text(),
            "bg_color": self.bg_color.text(),
            "text_color": self.text_color.text(),
            "arabic_font": self.arabic_font.currentText(),
            "english_font": self.english_font.currentText()
        }

class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Publish & Export Command Center")
        self.setMinimumWidth(500)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QVBoxLayout(self)

        self.layout.addWidget(QLabel("<b>Universal Export Center</b><br><span style='color:#666; font-size:12px;'>Choose your target format and build settings.</span>"))

        self.format_group = QGroupBox("Target Format")
        form_layout = QVBoxLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItem("PDF (Digital / Screen)", "pdf_digital")
        self.format_combo.addItem("PDF (Press-Ready CMYK + Bleed)", "pdf_print")
        self.format_combo.addItem("ePub 3.0 (Digital E-Reader)", "epub")
        self.format_combo.addItem("DOCX (Microsoft Word Manuscript)", "docx")
        
        form_layout.addWidget(self.format_combo)
        self.format_group.setLayout(form_layout)
        self.layout.addWidget(self.format_group)

        self.options_group = QGroupBox("Build Options")
        opt_layout = QVBoxLayout()
        self.tajweed_check = QCheckBox("Render Dynamic Tajweed Rules")
        self.tajweed_check.setChecked(True)
        self.cover_check = QCheckBox("Generate Cover Page")
        self.cover_check.setChecked(True)
        self.footnotes_check = QCheckBox("Include Takhreej / Footnotes")
        self.footnotes_check.setChecked(True)

        opt_layout.addWidget(self.tajweed_check)
        opt_layout.addWidget(self.cover_check)
        opt_layout.addWidget(self.footnotes_check)
        self.options_group.setLayout(opt_layout)
        self.layout.addWidget(self.options_group)

        self.buttons = QHBoxLayout()
        self.export_btn = QPushButton("🚀 Build & Publish")
        self.export_btn.setObjectName("primaryBtn")
        self.export_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.export_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addLayout(self.buttons)

    def get_options(self):
        return {
            "format": self.format_combo.currentData(),
            "enable_tajweed": self.tajweed_check.isChecked(),
            "include_cover": self.cover_check.isChecked(),
            "include_footnotes": self.footnotes_check.isChecked()
        }
