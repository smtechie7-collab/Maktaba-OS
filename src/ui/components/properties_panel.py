from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QGroupBox, 
                             QFormLayout, QComboBox, QSlider, QLabel, 
                             QCheckBox, QPushButton, QSpinBox, QScrollArea)
from PyQt6.QtCore import Qt

class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

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
        ar_layout.addRow("Font:", self.ar_font)
        ar_layout.addRow("Size:", self.ar_size)
        ar_layout.addRow("", self.ar_size_lbl)
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
        ur_layout.addRow("Font:", self.ur_font)
        ur_layout.addRow("Size:", self.ur_size)
        ur_layout.addRow("", self.ur_size_lbl)
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
        guj_layout.addRow("Font:", self.guj_font)
        guj_layout.addRow("Size:", self.guj_size)
        guj_layout.addRow("", self.guj_size_lbl)
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
        self.m_top, self.m_bot, self.m_left, self.m_right, self.m_gut = [QSpinBox() for _ in range(5)]
        for sb in (self.m_top, self.m_bot, self.m_left, self.m_right): sb.setRange(0, 50); sb.setValue(20)
        self.m_gut.setRange(0, 30); self.m_gut.setValue(10)
        m_layout.addRow("Top:", self.m_top); m_layout.addRow("Bottom:", self.m_bot)
        m_layout.addRow("Left:", self.m_left); m_layout.addRow("Right:", self.m_right)
        m_layout.addRow("Gutter:", self.m_gut)
        margins_group.setLayout(m_layout)
        l_layout.addWidget(margins_group)
        l_layout.addStretch()
        self.tabs.addTab(layout_tab, "📐 Layout")

        layout.addWidget(self.tabs)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def get_styles(self):
        return {
            "margins": {
                "top": self.m_top.value(), "bottom": self.m_bot.value(),
                "left": self.m_left.value(), "right": self.m_right.value(),
                "gutter": self.m_gut.value()
            },
            "fonts": {
                "arabic": self.ar_font.currentText(), "arabic_size": self.ar_size.value(),
                "urdu": self.ur_font.currentText(), "urdu_size": self.ur_size.value(),
                "gujarati": self.guj_font.currentText(), "gujarati_size": self.guj_size.value()
            }
        }