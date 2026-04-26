import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QLineEdit, QComboBox, QFormLayout, QGroupBox, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor

class AdvancedTextEdit(QTextEdit):
    """Custom TextEdit that emits signals when it gains or loses focus."""
    focus_in = pyqtSignal(str)

    def __init__(self, field_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_id = field_id

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_in.emit(self.field_id)

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

    def update_widget_style(self, widget, state=None, obj_name=None):
        if obj_name:
            widget.setObjectName(obj_name)
        if state is not None:
            widget.setProperty("state", state)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Mode Status Label
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Mode: Creating New Block")
        self.status_label.setObjectName("statusLabelNormal")
        status_layout.addWidget(self.status_label)
        
        # Global Error Label for Alignment mismatch
        self.alignment_warning = QLabel("")
        self.alignment_warning.setObjectName("warningLabelError")
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
        self.reset_stretches()

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
        self.cancel_edit_btn.setObjectName("secondaryBtn")
        self.cancel_edit_btn.setVisible(False)
        self.cancel_edit_btn.clicked.connect(self.clear_fields)
        
        self.focus_mode_btn = QPushButton("👁 Focus Mode")
        self.focus_mode_btn.setObjectName("secondaryBtn")
        self.focus_mode_btn.setCheckable(True)
        self.focus_mode_btn.setToolTip("Hide empty language panels to focus on active text")
        self.focus_mode_btn.clicked.connect(self.toggle_focus_mode)
        
        ref_layout.addWidget(self.focus_mode_btn)
        ref_layout.addWidget(self.cancel_edit_btn)
        ref_layout.addWidget(self.save_block_btn)
        layout.addLayout(ref_layout)

    def build_editors(self, schema):
        for field in schema:
            # Modern Card Container
            container = QFrame()
            container.setObjectName("editorContainer")
            container.setProperty("field_id", field["id"])
            container.setProperty("active_state", "normal")
            v_layout = QVBoxLayout(container)
            v_layout.setContentsMargins(12, 12, 12, 12)
            
            # Label with Line Counter
            header_layout = QHBoxLayout()
            lbl = QLabel(field["label"])
            lbl.setObjectName("fieldLabel")
            header_layout.addWidget(lbl)
            
            line_lbl = QLabel("0 Lines")
            line_lbl.setObjectName("lineLabel")
            header_layout.addWidget(line_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            v_layout.addLayout(header_layout)
            
            editor = AdvancedTextEdit(field["id"])
            editor.setPlaceholderText(f"Enter {field['label']}...")
            if field["rtl"]:
                editor.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                editor.setAlignment(Qt.AlignmentFlag.AlignRight)
            
            font = QFont(field["font"], field["size"])
            font.setBold(True)
            editor.setFont(font)
            self.update_widget_style(editor, state="normal")
            
            editor.focus_in.connect(self.on_editor_focus_in)
            
            counter_lbl = QLabel("0 chars")
            counter_lbl.setObjectName("charCounterLabel")
            
            # Pass line_lbl to the callback
            editor.textChanged.connect(lambda e=editor, fid=field["id"], c_lbl=counter_lbl, l_lbl=line_lbl: self.on_text_changed(e, fid, c_lbl, l_lbl))
            
            v_layout.addWidget(editor)
            v_layout.addWidget(counter_lbl, alignment=Qt.AlignmentFlag.AlignRight)
            self.grid_layout.addWidget(container)
            
            self.editors[field["id"]] = editor
            self.counters[field["id"]] = counter_lbl
            self.line_counters[field["id"]] = line_lbl

    def on_editor_focus_in(self, active_field_id):
        """Dynamic Flex Grid: Maximizes the active editor and minimizes the rest."""
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                if container.property("field_id") == active_field_id:
                    self.grid_layout.setStretch(i, 5) # Expand active (5x wider)
                    container.setProperty("active_state", "focused")
                else:
                    self.grid_layout.setStretch(i, 1) # Shrink inactive
                    container.setProperty("active_state", "dimmed")
                self.update_widget_style(container)

    def reset_stretches(self):
        """Resets all editors to equal widths."""
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                container = item.widget()
                self.grid_layout.setStretch(i, 1) # Reset to 1:1:1:1
                container.setProperty("active_state", "normal")
                self.update_widget_style(container)

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
                self.update_widget_style(editor, state="normal")
            return

        # Check if all active fields have the exact same line count
        first_count = list(active_lines.values())[0]
        is_aligned = all(count == first_count for count in active_lines.values())

        if is_aligned:
            self.alignment_warning.setText("✅ Lines Aligned Perfectly")
            self.update_widget_style(self.alignment_warning, obj_name="warningLabelSuccess")
            # Reset all borders to normal
            for fid, editor in self.editors.items():
                 if active_lines.get(fid):
                     self.update_widget_style(editor, state="success")
        else:
            mismatch_text = " | ".join([f"{fid.upper()}: {cnt}" for fid, cnt in active_lines.items()])
            self.alignment_warning.setText(f"⚠️ MISMATCH DETECTED: {mismatch_text}")
            self.update_widget_style(self.alignment_warning, obj_name="warningLabelError")
            # Highlight mismatched fields with red borders
            for fid, editor in self.editors.items():
                if active_lines.get(fid):
                    self.update_widget_style(editor, state="error")

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

    def toggle_focus_mode(self, checked):
        for fid, editor in self.editors.items():
            if checked:
                if not editor.toPlainText().strip():
                    editor.parent().setVisible(False)
            else:
                editor.parent().setVisible(True)

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
        self.update_widget_style(self.status_label, obj_name="statusLabelEditing")
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
        self.reset_stretches()

    def get_data(self):
        data = {key: editor.toPlainText().strip() for key, editor in self.editors.items()}
        data["reference"] = self.ref_input.text().strip()
        data["metadata"] = {"day": self.day_combo.currentText(), "track": self.track_combo.currentText().split(" ")[0], "section": self.section_combo.currentText()}
        return data

    def clear_fields(self):
        self.current_editing_block_id = None
        self.status_label.setText("Mode: Creating New Block")
        self.update_widget_style(self.status_label, obj_name="statusLabelNormal")
        self.cancel_edit_btn.setVisible(False)
        self.alignment_warning.setText("")
        
        self.focus_mode_btn.setChecked(False)
        self.toggle_focus_mode(False)
        self.reset_stretches()
        
        for editor in self.editors.values(): 
            editor.blockSignals(True)
            editor.clear()
            self.update_widget_style(editor, state="normal")
            editor.blockSignals(False)
            
        for counter in self.line_counters.values(): counter.setText("0 Lines")
        for counter in self.counters.values(): counter.setText("0 chars")
            
        self.ref_input.clear()
        self.text_changed_live.emit()

    def on_save_clicked(self):
        data = self.get_data()
        has_content = any(data.get(k) for k in ["ar", "ur", "guj", "en"])
        if not has_content:
            QMessageBox.warning(self, "Validation Error", "Cannot save an empty block. Please enter text in at least one language.")
            return
            
        if self.current_editing_block_id:
            data['update_block_id'] = self.current_editing_block_id
        self.save_requested.emit(data)
