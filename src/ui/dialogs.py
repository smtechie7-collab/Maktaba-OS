import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QFormLayout, QComboBox, 
                             QTextEdit, QSpinBox, QGroupBox)
from PyQt6.QtCore import Qt

DIALOG_STYLE = """
    QDialog { background-color: #F3F4F6; color: #000000; }
    QLabel { color: #000000; font-weight: bold; font-size: 13px; }
    QLineEdit, QTextEdit, QSpinBox, QComboBox { 
        background-color: #FFFFFF; color: #000000; font-weight: bold; font-size: 13px;
        border: 2px solid #A0A0A0; border-radius: 4px; padding: 6px;
    }
    QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus { border: 2px solid #0066CC; }
    QPushButton { 
        background-color: #E5E7EB; color: #000000; border: 1px solid #9CA3AF; 
        padding: 8px 16px; border-radius: 4px; font-weight: bold; font-size: 13px;
    }
    QPushButton:hover { background-color: #D1D5DB; }
    QPushButton#primaryBtn { background-color: #0066CC; color: #FFFFFF; border: none; }
    QPushButton#primaryBtn:hover { background-color: #0052A3; }
    QGroupBox { border: 2px solid #A0A0A0; border-radius: 6px; margin-top: 15px; color: #000000; font-weight: bold;}
    QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #0066CC; font-weight: bold; }
"""

class BookDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Book")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLE)
        self.layout = QFormLayout(self)
        self.title_input = QLineEdit()
        self.author_input = QLineEdit()
        self.lang_input = QComboBox()
        self.lang_input.addItems(["Arabic", "Urdu", "English", "Multilingual"])
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

    def get_data(self):
        return {
            "title": self.title_input.text(), "author": self.author_input.text(),
            "language": self.lang_input.currentText().lower()[:2] if self.lang_input.currentText() != "Multilingual" else "multi"
        }

class ChapterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Book Element")
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
