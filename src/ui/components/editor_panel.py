import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QLineEdit, QComboBox, QFormLayout, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor

class EditorPanel(QWidget):
    save_requested = pyqtSignal(dict)
    text_changed_live = pyqtSignal() # LIVE PREVIEW SIGNAL

    def __init__(self, parent=None):
        super().__init__(parent)
        self.editors = {}
        self.counters = {}
        self.line_counters = {} # Naya dictionary lines count karne ke liye
        self.holy_names_enabled = True
        self.current_editing_block_id = None 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Mode Status Label
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Mode: Creating New Block")
        self.status_label.setStyleSheet("color: #0066CC; font-weight: bold; font-size: 14px; padding-bottom: 10px;")
        status_layout.addWidget(self.status_label)
        
        # Global Error Label for Alignment mismatch
        self.alignment_warning = QLabel("")
        self.alignment_warning.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 13px; padding-bottom: 10px;")
        status_layout.addWidget(self.alignment_warning, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(status_layout)

        self.grid_layout = QHBoxLayout()
        layout.addLayout(self.grid_layout)

        default_schema = [
            {"id": "ar", "label": "Arabic (نص عربي)", "font": "Amiri", "size": 22, "rtl": True},
            {"id": "ur", "label": "Urdu (اردو)", "font": "Jameel Noori Nastaliq", "size": 18, "rtl": True},
            {"id": "guj", "label": "Gujarati Transliteration", "font": "Noto Sans Gujarati", "size": 14, "rtl": False},
            {"id": "en", "label": "Hinglish (Roman)", "font": "Segoe UI", "size": 14, "rtl": False}
        ]
        self.build_editors(default_schema)

        metadata_group = QGroupBox("Tagging & Metadata")
        meta_layout = QHBoxLayout()
        self.day_combo = QComboBox()
        self.day_combo.addItems(["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        meta_layout.addWidget(QLabel("Day:"))
        meta_layout.addWidget(self.day_combo)
        
        self.track_combo = QComboBox()
        self.track_combo.addItems(["T1 (Daily Base)", "T2 (Dua Iftitah)", "T3 (Monday Hizb)", "T10 (Shajra)"])
        meta_layout.addWidget(QLabel("Track:"))
        meta_layout.addWidget(self.track_combo)
        
        self.section_combo = QComboBox()
        self.section_combo.addItems(["General", "Muqaddama", "Asma-ul-Husna", "Dua-e-Iftitah", "Hizb", "Shajra"])
        meta_layout.addWidget(QLabel("Section:"))
        meta_layout.addWidget(self.section_combo)
        metadata_group.setLayout(meta_layout)
        layout.addWidget(metadata_group)

        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Reference:"))
        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("e.g. Pg 12")
        ref_layout.addWidget(self.ref_input)
        
        self.save_block_btn = QPushButton("💾 Save / Update Block")
        self.save_block_btn.setObjectName("primaryBtn")
        self.save_block_btn.clicked.connect(self.on_save_clicked)
        
        self.cancel_edit_btn = QPushButton("Cancel Edit")
        self.cancel_edit_btn.setVisible(False)
        self.cancel_edit_btn.clicked.connect(self.clear_fields)
        
        ref_layout.addWidget(self.cancel_edit_btn)
        ref_layout.addWidget(self.save_block_btn)
        layout.addLayout(ref_layout)

    def build_editors(self, schema):
        for field in schema:
            widget = QWidget()
            v_layout = QVBoxLayout(widget)
            
            # Label with Line Counter
            header_layout = QHBoxLayout()
            lbl = QLabel(field["label"])
            lbl.setStyleSheet("font-weight: bold; color: #000000; font-size: 14px;")
            header_layout.addWidget(lbl)
            
            line_lbl = QLabel("0 Lines")
            line_lbl.setStyleSheet("color: #0066CC; font-size: 11px; font-weight: bold;")
            header_layout.addWidget(line_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            v_layout.addLayout(header_layout)
            
            editor = QTextEdit()
            editor.setPlaceholderText(f"Enter {field['label']}...")
            if field["rtl"]:
                editor.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                editor.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            font = QFont(field["font"], field["size"])
            font.setBold(True)
            editor.setFont(font)
            editor.setStyleSheet("QTextEdit { background-color: #FFFFFF; color: #000000; border: 2px solid #A0A0A0; border-radius: 4px; } QTextEdit:focus { border: 2px solid #0066CC; }")
            
            counter_lbl = QLabel("0 chars")
            counter_lbl.setStyleSheet("color: #333333; font-size: 11px; font-weight: bold;")
            
            # Pass line_lbl to the callback
            editor.textChanged.connect(lambda e=editor, fid=field["id"], c_lbl=counter_lbl, l_lbl=line_lbl: self.on_text_changed(e, fid, c_lbl, l_lbl))
            
            v_layout.addWidget(editor)
            v_layout.addWidget(counter_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            self.grid_layout.addWidget(widget)
            
            self.editors[field["id"]] = editor
            self.counters[field["id"]] = counter_lbl
            self.line_counters[field["id"]] = line_lbl

    def check_translation_alignment(self):
        """Cross-checks if all populated fields have the same number of lines."""
        active_lines = {}
        for fid, editor in self.editors.items():
            text = editor.toPlainText().strip()
            if text:
                # Count lines accurately even if there are empty lines in between
                lines = len([line for line in text.split('\n') if line.strip() != ''])
                active_lines[fid] = lines
        
        # If less than 2 languages are filled, no need to check alignment
        if len(active_lines) < 2:
            self.alignment_warning.setText("")
            for editor in self.editors.values():
                editor.setStyleSheet("QTextEdit { background-color: #FFFFFF; color: #000000; border: 2px solid #A0A0A0; border-radius: 4px; } QTextEdit:focus { border: 2px solid #0066CC; }")
            return

        # Check if all active fields have the exact same line count
        first_count = list(active_lines.values())[0]
        is_aligned = all(count == first_count for count in active_lines.values())

        if is_aligned:
            self.alignment_warning.setText("✅ Lines Aligned Perfectly")
            self.alignment_warning.setStyleSheet("color: #059669; font-weight: bold; font-size: 13px; padding-bottom: 10px;")
            # Reset all borders to normal
            for fid, editor in self.editors.items():
                 if active_lines.get(fid):
                     editor.setStyleSheet("QTextEdit { background-color: #FFFFFF; color: #000000; border: 2px solid #059669; border-radius: 4px; }")
        else:
            mismatch_text = " | ".join([f"{fid.upper()}: {cnt}" for fid, cnt in active_lines.items()])
            self.alignment_warning.setText(f"⚠️ MISMATCH DETECTED: {mismatch_text}")
            self.alignment_warning.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 13px; padding-bottom: 10px;")
            # Highlight mismatched fields with red borders
            for fid, editor in self.editors.items():
                if active_lines.get(fid):
                    editor.setStyleSheet("QTextEdit { background-color: #FEF2F2; color: #000000; border: 2px solid #DC2626; border-radius: 4px; }")

    def on_text_changed(self, editor, field_id, counter_lbl, line_lbl):
        raw_text = editor.toPlainText()
        text_len = len(raw_text)
        
        # Update char count
        counter_lbl.setText(f"{text_len} chars")
        
        # Update line count (Only counting non-empty lines)
        lines_count = len([line for line in raw_text.split('\n') if line.strip() != ''])
        line_lbl.setText(f"{lines_count} Lines")

        if field_id == "ar" and self.holy_names_enabled:
            self.apply_holy_names_highlight(editor)
            
        # Run Alignment Checker
        self.check_translation_alignment()
        
        self.text_changed_live.emit()

    def toggle_holy_highlighter(self, state):
        self.holy_names_enabled = state

    def apply_holy_names_highlight(self, editor):
        editor.blockSignals(True)
        original_cursor = editor.textCursor()
        gold_format = QTextCharFormat(); gold_format.setForeground(QColor("#D97706")) 
        red_format = QTextCharFormat(); red_format.setForeground(QColor("#DC2626"))
        words_to_highlight = {"Allah": gold_format, "الله": gold_format, "Muhammad": red_format, "محمد": red_format}
        
        document = editor.document()
        for word, char_format in words_to_highlight.items():
            cursor = document.find(word)
            while not cursor.isNull():
                cursor.mergeCharFormat(char_format)
                cursor = document.find(word, cursor)
                
        editor.setTextCursor(original_cursor)
        editor.blockSignals(False)

    def load_data_for_editing(self, block_id, data):
        self.current_editing_block_id = block_id
        self.status_label.setText(f"Mode: EDITING Block #{block_id} ✏️")
        self.status_label.setStyleSheet("color: #DC2626; font-weight: bold; font-size: 14px; padding-bottom: 10px;")
        self.cancel_edit_btn.setVisible(True)
        
        for editor in self.editors.values(): editor.blockSignals(True)
        
        for key in self.editors.keys():
            if key in data:
                self.editors[key].setPlainText(data[key])
        self.ref_input.setText(data.get("reference", ""))
        
        if "metadata" in data:
            meta = data["metadata"]
            if "day" in meta: self.day_combo.setCurrentText(meta["day"])
            if "track" in meta: 
                idx = self.track_combo.findText(meta["track"], Qt.MatchFlag.MatchStartsWith)
                if idx >= 0: self.track_combo.setCurrentIndex(idx)
            if "section" in meta: self.section_combo.setCurrentText(meta["section"])
            
        for editor in self.editors.values(): editor.blockSignals(False)
        self.check_translation_alignment() # Run checker on load

    def get_data(self):
        data = {key: editor.toPlainText().strip() for key, editor in self.editors.items()}
        data["reference"] = self.ref_input.text().strip()
        data["metadata"] = {"day": self.day_combo.currentText(), "track": self.track_combo.currentText().split(" ")[0], "section": self.section_combo.currentText()}
        return data

    def clear_fields(self):
        self.current_editing_block_id = None
        self.status_label.setText("Mode: Creating New Block")
        self.status_label.setStyleSheet("color: #0066CC; font-weight: bold; font-size: 14px; padding-bottom: 10px;")
        self.cancel_edit_btn.setVisible(False)
        self.alignment_warning.setText("")
        
        for editor in self.editors.values(): 
            editor.blockSignals(True)
            editor.clear()
            editor.setStyleSheet("QTextEdit { background-color: #FFFFFF; color: #000000; border: 2px solid #A0A0A0; border-radius: 4px; } QTextEdit:focus { border: 2px solid #0066CC; }")
            editor.blockSignals(False)
            
        for counter in self.line_counters.values(): counter.setText("0 Lines")
        for counter in self.counters.values(): counter.setText("0 chars")
            
        self.ref_input.clear()
        self.text_changed_live.emit()

    def on_save_clicked(self):
        data = self.get_data()
        if self.current_editing_block_id:
            data['update_block_id'] = self.current_editing_block_id
        self.save_requested.emit(data)