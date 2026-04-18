import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QLineEdit, QComboBox, QFormLayout, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor

class EditorPanel(QWidget):
    save_requested = pyqtSignal(dict) # Emits structured block data jab save click ho

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self.holy_names_enabled = True
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.focus_mode_btn = QPushButton("🎯 Focus Mode")
        self.focus_mode_btn.setCheckable(True)
        self.preview_mode_btn = QPushButton("👁 Preview")
        self.preview_mode_btn.setCheckable(True)
        toolbar.addWidget(self.focus_mode_btn)
        toolbar.addWidget(self.preview_mode_btn)
        layout.addLayout(toolbar)

        # Dynamic Editor Grid
        self.grid_layout = QHBoxLayout()
        layout.addLayout(self.grid_layout)

        # Default schema (4 Layers for Dalail)
        default_schema = [
            {"id": "ar", "label": "Arabic (نص عربي)", "font": "Amiri", "size": 18, "rtl": True},
            {"id": "ur", "label": "Urdu (اردو)", "font": "Jameel Noori Nastaliq", "size": 16, "rtl": True},
            {"id": "guj", "label": "Gujarati Transliteration", "font": "Noto Sans Gujarati", "size": 14, "rtl": False},
            {"id": "en", "label": "Hinglish (Roman)", "font": "Segoe UI", "size": 14, "rtl": False}
        ]
        self.build_editors(default_schema)

        # --- NAYA PART: Metadata & Tags (Phase 2 Requirement) ---
        metadata_group = QGroupBox("Tagging & Metadata")
        meta_layout = QHBoxLayout()
        
        # Day Dropdown
        self.day_combo = QComboBox()
        self.day_combo.addItems(["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        meta_layout.addWidget(QLabel("Day:"))
        meta_layout.addWidget(self.day_combo)
        
        # Track Reference Dropdown
        self.track_combo = QComboBox()
        self.track_combo.addItems(["T1 (Daily Base)", "T2 (Dua Iftitah)", "T3 (Monday Hizb)", "T4 (Tuesday)", "T5 (Wednesday)", "T6 (Thursday)", "T7 (Friday)", "T8 (Saturday)", "T9 (Sunday)", "T10 (Shajra)"])
        meta_layout.addWidget(QLabel("Track:"))
        meta_layout.addWidget(self.track_combo)
        
        # Section Dropdown
        self.section_combo = QComboBox()
        self.section_combo.addItems(["General", "Muqaddama", "Asma-ul-Husna", "Dua-e-Iftitah", "Hizb", "Shajra"])
        meta_layout.addWidget(QLabel("Section:"))
        meta_layout.addWidget(self.section_combo)

        metadata_group.setLayout(meta_layout)
        layout.addWidget(metadata_group)
        # ---------------------------------------------------------

        # Reference & Save Bar
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Reference:"))
        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("e.g. Pg 12 | Bukhari 123")
        ref_layout.addWidget(self.ref_input)
        
        self.save_block_btn = QPushButton("💾 Save Block")
        self.save_block_btn.setObjectName("primaryBtn")
        self.save_block_btn.clicked.connect(self.on_save_clicked)
        ref_layout.addWidget(self.save_block_btn)
        layout.addLayout(ref_layout)

    def build_editors(self, schema):
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)
        self.editors.clear()

        for field in schema:
            widget = QWidget()
            v_layout = QVBoxLayout(widget)
            v_layout.addWidget(QLabel(field["label"]))
            
            editor = QTextEdit()
            editor.setPlaceholderText(f"Enter {field['label']}...")
            if field["rtl"]:
                editor.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                editor.setAlignment(Qt.AlignmentFlag.AlignRight)
            editor.setFont(QFont(field["font"], field["size"]))
            editor.textChanged.connect(lambda e=editor, fid=field["id"]: self.on_text_changed(e, fid))
            
            v_layout.addWidget(editor)
            self.grid_layout.addWidget(widget)
            self.editors[field["id"]] = editor

    def on_text_changed(self, editor, field_id):
        if field_id == "ar" and self.holy_names_enabled:
            self.apply_holy_names_highlight(editor)
        self.check_overflow(editor)

    def check_overflow(self, editor):
        limit = 600 
        text_len = len(editor.toPlainText())
        if text_len > limit:
            editor.setStyleSheet("border: 2px solid #ff4444; background-color: #1a0000;")
        else:
            editor.setStyleSheet("")

    def toggle_holy_highlighter(self, state):
        self.holy_names_enabled = state
        if state and "ar" in self.editors:
            self.apply_holy_names_highlight(self.editors["ar"])

    def apply_holy_names_highlight(self, editor):
        editor.blockSignals(True)
        original_cursor = editor.textCursor()
        
        gold_format = QTextCharFormat()
        gold_format.setForeground(QColor("gold"))
        red_format = QTextCharFormat()
        red_format.setForeground(QColor("#ff6b6b"))
        
        words_to_highlight = {
            "Allah": gold_format, "الله": gold_format,
            "Muhammad (ﷺ)": red_format, "محمد": red_format
        }
        
        document = editor.document()
        for word, char_format in words_to_highlight.items():
            cursor = document.find(word)
            while not cursor.isNull():
                cursor.mergeCharFormat(char_format)
                cursor = document.find(word, cursor)
                
        editor.setTextCursor(original_cursor)
        editor.blockSignals(False)

    def get_data(self):
        # Yahan hum block data aur metadata dono bhejenge
        data = {key: editor.toPlainText().strip() for key, editor in self.editors.items()}
        data["reference"] = self.ref_input.text().strip()
        data["metadata"] = {
            "day": self.day_combo.currentText(),
            "track": self.track_combo.currentText().split(" ")[0], # Sirf T1, T2 store karenge
            "section": self.section_combo.currentText()
        }
        return data

    def clear_fields(self):
        for editor in self.editors.values():
            editor.clear()
        self.ref_input.clear()

    def on_save_clicked(self):
        self.save_requested.emit(self.get_data())
