from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QComboBox, QPushButton, QMessageBox, QFrame)
from PyQt6.QtCore import Qt

class SearchReplaceDialog(QDialog):
    """
    Pro Studio Global Find & Replace Dialog.
    Allows the user to surgically target specific languages or search across all JSON content blocks.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Find & Replace")
        self.setFixedSize(450, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setObjectName("searchReplaceDialog")
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("🔍 Global Find & Replace")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #176B87;")
        layout.addWidget(header)
        
        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter word or phrase to find...")
        self.search_input.setStyleSheet("padding: 10px; font-size: 14px; border: 1px solid #CBD5E1; border-radius: 6px;")
        layout.addWidget(QLabel("<b>Find:</b>"))
        layout.addWidget(self.search_input)
        
        # Replace Input
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Enter replacement text...")
        self.replace_input.setStyleSheet("padding: 10px; font-size: 14px; border: 1px solid #CBD5E1; border-radius: 6px;")
        layout.addWidget(QLabel("<b>Replace with:</b>"))
        layout.addWidget(self.replace_input)
        
        # Language Selection Scope
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("All Languages", None)
        self.lang_combo.addItem("Arabic (ar)", "ar")
        self.lang_combo.addItem("English (en)", "en")
        self.lang_combo.addItem("Urdu (ur)", "ur")
        self.lang_combo.addItem("Gujarati (guj)", "guj")
        self.lang_combo.setStyleSheet("padding: 8px; font-size: 14px; border-radius: 4px; border: 1px solid #CBD5E1;")
        layout.addWidget(QLabel("<b>Target Language Scope:</b>"))
        layout.addWidget(self.lang_combo)
        
        # Warning label
        warning = QLabel("⚠️ Warning: This will modify all blocks in the active book.\nChanges are versioned individually, but large operations may take a moment.")
        warning.setStyleSheet("color: #D32F2F; font-size: 11px; font-style: italic;")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setObjectName("secondaryBtn")
        self.cancel_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        
        self.replace_btn = QPushButton("Replace All")
        self.replace_btn.setObjectName("dangerBtn")
        self.replace_btn.setStyleSheet("padding: 8px 16px; font-weight: bold;")
        self.replace_btn.clicked.connect(self.validate_and_accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.replace_btn)
        
        layout.addLayout(btn_layout)
        
    def validate_and_accept(self):
        if not self.search_input.text().strip():
            QMessageBox.warning(self, "Validation Error", "The 'Find' field cannot be empty.")
            return
        
        reply = QMessageBox.question(
            self, 
            "Confirm Global Replace", 
            f"Are you sure you want to replace all occurrences of '{self.search_input.text()}'?\n\nThis action affects the entire active book.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.accept()
            
    def get_data(self):
        return {
            "search": self.search_input.text(),
            "replace": self.replace_input.text(),
            "lang": self.lang_combo.currentData()
        }