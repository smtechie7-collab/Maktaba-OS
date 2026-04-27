import os
import sys
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolBar, 
                             QLabel, QTextEdit, QLineEdit, QComboBox, QFormLayout, QGroupBox, 
                             QMessageBox, QFrame, QColorDialog, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QSplitter)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor

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

        # --- RICH TEXT TOOLBAR ---
        self.build_formatting_toolbar(layout)

        # --- ISLAMIC ORNAMENTS TOOLBAR ---
        self.build_symbols_toolbar(layout)

        # --- DUAL-MODE EDITING TABS ---
        self.editor_tabs = QTabWidget()
        layout.addWidget(self.editor_tabs)
        
        para_widget = QWidget()
        para_layout = QVBoxLayout(para_widget)
        para_layout.setContentsMargins(0, 0, 0, 0)
        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        para_layout.addWidget(self.editor_splitter)
        self.editor_tabs.addTab(para_widget, "📝 Paragraph Editor")
        self.build_karaoke_tab()
        self.build_metadata_tab()

        default_schema = [
            {"id": "ar", "label": "Arabic (نص عربي)", "font": "Amiri", "size": 22, "rtl": True},
            {"id": "ur", "label": "Urdu (اردو)", "font": "Jameel Noori Nastaliq", "size": 18, "rtl": True},
            {"id": "guj", "label": "Gujarati", "font": "Noto Sans Gujarati", "size": 14, "rtl": False},
            {"id": "en", "label": "English", "font": "Segoe UI", "size": 14, "rtl": False}
        ]
        self.build_editors(default_schema)
        self.reset_stretches()

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

    def build_metadata_tab(self):
        meta_fn_widget = QWidget()
        meta_fn_layout = QVBoxLayout(meta_fn_widget)
        
        metadata_group = QGroupBox("Tagging & Metadata")
        m_layout = QHBoxLayout()
        self.day_combo = QComboBox()
        self.day_combo.addItems(["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        m_layout.addWidget(QLabel("Day:"))
        m_layout.addWidget(self.day_combo)
        
        self.track_combo = QComboBox()
        self.track_combo.addItems(["T1 (Daily Base)", "T2 (Dua Iftitah)", "T3 (Monday Hizb)", "T10 (Shajra)"])
        m_layout.addWidget(QLabel("Track:"))
        m_layout.addWidget(self.track_combo)
        
        self.section_combo = QComboBox()
        self.section_combo.addItems(["General", "Muqaddama", "Asma-ul-Husna", "Dua-e-Iftitah", "Hizb", "Shajra"])
        m_layout.addWidget(QLabel("Section:"))
        m_layout.addWidget(self.section_combo)
        metadata_group.setLayout(m_layout)
        meta_fn_layout.addWidget(metadata_group)
        
        # --- FOOTNOTE (TAKHREEJ) ENGINE ---
        footnote_group = QGroupBox("📚 Takhreej & Footnotes")
        fn_layout = QFormLayout()
        self.fn_ar_input = QLineEdit()
        self.fn_ar_input.setPlaceholderText("Arabic Takhreej / Reference Note...")
        self.fn_ar_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.fn_en_input = QLineEdit()
        self.fn_en_input.setPlaceholderText("English / Roman Footnote...")
        fn_layout.addRow("AR:", self.fn_ar_input)
        fn_layout.addRow("EN:", self.fn_en_input)
        footnote_group.setLayout(fn_layout)
        meta_fn_layout.addWidget(footnote_group)
        
        meta_fn_layout.addStretch()
        self.editor_tabs.addTab(meta_fn_widget, "🏷️ Metadata & Footnotes")

    def build_karaoke_tab(self):
        """Builds the Word-by-Word Data Grid for Transliteration & Audio Sync."""
        karaoke_widget = QWidget()
        k_layout = QVBoxLayout(karaoke_widget)
        
        k_toolbar = QHBoxLayout()
        
        extract_btn = QPushButton("✨ Auto-Extract Words from Arabic")
        extract_btn.setObjectName("primaryBtn")
        extract_btn.setToolTip("Automatically splits the Arabic text into words for mapping")
        extract_btn.clicked.connect(self.auto_extract_words)
        
        add_row_btn = QPushButton("➕ Add Word Row")
        add_row_btn.clicked.connect(lambda: self.add_word_row())
        
        del_row_btn = QPushButton("🗑️ Delete Selected Row")
        del_row_btn.clicked.connect(self.delete_word_row)
        
        k_toolbar.addWidget(extract_btn)
        k_toolbar.addWidget(add_row_btn)
        k_toolbar.addWidget(del_row_btn)
        k_toolbar.addStretch()
        k_layout.addLayout(k_toolbar)
        
        # Karaoke Data Grid
        self.words_table = QTableWidget(0, 6)
        self.words_table.setHorizontalHeaderLabels(["Arabic (Ar)", "Urdu (Ur)", "Gujarati (Guj)", "English (En)", "Audio Start (s)", "Audio End (s)"])
        self.words_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.words_table.setAlternatingRowColors(True)
        self.words_table.setStyleSheet("QTableWidget { font-size: 14px; }")
        
        k_layout.addWidget(self.words_table)
        self.editor_tabs.addTab(karaoke_widget, "⏱️ Word-by-Word Sync (Karaoke)")

    def auto_extract_words(self):
        """Splits Arabic plain text and pre-fills the Karaoke grid."""
        ar_text = self.clean_html(self.editors["ar"].toHtml()) if self.editors["ar"].toPlainText().strip() else ""
        # Strip HTML tags just to get clean text for splitting
        clean_text = re.sub(r'<[^>]+>', '', ar_text).strip()
        
        if not clean_text:
            return QMessageBox.warning(self, "No Text", "Please enter Arabic text in the Paragraph Editor first.")
            
        if self.words_table.rowCount() > 0:
            reply = QMessageBox.question(self, "Overwrite?", "This will clear existing words in the table. Continue?")
            if reply != QMessageBox.StandardButton.Yes: return
            
        self.words_table.setRowCount(0)
        words = [w for w in clean_text.split() if w.strip()]
        for w in words:
            self.add_word_row(ar=w)
            
    def delete_word_row(self):
        current_row = self.words_table.currentRow()
        if current_row >= 0: self.words_table.removeRow(current_row)

    def capture_audio_timestamp(self, time_sec):
        """Captures the clicked audio time and assigns it to the current Karaoke word."""
        if self.editor_tabs.currentIndex() != 1: # Index 1 is the Word-by-Word Sync Tab
            return False
            
        row = self.words_table.currentRow()
        if row < 0:
            if self.words_table.rowCount() > 0:
                row = 0
                self.words_table.selectRow(row)
            else:
                return False
                
        start_item = self.words_table.item(row, 4)
        end_item = self.words_table.item(row, 5)
        
        start_val = start_item.text().strip() if start_item else ""
        end_val = end_item.text().strip() if end_item else ""
        
        time_str = f"{time_sec:.3f}"
        
        if not start_val:
            self.words_table.setItem(row, 4, QTableWidgetItem(time_str))
        elif not end_val:
            self.words_table.setItem(row, 5, QTableWidgetItem(time_str))
            # Auto-advance to next row
            if row + 1 < self.words_table.rowCount():
                self.words_table.selectRow(row + 1)
        else:
            # Overwrite start and clear end if both were filled
            self.words_table.setItem(row, 4, QTableWidgetItem(time_str))
            self.words_table.setItem(row, 5, QTableWidgetItem(""))
            
        return True

    def build_formatting_toolbar(self, parent_layout):
        """Adds a toolbar for Rich Text formatting (Bold, Color, Harakat)."""
        toolbar_layout = QHBoxLayout()
        fmt_label = QLabel("Rich Text:")
        fmt_label.setObjectName("fieldLabel")
        toolbar_layout.addWidget(fmt_label)
        
        bold_btn = QPushButton("B")
        bold_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        bold_btn.clicked.connect(lambda: self.apply_format('bold'))
        
        italic_btn = QPushButton("I")
        italic_btn.setFont(QFont("Arial", 10, QFont.Weight.Normal, True))
        italic_btn.clicked.connect(lambda: self.apply_format('italic'))
        
        ul_btn = QPushButton("U")
        f = QFont("Arial", 10)
        f.setUnderline(True)
        ul_btn.setFont(f)
        ul_btn.clicked.connect(lambda: self.apply_format('underline'))
        
        color_btn = QPushButton("🎨 Color")
        color_btn.clicked.connect(self.pick_color)
        
        harakat_btn = QPushButton("🔴 Color Harakat")
        harakat_btn.setToolTip("Colors all Arabic vowel marks red")
        harakat_btn.clicked.connect(self.color_harakat)

        for btn in [bold_btn, italic_btn, ul_btn, color_btn, harakat_btn]:
            toolbar_layout.addWidget(btn)
            
        toolbar_layout.addStretch()
        parent_layout.addLayout(toolbar_layout)

    def build_symbols_toolbar(self, parent_layout):
        """Adds a professional toolbar for quick insertion of Islamic ornaments & Calligraphy."""
        toolbar_layout = QHBoxLayout()
        toolbar_label = QLabel("Calligraphy & Symbols:")
        toolbar_label.setObjectName("fieldLabel")
        toolbar_layout.addWidget(toolbar_label)
        
        symbols = [
            ("Ayah ۝", "۝"), ("Bismillah ﷽", "﷽"), ("Sallallahu Alayhi Wasallam ﷺ", "ﷺ"), 
            ("Jalla Jalaluhu ﷻ", "ﷻ"), ("Radi Allahu Anhu ؓ", "ؓ"), ("Star ۞", "۞")
        ]
        
        for name, char in symbols:
            btn = QPushButton(name)
            btn.setToolTip(f"Insert {name}")
            btn.clicked.connect(lambda checked, c=char: self.insert_symbol_to_active_editor(c))
            toolbar_layout.addWidget(btn)
            
        toolbar_layout.addStretch()
        parent_layout.addLayout(toolbar_layout)

    def insert_symbol_to_active_editor(self, symbol):
        """Inserts the selected symbol into the currently focused editor."""
        for editor in self.editors.values():
            if editor.hasFocus():
                editor.insertPlainText(symbol)
                return
        # Fallback to Arabic editor if none is explicitly focused
        if "ar" in self.editors:
            self.editors["ar"].insertPlainText(symbol)

    def get_active_editor(self):
        """Returns the currently focused editor, fallback to Arabic."""
        for editor in self.editors.values():
            if editor.hasFocus():
                return editor
        return self.editors.get("ar")

    def apply_format(self, fmt_type):
        """Applies basic formatting like bold, italic to the selection."""
        editor = self.get_active_editor()
        if not editor: return
        cursor = editor.textCursor()
        fmt = QTextCharFormat()
        if fmt_type == 'bold':
            current_weight = cursor.charFormat().fontWeight()
            fmt.setFontWeight(QFont.Weight.Normal if current_weight == QFont.Weight.Bold else QFont.Weight.Bold)
        elif fmt_type == 'italic':
            fmt.setFontItalic(not cursor.charFormat().fontItalic())
        elif fmt_type == 'underline':
            fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            editor.mergeCurrentCharFormat(fmt)
        self.text_changed_live.emit()

    def pick_color(self):
        """Opens a color picker and applies the color to selected text."""
        editor = self.get_active_editor()
        if not editor: return
        color = QColorDialog.getColor()
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            cursor = editor.textCursor()
            if cursor.hasSelection():
                cursor.mergeCharFormat(fmt)
            else:
                editor.mergeCurrentCharFormat(fmt)
            self.text_changed_live.emit()

    def color_harakat(self):
        """Finds all Arabic vowel marks in the text and colors them Red."""
        editor = self.editors.get("ar")
        if not editor: return
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        doc = editor.document()
        text = doc.toPlainText()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#DC2626")) # Standard Red
        for i, char in enumerate(text):
            if '\u064B' <= char <= '\u065F' or char == '\u0670':
                cursor.setPosition(i)
                cursor.setPosition(i + 1, QTextCursor.MoveMode.KeepAnchor)
                cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()
        self.text_changed_live.emit()

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
            self.editor_splitter.addWidget(container)
            
            self.editors[field["id"]] = editor
            self.counters[field["id"]] = counter_lbl
            self.line_counters[field["id"]] = line_lbl

    def on_editor_focus_in(self, active_field_id):
        """Dynamic Flex Grid: Maximizes the active editor and minimizes the rest."""
        sizes = []
        for i in range(self.editor_splitter.count()):
            container = self.editor_splitter.widget(i)
            if container.property("field_id") == active_field_id:
                sizes.append(600) # Expand active
                container.setProperty("active_state", "focused")
            else:
                sizes.append(150) # Shrink inactive
                container.setProperty("active_state", "dimmed")
            self.update_widget_style(container)
        self.editor_splitter.setSizes(sizes)

    def reset_stretches(self):
        """Resets all editors to equal widths."""
        sizes = []
        for i in range(self.editor_splitter.count()):
            container = self.editor_splitter.widget(i)
            sizes.append(300) # Reset to equal
            container.setProperty("active_state", "normal")
            self.update_widget_style(container)
        self.editor_splitter.setSizes(sizes)

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

    def add_word_row(self, ar="", ur="", guj="", en="", start="", end=""):
        row = self.words_table.rowCount()
        self.words_table.insertRow(row)
        self.words_table.setItem(row, 0, QTableWidgetItem(str(ar)))
        self.words_table.setItem(row, 1, QTableWidgetItem(str(ur)))
        self.words_table.setItem(row, 2, QTableWidgetItem(str(guj)))
        self.words_table.setItem(row, 3, QTableWidgetItem(str(en)))
        self.words_table.setItem(row, 4, QTableWidgetItem(str(start)))
        self.words_table.setItem(row, 5, QTableWidgetItem(str(end)))

    def load_data_for_editing(self, block_id, data):
        self.current_editing_block_id = block_id
        self.status_label.setText(f"Mode: EDITING Block #{block_id} ✏️")
        self.update_widget_style(self.status_label, obj_name="statusLabelEditing")
        self.cancel_edit_btn.setVisible(True)
        
        for editor in self.editors.values(): editor.blockSignals(True)
        
        for key in self.editors.keys():
            if key in data:
                text = data[key]
                # Auto-detect if data contains HTML tags
                if bool(re.search(r'<[^>]+>', text)):
                    self.editors[key].setHtml(text)
                else:
                    self.editors[key].setPlainText(text)
        self.ref_input.setText(data.get("reference", ""))
        
        if "metadata" in data:
            meta = data["metadata"]
            if "day" in meta: self.day_combo.setCurrentText(meta["day"])
            if "track" in meta: 
                idx = self.track_combo.findText(meta["track"], Qt.MatchFlag.MatchStartsWith)
                if idx >= 0: self.track_combo.setCurrentIndex(idx)
            if "section" in meta: self.section_combo.setCurrentText(meta["section"])
            
        # Load footnotes if provided
        self.fn_ar_input.clear()
        self.fn_en_input.clear()
        if "footnotes" in data and data["footnotes"]:
            # Load the first footnote for simple editing
            first_fn = data["footnotes"][0].get("content", {})
            if "ar" in first_fn: self.fn_ar_input.setText(first_fn["ar"])
            if "en" in first_fn: self.fn_en_input.setText(first_fn["en"])
            
        for editor in self.editors.values(): editor.blockSignals(False)
        
        self.words_table.setRowCount(0)
        if "words" in data and data["words"]:
            for w in data["words"]:
                self.add_word_row(w.get("ar", ""), w.get("ur", ""), w.get("guj", ""), w.get("en", ""), w.get("start", ""), w.get("end", ""))
                
        self.check_translation_alignment() # Run checker on load
        self.reset_stretches()

    def clean_html(self, html_str):
        """Extracts inner HTML from PyQt's boilerplate document structure."""
        match = re.search(r'<body[^>]*>(.*?)</body>', html_str, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return html_str.strip()

    def get_data(self):
        # Now extracts and saves safe HTML snippets instead of plain text
        data = {key: self.clean_html(editor.toHtml()) if editor.toPlainText().strip() else "" for key, editor in self.editors.items()}
        data["reference"] = self.ref_input.text().strip()
        data["metadata"] = {"day": self.day_combo.currentText(), "track": self.track_combo.currentText().split(" ")[0], "section": self.section_combo.currentText()}
        
        # Extract Footnotes for Save payload
        fn_ar = self.fn_ar_input.text().strip()
        fn_en = self.fn_en_input.text().strip()
        if fn_ar or fn_en:
            data["footnotes"] = [{"marker": "*", "content": {"ar": fn_ar, "en": fn_en}}]
        else:
            data["footnotes"] = []
            
        # Extract Karaoke Words
        words_data = []
        for row in range(self.words_table.rowCount()):
            ar_item = self.words_table.item(row, 0)
            ar_text = ar_item.text().strip() if ar_item else ""
            if not ar_text: continue
            words_data.append({
                "ar": ar_text,
                "ur": self.words_table.item(row, 1).text().strip() if self.words_table.item(row, 1) else "",
                "guj": self.words_table.item(row, 2).text().strip() if self.words_table.item(row, 2) else "",
                "en": self.words_table.item(row, 3).text().strip() if self.words_table.item(row, 3) else "",
                "start": self.words_table.item(row, 4).text().strip() if self.words_table.item(row, 4) else "",
                "end": self.words_table.item(row, 5).text().strip() if self.words_table.item(row, 5) else ""
            })
            
        data["words"] = words_data
            
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
        self.fn_ar_input.clear()
        self.fn_en_input.clear()
        self.words_table.setRowCount(0)
        
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
