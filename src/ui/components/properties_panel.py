import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QGroupBox, 
                             QFormLayout, QComboBox, QSlider, QLabel, 
                             QCheckBox, QPushButton, QSpinBox, QScrollArea,
                             QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal

class PropertiesPanel(QWidget):
    properties_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)


        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)

        self.tabs = QTabWidget()

        # --- TYPOGRAPHY TAB ---
        typo_tab = QWidget()
        typo_layout = QVBoxLayout(typo_tab)

        ar_group = QGroupBox("Arabic Font")
        ar_layout = QFormLayout()
        self.ar_font = QComboBox()
        self.ar_font.addItems(["Amiri", "Noor-e-Huda", "Alvi Nastaleeq", "Traditional Arabic"])
        self.ar_size = QSlider(Qt.Orientation.Horizontal)
        self.ar_size.setRange(12, 72)
        self.ar_size.setValue(24)
        self.ar_size_lbl = QLabel("24 pt")
        self.ar_size.valueChanged.connect(lambda v: self.ar_size_lbl.setText(f"{v} pt"))
        self.ar_align = QComboBox()
        self.ar_align.addItems(["Right", "Center", "Justify", "Left"])
        ar_layout.addRow("Font:", self.ar_font)
        ar_layout.addRow("Size:", self.ar_size)
        ar_layout.addRow("", self.ar_size_lbl)
        ar_layout.addRow("Alignment:", self.ar_align)
        ar_group.setLayout(ar_layout)
        typo_layout.addWidget(ar_group)

        ur_group = QGroupBox("Urdu Font")
        ur_layout = QFormLayout()
        self.ur_font = QComboBox()
        self.ur_font.addItems(["Jameel Noori Nastaliq", "Alvi Nastaleeq", "Pak Urdu Naskh"])
        self.ur_size = QSlider(Qt.Orientation.Horizontal)
        self.ur_size.setRange(12, 72)
        self.ur_size.setValue(20)
        self.ur_size_lbl = QLabel("20 pt")
        self.ur_size.valueChanged.connect(lambda v: self.ur_size_lbl.setText(f"{v} pt"))
        self.ur_align = QComboBox()
        self.ur_align.addItems(["Right", "Center", "Justify", "Left"])
        ur_layout.addRow("Font:", self.ur_font)
        ur_layout.addRow("Size:", self.ur_size)
        ur_layout.addRow("", self.ur_size_lbl)
        ur_layout.addRow("Alignment:", self.ur_align)
        ur_group.setLayout(ur_layout)
        typo_layout.addWidget(ur_group)

        guj_group = QGroupBox("Gujarati Font")
        guj_layout = QFormLayout()
        self.guj_font = QComboBox()
        self.guj_font.addItems(["Noto Sans Gujarati", "Aakar"])
        self.guj_size = QSlider(Qt.Orientation.Horizontal)
        self.guj_size.setRange(12, 48)
        self.guj_size.setValue(16)
        self.guj_size_lbl = QLabel("16 pt")
        self.guj_size.valueChanged.connect(lambda v: self.guj_size_lbl.setText(f"{v} pt"))
        self.guj_align = QComboBox()
        self.guj_align.addItems(["Left", "Center", "Justify", "Right"])
        guj_layout.addRow("Font:", self.guj_font)
        guj_layout.addRow("Size:", self.guj_size)
        guj_layout.addRow("", self.guj_size_lbl)
        guj_layout.addRow("Alignment:", self.guj_align)
        guj_group.setLayout(guj_layout)
        typo_layout.addWidget(guj_group)

        self.holy_checkbox = QCheckBox("✨ Highlight Holy Names")
        self.holy_checkbox.setChecked(True)
        typo_layout.addWidget(self.holy_checkbox)
        typo_layout.addStretch()
        self.tabs.addTab(typo_tab, "🔤 Typography")

        # --- LAYOUT TAB ---
        layout_tab = QWidget()
        l_layout = QVBoxLayout(layout_tab)

        theme_group = QGroupBox("📅 Day-Wise Theme")
        t_layout = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["None", "Monday (Blue Border)", "Tuesday (Green Border)", "Wednesday (Orange Border)"])
        t_layout.addRow("Border:", self.theme_combo)
        theme_group.setLayout(t_layout)
        l_layout.addWidget(theme_group)

        margins_group = QGroupBox("📐 Page Margins (mm)")
        m_layout = QFormLayout()
        
        self.m_top = QSlider(Qt.Orientation.Horizontal); self.m_top.setRange(0, 50); self.m_top.setValue(20)
        self.lbl_top = QLabel("20 mm"); self.m_top.valueChanged.connect(lambda v: self.lbl_top.setText(f"{v} mm"))
        
        self.m_bot = QSlider(Qt.Orientation.Horizontal); self.m_bot.setRange(0, 50); self.m_bot.setValue(20)
        self.lbl_bot = QLabel("20 mm"); self.m_bot.valueChanged.connect(lambda v: self.lbl_bot.setText(f"{v} mm"))
        
        self.m_left = QSlider(Qt.Orientation.Horizontal); self.m_left.setRange(0, 50); self.m_left.setValue(20)
        self.lbl_left = QLabel("20 mm"); self.m_left.valueChanged.connect(lambda v: self.lbl_left.setText(f"{v} mm"))
        
        self.m_right = QSlider(Qt.Orientation.Horizontal); self.m_right.setRange(0, 50); self.m_right.setValue(20)
        self.lbl_right = QLabel("20 mm"); self.m_right.valueChanged.connect(lambda v: self.lbl_right.setText(f"{v} mm"))
        
        self.m_gut = QSlider(Qt.Orientation.Horizontal); self.m_gut.setRange(0, 30); self.m_gut.setValue(10)
        self.lbl_gut = QLabel("10 mm"); self.m_gut.valueChanged.connect(lambda v: self.lbl_gut.setText(f"{v} mm"))

        m_layout.addRow("Top:", self.m_top); m_layout.addRow("", self.lbl_top)
        m_layout.addRow("Bottom:", self.m_bot); m_layout.addRow("", self.lbl_bot)
        m_layout.addRow("Left:", self.m_left); m_layout.addRow("", self.lbl_left)
        m_layout.addRow("Right:", self.m_right); m_layout.addRow("", self.lbl_right)
        m_layout.addRow("Gutter:", self.m_gut); m_layout.addRow("", self.lbl_gut)
        margins_group.setLayout(m_layout)
        l_layout.addWidget(margins_group)
        l_layout.addStretch()
        self.tabs.addTab(layout_tab, "📐 Layout")

        # --- PRESETS TAB ---
        presets_tab = QWidget()
        p_layout = QVBoxLayout(presets_tab)
        
        presets_group = QGroupBox("Theme Presets")
        p_btn_layout = QVBoxLayout()
        
        self.save_theme_btn = QPushButton("💾 Save Current Theme as Preset...")
        self.save_theme_btn.setObjectName("secondaryBtn")
        self.save_theme_btn.clicked.connect(self.save_theme)
        
        self.load_theme_btn = QPushButton("📂 Load Theme Preset...")
        self.load_theme_btn.setObjectName("primaryBtn")
        self.load_theme_btn.clicked.connect(self.load_theme)
        
        p_btn_layout.addWidget(self.save_theme_btn)
        p_btn_layout.addWidget(self.load_theme_btn)
        presets_group.setLayout(p_btn_layout)
        p_layout.addWidget(presets_group)
        p_layout.addStretch()
        self.tabs.addTab(presets_tab, "🎨 Presets")

        layout.addWidget(self.tabs)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # --- WIRE LIVE PREVIEW TRIGGERS ---
        for combo in (self.ar_font, self.ur_font, self.guj_font, self.theme_combo, self.ar_align, self.ur_align, self.guj_align):
            combo.currentTextChanged.connect(lambda _: self.properties_changed.emit())
            
        for slider in (self.ar_size, self.ur_size, self.guj_size, self.m_top, self.m_bot, self.m_left, self.m_right, self.m_gut):
            slider.valueChanged.connect(lambda _: self.properties_changed.emit())
            
        self.holy_checkbox.stateChanged.connect(lambda _: self.properties_changed.emit())

    def get_styles(self):
        return {
            "margins": {
                "top": self.m_top.value(), "bottom": self.m_bot.value(),
                "left": self.m_left.value(), "right": self.m_right.value(),
                "gutter": self.m_gut.value()
            },
            "fonts": {
                "arabic": self.ar_font.currentText(), "arabic_size": self.ar_size.value(), "arabic_align": self.ar_align.currentText().lower(),
                "urdu": self.ur_font.currentText(), "urdu_size": self.ur_size.value(), "urdu_align": self.ur_align.currentText().lower(),
                "gujarati": self.guj_font.currentText(), "gujarati_size": self.guj_size.value(), "gujarati_align": self.guj_align.currentText().lower()
            }
        }

    def save_theme(self):
        styles = self.get_styles()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Theme Preset", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(styles, f, indent=4)
                QMessageBox.information(self, "Success", "Theme saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save theme: {e}")

    def load_theme(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Theme Preset", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    styles = json.load(f)
                
                # Block signals to prevent redundant live preview updates during bulk loading
                self.blockSignals(True)
                
                fonts = styles.get("fonts", {})
                if "arabic" in fonts: self.ar_font.setCurrentText(fonts["arabic"])
                if "arabic_size" in fonts: self.ar_size.setValue(fonts["arabic_size"])
                if "arabic_align" in fonts: self.ar_align.setCurrentText(fonts["arabic_align"].capitalize())
                if "urdu" in fonts: self.ur_font.setCurrentText(fonts["urdu"])
                if "urdu_size" in fonts: self.ur_size.setValue(fonts["urdu_size"])
                if "urdu_align" in fonts: self.ur_align.setCurrentText(fonts["urdu_align"].capitalize())
                if "gujarati" in fonts: self.guj_font.setCurrentText(fonts["gujarati"])
                if "gujarati_size" in fonts: self.guj_size.setValue(fonts["gujarati_size"])
                if "gujarati_align" in fonts: self.guj_align.setCurrentText(fonts["gujarati_align"].capitalize())
                
                margins = styles.get("margins", {})
                if "top" in margins: self.m_top.setValue(margins["top"])
                if "bottom" in margins: self.m_bot.setValue(margins["bottom"])
                if "left" in margins: self.m_left.setValue(margins["left"])
                if "right" in margins: self.m_right.setValue(margins["right"])
                if "gutter" in margins: self.m_gut.setValue(margins["gutter"])
                
                self.blockSignals(False)
                self.properties_changed.emit()
                QMessageBox.information(self, "Success", "Theme loaded successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load theme: {e}")