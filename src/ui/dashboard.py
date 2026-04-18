import sys
import os
import json
import re  # NAYA IMPORT: Regex use karne ke liye for unicode detection

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QMessageBox, QFrame, QLineEdit, QDialog, QFormLayout,
                             QComboBox, QTextEdit, QSpinBox, QFileDialog, QTreeWidget,
                             QTreeWidgetItem, QSplitter, QTabWidget, QSlider, QCheckBox,
                             QGroupBox, QColorDialog, QScrollArea)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator
from src.utils.md_exporter import MarkdownExporter

# Import Decoupled Components
from src.ui.components.editor_panel import EditorPanel
from src.ui.components.audio_panel import AudioPanel

class PDFWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, book_id, output_path, styles=None):
        super().__init__()
        self.book_id = book_id
        self.output_path = output_path
        self.styles = styles

    def run(self):
        try:
            generator = PDFGenerator()
            generator.generate_pdf(self.book_id, self.output_path, styles=self.styles)
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class BookDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Book")
        self.setMinimumWidth(400)
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
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)

    def get_data(self):
        return {
            "title": self.title_input.text(),
            "author": self.author_input.text(),
            "language": self.lang_input.currentText().lower()[:2] if self.lang_input.currentText() != "Multilingual" else "multi"
        }

class ChapterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Chapter")
        self.setMinimumWidth(400)
        self.layout = QFormLayout(self)

        self.title_input = QLineEdit()
        self.seq_input = QSpinBox()
        self.seq_input.setMinimum(1)
        self.seq_input.setMaximum(1000)

        self.layout.addRow("Chapter Title:", self.title_input)
        self.layout.addRow("Sequence Number:", self.seq_input)

        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save Chapter")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)

    def get_data(self):
        return {
            "title": self.title_input.text(),
            "sequence": self.seq_input.value()
        }

class ContentBlockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Content Block")
        self.setMinimumWidth(500)
        self.layout = QFormLayout(self)

        self.ar_input = QTextEdit()
        self.ar_input.setPlaceholderText("Arabic text here...")
        self.ar_input.setMaximumHeight(100)
        self.ar_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.ur_input = QTextEdit()
        self.ur_input.setPlaceholderText("Urdu translation here...")
        self.ur_input.setMaximumHeight(100)
        self.ur_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.en_input = QTextEdit()
        self.en_input.setPlaceholderText("English translation here...")
        self.en_input.setMaximumHeight(100)
        
        self.ref_input = QLineEdit()
        self.ref_input.setPlaceholderText("e.g. Bukhari 123")

        self.layout.addRow("Arabic Text:", self.ar_input)
        self.layout.addRow("Urdu Text:", self.ur_input)
        self.layout.addRow("English Text:", self.en_input)
        self.layout.addRow("Reference:", self.ref_input)

        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save Block")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)

    def get_data(self):
        return {
            "ar": self.ar_input.toPlainText().strip(),
            "ur": self.ur_input.toPlainText().strip(),
            "en": self.en_input.toPlainText().strip(),
            "reference": self.ref_input.text().strip()
        }

class BulkImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Import - Smart Text Converter")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.layout = QVBoxLayout(self)

        info_text = """
        <b>Smart Parser Instructions:</b><br>
        Paste your raw text below. Use double newlines to separate blocks.<br>
        <i>The system will auto-detect languages based on Unicode characters:</i><br>
        - Arabic (ar): U+0600-U+06FF<br>
        - Urdu (ur): Automatically falls back to Urdu if Arabic is already filled.<br>
        - Gujarati (guj): U+0A80-U+0AFF<br>
        - Hinglish/English (en): Basic Latin A-Z.
        """
        self.layout.addWidget(QLabel(info_text))

        self.raw_text = QTextEdit()
        self.raw_text.setPlaceholderText("Paste your Dalail multi-language text here...\n\nExample:\nبِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ\nاللہ کے نام سے شروع جو بڑا مہربان نہایت رحم والا ہے\nબિસ્મિલ્લાહિર રહેમાનિર રહીમ\nBismillah ir Rahman ir Raheem\n\n(Leave an empty line between blocks)")
        self.layout.addWidget(self.raw_text)

        # Config Panel
        config_group = QGroupBox("Import Configuration")
        config_layout = QFormLayout()
        
        self.separator_input = QLineEdit("\n\n")
        self.separator_input.setMaximumWidth(150)
        config_layout.addRow("Block Separator (Regex allowed):", self.separator_input)
        
        self.day_combo = QComboBox()
        self.day_combo.addItems(["All Days", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        config_layout.addRow("Assign Day:", self.day_combo)
        
        self.track_combo = QComboBox()
        self.track_combo.addItems(["T1 (Daily Base)", "T2 (Dua Iftitah)", "T3 (Monday Hizb)", "T4 (Tuesday)", "T5 (Wednesday)", "T6 (Thursday)", "T7 (Friday)", "T8 (Saturday)", "T9 (Sunday)", "T10 (Shajra)"])
        config_layout.addRow("Assign Track:", self.track_combo)
        
        self.section_combo = QComboBox()
        self.section_combo.addItems(["General", "Muqaddama", "Asma-ul-Husna", "Dua-e-Iftitah", "Hizb", "Shajra"])
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

class MaktabaDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager("maktaba_production.db")
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Maktaba-OS | Digital Publishing Dashboard")
        self.setMinimumSize(1000, 700)
        
        # Apply High-Contrast Dark Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a0a; }
            QWidget { 
                color: #ffffff; 
                font-family: 'Segoe UI', sans-serif; 
                font-size: 14px;
            }
            QLabel { font-weight: 500; }
            QListWidget, QTreeWidget { 
                background-color: #161616; 
                border: 1px solid #333; 
                border-radius: 5px; 
                padding: 10px;
                font-size: 14px;
                color: #ffffff;
            }
            QListWidget::item { padding: 12px; border-bottom: 1px solid #222; }
            QListWidget::item:selected, QTreeWidget::item:selected { background-color: #3d5afe; color: white; border-radius: 3px; font-weight: bold; }
            
            QPushButton { 
                background-color: #2a2a2a; 
                color: #ffffff;
                border: 1px solid #444; 
                padding: 12px; 
                border-radius: 5px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3d5afe; border: 1px solid #536dfe; }
            QPushButton#primaryBtn { background-color: #3d5afe; border: 1px solid #536dfe; }
            QPushButton#primaryBtn:hover { background-color: #536dfe; }
            
            QLabel#header { font-size: 24px; font-weight: bold; color: #3d5afe; margin-bottom: 20px; }
            
            QLineEdit, QTextEdit, QSpinBox, QComboBox { 
                background-color: #161616; 
                border: 1px solid #333; 
                padding: 10px; 
                border-radius: 5px; 
                color: #ffffff;
                font-weight: bold;
            }
            QLineEdit:focus, QTextEdit:focus { border: 1px solid #3d5afe; }
            
            QTabWidget::pane { border: 1px solid #333; background: #161616; }
            QTabBar::tab { 
                background: #2a2a2a; 
                color: #bbbbbb; 
                padding: 10px 20px; 
                border-top-left-radius: 4px; 
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: #3d5afe; color: white; font-weight: bold; }
            
            QGroupBox { 
                border: 1px solid #333; 
                border-radius: 8px; 
                margin-top: 15px; 
                font-weight: bold; 
                padding-top: 15px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #3d5afe; }
        """)

        # Main Layout with 3 panels
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Use QSplitter for resizable panels
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # ============================================
        # LEFT SIDEBAR (Navigation: Days & Chapters)
        # ============================================
        left_widget = QWidget()
        left_widget.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)

        header_label = QLabel("📚 Navigation")
        header_label.setObjectName("header")
        left_layout.addWidget(header_label)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search books...")
        self.search_bar.textChanged.connect(self.load_books)
        left_layout.addWidget(self.search_bar)

        btn_layout = QHBoxLayout()
        self.add_book_btn = QPushButton("+ New")
        self.add_book_btn.setObjectName("primaryBtn")
        self.add_book_btn.clicked.connect(self.show_add_book_dialog)
        btn_layout.addWidget(self.add_book_btn)

        self.open_project_btn = QPushButton("📂 Open")
        self.open_project_btn.clicked.connect(self.handle_open_project)
        btn_layout.addWidget(self.open_project_btn)
        left_layout.addLayout(btn_layout)

        self.book_list = QListWidget()
        self.book_list.itemSelectionChanged.connect(self.handle_selection_change)
        self.load_books()
        left_layout.addWidget(self.book_list)

        self.add_chapter_btn = QPushButton("+ Add Chapter")
        self.add_chapter_btn.clicked.connect(self.show_add_chapter_dialog)
        left_layout.addWidget(self.add_chapter_btn)

        self.add_content_btn = QPushButton("+ Add Content Block")
        self.add_content_btn.clicked.connect(self.show_add_content_dialog)
        left_layout.addWidget(self.add_content_btn)

        self.bulk_import_btn = QPushButton("📥 Bulk Import")
        self.bulk_import_btn.clicked.connect(self.show_bulk_import_dialog)
        left_layout.addWidget(self.bulk_import_btn)

        self.main_splitter.addWidget(left_widget)
        self.left_widget = left_widget

        # ============================================
        # CENTER PANEL (Main Workspace)
        # ============================================
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(5, 5, 5, 5)

        center_header = QLabel("✏️ Editor Workspace")
        center_header.setObjectName("header")
        center_layout.addWidget(center_header)

        self.center_tabs = QTabWidget()
        self.center_tabs.setTabPosition(QTabWidget.TabPosition.North)

        # --- DYNAMIC EDITOR PANEL (Decoupled Component) ---
        self.editor_panel = EditorPanel()
        self.editor_panel.save_requested.connect(self.save_content_block)
        self.editor_panel.focus_mode_btn.clicked.connect(self.toggle_focus_mode)
        self.editor_panel.preview_mode_btn.clicked.connect(self.toggle_preview_mode)
        self.center_tabs.addTab(self.editor_panel, "📝 Text Editor")

        # --- AUDIO PANEL (Decoupled Component) ---
        self.audio_panel = AudioPanel()
        self.center_tabs.addTab(self.audio_panel, "🎵 Audio Engine")

        # --- PDF PREVIEW TAB ---
        self.pdf_preview_tab = QWidget()
        pdf_layout = QVBoxLayout(self.pdf_preview_tab)
        pdf_header = QLabel("📄 PDF Preview")
        pdf_header.setStyleSheet("font-size: 16px; font-weight: bold;")
        pdf_layout.addWidget(pdf_header)
        self.pdf_preview_label = QLabel("Select a book and click 'Generate PDF' to view")
        self.pdf_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pdf_preview_label.setStyleSheet("padding: 50px; color: #ffffff; font-weight: bold;")
        pdf_layout.addWidget(self.pdf_preview_label)
        self.center_tabs.addTab(self.pdf_preview_tab, "📄 PDF Preview")

        center_layout.addWidget(self.center_tabs)
        self.main_splitter.addWidget(center_widget)

        # ============================================
        # RIGHT SIDEBAR (Properties Panel)
        # ============================================
        right_widget = QWidget()
        right_widget.setMaximumWidth(300)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)

        right_header = QLabel("⚙️ Properties")
        right_header.setObjectName("header")
        right_layout.addWidget(right_header)

        self.properties_tabs = QTabWidget()

        # 1. Typography Settings Tab
        self.typography_tab = QWidget()
        typo_layout = QVBoxLayout(self.typography_tab)

        ar_font_group = QGroupBox("Arabic Font")
        ar_font_layout = QFormLayout()
        self.ar_font_combo = QComboBox()
        self.ar_font_combo.addItems(["Amiri", "Noor-e-Huda", "Alvi Nastaleeq", "Jameel Noori Nastaliq", "Traditional Arabic"])
        ar_font_layout.addRow("Font:", self.ar_font_combo)
        self.ar_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.ar_size_slider.setMinimum(12)
        self.ar_size_slider.setMaximum(72)
        self.ar_size_slider.setValue(24)
        self.ar_size_label = QLabel("24 pt")
        self.ar_size_slider.valueChanged.connect(lambda v: self.ar_size_label.setText(f"{v} pt"))
        ar_font_layout.addRow("Size:", self.ar_size_slider)
        ar_font_layout.addRow("", self.ar_size_label)
        ar_font_group.setLayout(ar_font_layout)
        typo_layout.addWidget(ar_font_group)

        ur_font_group = QGroupBox("Urdu Font")
        ur_font_layout = QFormLayout()
        self.ur_font_combo = QComboBox()
        self.ur_font_combo.addItems(["Jameel Noori Nastaliq", "Alvi Nastaleeq", "Nafees Nastaleeq", "Pak Urdu Naskh"])
        ur_font_layout.addRow("Font:", self.ur_font_combo)
        self.ur_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.ur_size_slider.setMinimum(12)
        self.ur_size_slider.setMaximum(72)
        self.ur_size_slider.setValue(20)
        self.ur_size_label = QLabel("20 pt")
        self.ur_size_slider.valueChanged.connect(lambda v: self.ur_size_label.setText(f"{v} pt"))
        ur_font_layout.addRow("Size:", self.ur_size_slider)
        ur_font_layout.addRow("", self.ur_size_label)
        ur_font_group.setLayout(ur_font_layout)
        typo_layout.addWidget(ur_font_group)

        guj_font_group = QGroupBox("Gujarati Font")
        guj_font_layout = QFormLayout()
        self.guj_font_combo = QComboBox()
        self.guj_font_combo.addItems(["Noto Sans Gujarati", "Aakar", "Mahashakti", "Sahadeva"])
        guj_font_layout.addRow("Font:", self.guj_font_combo)
        self.guj_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.guj_size_slider.setMinimum(12)
        self.guj_size_slider.setMaximum(48)
        self.guj_size_slider.setValue(16)
        self.guj_size_label = QLabel("16 pt")
        self.guj_size_slider.valueChanged.connect(lambda v: self.guj_size_label.setText(f"{v} pt"))
        guj_font_layout.addRow("Size:", self.guj_size_slider)
        guj_font_layout.addRow("", self.guj_size_label)
        guj_font_group.setLayout(guj_font_layout)
        typo_layout.addWidget(guj_font_group)

        self.holy_names_checkbox = QCheckBox("✨ Highlight Holy Names (Allah/محمد ﷺ)")
        self.holy_names_checkbox.setChecked(True)
        self.holy_names_checkbox.stateChanged.connect(self.toggle_holy_highlighter)
        typo_layout.addWidget(self.holy_names_checkbox)

        typo_layout.addStretch()
        self.properties_tabs.addTab(self.typography_tab, "🔤 Typography")

        # 2. Layout Settings Tab
        self.layout_tab = QWidget()
        layout_layout = QVBoxLayout(self.layout_tab)

        theme_group = QGroupBox("📅 Day-Wise Theme")
        theme_layout = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["None", "Monday (Blue Border)", "Tuesday (Green Border)", "Wednesday (Orange Border)",
                                   "Thursday (Purple Border)", "Friday (Golden Border)", "Saturday (Silver Border)", "Sunday (White Border)"])
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addRow("Border:", self.theme_combo)
        self.border_color_btn = QPushButton("🎨 Border Color")
        self.border_color_btn.clicked.connect(self.choose_border_color)
        theme_layout.addRow("", self.border_color_btn)
        theme_group.setLayout(theme_layout)
        layout_layout.addWidget(theme_group)

        margins_group = QGroupBox("📐 Page Margins (mm)")
        margins_layout = QFormLayout()
        self.top_margin = QSpinBox()
        self.top_margin.setRange(0, 50)
        self.top_margin.setValue(20)
        margins_layout.addRow("Top:", self.top_margin)

        self.bottom_margin = QSpinBox()
        self.bottom_margin.setRange(0, 50)
        self.bottom_margin.setValue(20)
        margins_layout.addRow("Bottom:", self.bottom_margin)

        self.left_margin = QSpinBox()
        self.left_margin.setRange(0, 50)
        self.left_margin.setValue(15)
        margins_layout.addRow("Left:", self.left_margin)

        self.right_margin = QSpinBox()
        self.right_margin.setRange(0, 50)
        self.right_margin.setValue(15)
        margins_layout.addRow("Right:", self.right_margin)

        self.gutter_margin = QSpinBox()
        self.gutter_margin.setRange(0, 30)
        self.gutter_margin.setValue(10)
        margins_layout.addRow("Gutter:", self.gutter_margin)
        margins_group.setLayout(margins_layout)
        layout_layout.addWidget(margins_group)

        export_group = QGroupBox("📤 Export Options")
        export_layout = QVBoxLayout()

        self.export_md_btn = QPushButton("📝 Export Markdown")
        self.export_md_btn.clicked.connect(self.handle_export_md)
        export_layout.addWidget(self.export_md_btn)

        self.export_draft_btn = QPushButton("📄 Export Draft PDF (Low Quality)")
        self.export_draft_btn.clicked.connect(self.handle_export_draft_pdf)
        export_layout.addWidget(self.export_draft_btn)

        self.export_press_btn = QPushButton("🖨 Export Press-Ready (300 DPI CMYK)")
        self.export_press_btn.setObjectName("primaryBtn")
        self.export_press_btn.clicked.connect(self.handle_export_press_pdf)
        export_layout.addWidget(self.export_press_btn)

        self.export_maktaba_btn = QPushButton("📦 Export .maktaba Format")
        self.export_maktaba_btn.clicked.connect(self.handle_export_maktaba)
        export_layout.addWidget(self.export_maktaba_btn)

        export_group.setLayout(export_layout)
        layout_layout.addWidget(export_group)

        layout_layout.addStretch()
        self.properties_tabs.addTab(self.layout_tab, "📐 Layout")
        
        # Metadata Section
        self.metadata_label = QLabel("Details")
        self.metadata_label.setObjectName("header")
        right_layout.addWidget(self.metadata_label)

        self.details_area = QLabel("Select a book to see details")
        self.details_area.setWordWrap(True)
        self.details_area.setStyleSheet("background-color: #1e1e1e; padding: 15px; border-radius: 5px; border: 1px solid #333;")
        right_layout.addWidget(self.details_area)
        
        # Chapter Tree initialized correctly to avoid crash
        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["Content Title", "Type"])
        self.chapter_tree.setStyleSheet("background-color: #161616; color: #fff; border: 1px solid #333; margin-top: 10px;")
        right_layout.addWidget(self.chapter_tree)

        right_layout.addSpacing(20)
        right_layout.addWidget(self.properties_tabs)
        self.right_widget = right_widget

        refresh_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_books)
        refresh_layout.addWidget(self.refresh_btn)

        self.gen_pdf_btn = QPushButton("📄 Generate PDF")
        self.gen_pdf_btn.setObjectName("primaryBtn")
        self.gen_pdf_btn.clicked.connect(self.handle_pdf_generation)
        refresh_layout.addWidget(self.gen_pdf_btn)
        right_layout.addWidget(QFrame()) # spacer
        right_layout.addLayout(refresh_layout)

        self.main_splitter.addWidget(right_widget)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 3)
        self.main_splitter.setStretchFactor(2, 1)

        # Initialize Status Bar
        self.statusBar().showMessage("Ready")
        self.focus_mode_active = False

    def handle_open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Maktaba Project", "", "Maktaba Files (*.maktaba)"
        )
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            book_id = self.db.add_book(
                f"Imported: {os.path.basename(file_path)}", 
                "Unknown", 
                "multi",
                metadata=data.get("typography")
            )
            
            chap_id = self.db.add_chapter(book_id, "Imported Content", 1)
            
            blocks = data.get("content", [])
            for block in blocks:
                block_data = json.loads(block['content_data']) if isinstance(block['content_data'], str) else block['content_data']
                self.db.add_content_block(chap_id, block_data)
            
            self.load_books()
            self.statusBar().showMessage(f"Project imported successfully! ID: {book_id}", 5000)
            QMessageBox.information(self, "Success", "Project imported as a new book.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project: {str(e)}")

    def load_books(self):
        search_query = self.search_bar.text().lower()
        self.book_list.clear()
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, author FROM Books")
            for row in cursor.fetchall():
                display_text = f"{row['id']} - {row['title']}"
                author = row['author'] if row['author'] else ""
                if search_query in display_text.lower() or search_query in author.lower():
                    self.book_list.addItem(display_text)

    def show_add_book_dialog(self):
        dialog = BookDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['title']:
                QMessageBox.warning(self, "Validation Error", "Book title is required!")
                return
            try:
                self.db.add_book(data['title'], data['author'], data['language'])
                self.load_books()
                QMessageBox.information(self, "Success", f"Book '{data['title']}' added successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add book: {str(e)}")

    def show_add_chapter_dialog(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        dialog = ChapterDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data['title']:
                QMessageBox.warning(self, "Validation Error", "Chapter title is required!")
                return
            try:
                self.db.add_chapter(book_id, data['title'], data['sequence'])
                self.load_book_details(book_id)
                QMessageBox.information(self, "Success", f"Chapter '{data['title']}' added successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add chapter: {str(e)}")

    def show_add_content_dialog(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM Chapters WHERE book_id = ? ORDER BY sequence_number", (book_id,))
            chapters = cursor.fetchall()
            
        if not chapters:
            QMessageBox.warning(self, "No Chapters", "Please create a chapter first!")
            return

        items = [f"{c['id']} - {c['title']}" for c in chapters]
        from PyQt6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(self, "Select Chapter", "Add content to:", items, 0, False)
        
        if ok and item:
            chapter_id = int(item.split(" - ")[0])
            dialog = ContentBlockDialog(self)
            if dialog.exec():
                data = dialog.get_data()
                if not any([data['ar'], data['ur'], data['en']]):
                    QMessageBox.warning(self, "Validation Error", "At least one text field is required!")
                    return
                try:
                    self.db.add_content_block(chapter_id, data)
                    self.load_book_details(book_id)
                    QMessageBox.information(self, "Success", "Content block added successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add content: {str(e)}")

    def show_bulk_import_dialog(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM Chapters WHERE book_id = ? ORDER BY sequence_number", (book_id,))
            chapters = cursor.fetchall()
            
        if not chapters:
            QMessageBox.warning(self, "No Chapters", "Please create a chapter first!")
            return

        items = [f"{c['id']} - {c['title']}" for c in chapters]
        from PyQt6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(self, "Select Chapter", "Bulk Import to:", items, 0, False)
        
        if ok and item:
            chapter_id = int(item.split(" - ")[0])
            dialog = BulkImportDialog(self)
            if dialog.exec():
                data = dialog.get_data()
                raw_text = data['text']
                separator = data['separator']
                metadata = data['metadata']
                
                if not raw_text.strip():
                    return
                
                # Split using simple separator or regex if it looks like regex
                if '\\' in separator or separator == '\n\n':
                     # Basic split for simple double newlines
                     blocks = re.split(r'\n\s*\n', raw_text.strip())
                else:
                     blocks = raw_text.split(separator)
                
                imported_count = 0
                
                for block in blocks:
                    lines = block.strip().split("\n")
                    if not lines: continue
                    
                    block_data = {
                        "ar": "",
                        "ur": "",
                        "guj": "",
                        "en": "",
                        "reference": "",
                        "metadata": metadata
                    }
                    
                    # SMART PARSING LOGIC
                    for line in lines:
                        line = line.strip()
                        if not line: continue
                        
                        # Detect Gujarati (U+0A80 to U+0AFF)
                        if re.search(r'[\u0a80-\u0aff]', line):
                            block_data["guj"] = line
                        # Detect Basic Latin (Hinglish/English)
                        elif re.search(r'^[a-zA-Z0-9\s.,!?\'"-]+$', line):
                            block_data["en"] = line
                        # Detect Arabic/Urdu (U+0600 to U+06FF)
                        elif re.search(r'[\u0600-\u06ff]', line):
                            # Usually Arabic comes first. If empty, put in AR. Else put in UR.
                            if not block_data["ar"]:
                                block_data["ar"] = line
                            else:
                                block_data["ur"] = line
                        else:
                            # Fallback if detection fails (e.g., special symbols)
                            if not block_data["ar"]: block_data["ar"] = line
                            elif not block_data["ur"]: block_data["ur"] = line
                            elif not block_data["guj"]: block_data["guj"] = line
                            else: block_data["en"] = line
                    
                    try:
                        self.db.add_content_block(chapter_id, block_data)
                        imported_count += 1
                    except Exception as e:
                        print(f"Bulk import failed for block: {str(e)}")
                
                self.load_book_details(book_id)
                QMessageBox.information(self, "Import Complete", f"Successfully imported {imported_count} blocks using Smart Parser!")

    def handle_selection_change(self):
        selected = self.book_list.currentItem()
        if not selected:
            if hasattr(self, 'details_area'):
                self.details_area.setText("Select a book to see details")
            if hasattr(self, 'chapter_tree'):
                self.chapter_tree.clear()
            return

        book_id = int(selected.text().split(" - ")[0])
        self.load_book_details(book_id)

    def load_book_details(self, book_id):
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Books WHERE id = ?", (book_id,))
            book = cursor.fetchone()
            
            metadata_str = f"<b>Title:</b> {book['title']}<br>"
            metadata_str += f"<b>Author:</b> {book['author']}<br>"
            metadata_str += f"<b>Language:</b> {book['language']}<br>"
            metadata_str += f"<b>Created:</b> {book['created_at']}<br>"
            if hasattr(self, 'details_area'):
                self.details_area.setText(metadata_str)

        if hasattr(self, 'chapter_tree'):
            self.chapter_tree.clear()
            content = self.db.get_book_content(book_id)
            
            chapters = {}
            for block in content:
                chap_title = block['chapter_title']
                if chap_title not in chapters:
                    chap_item = QTreeWidgetItem(self.chapter_tree, [chap_title, "Chapter"])
                    chap_item.setExpanded(True)
                    chapters[chap_title] = chap_item
                
                block_data = json.loads(block['content_data'])
                preview_text = block_data.get('ar', block_data.get('ur', block_data.get('en', 'Text Block')))[:30] + "..."
                QTreeWidgetItem(chapters[chap_title], [preview_text, "Content"])

    def get_current_styles(self):
        return {
            "margins": {
                "top": self.top_margin.value(),
                "bottom": self.bottom_margin.value(),
                "left": self.left_margin.value(),
                "right": self.right_margin.value(),
                "gutter": self.gutter_margin.value()
            },
            "fonts": {
                "arabic": self.ar_font_combo.currentText(),
                "arabic_size": self.ar_size_slider.value(),
                "urdu": self.ur_font_combo.currentText(),
                "urdu_size": self.ur_size_slider.value(),
                "gujarati": self.guj_font_combo.currentText(),
                "gujarati_size": self.guj_size_slider.value()
            },
            "theme_border_image": f"assets/borders/{self.theme_combo.currentText().split(' ')[0].lower()}.png" if self.theme_combo.currentIndex() > 0 else None
        }

    def handle_pdf_generation(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        book_title = selected.text().split(" - ")[1].replace(" ", "_")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", f"{book_title}.pdf", "PDF Files (*.pdf)"
        )
        if not file_path:
            return

        self.gen_pdf_btn.setEnabled(False)
        self.gen_pdf_btn.setText("Generating...")
        self.statusBar().showMessage(f"Generating PDF for Book ID {book_id}...")
        
        styles = self.get_current_styles()
        self.worker = PDFWorker(book_id, file_path, styles)
        self.worker.finished.connect(self.on_pdf_finished)
        self.worker.start()

    def on_pdf_finished(self, success, message):
        self.gen_pdf_btn.setEnabled(True)
        self.gen_pdf_btn.setText("Generate PDF")
        
        if success:
            self.statusBar().showMessage(f"Successfully generated PDF at {message}", 5000)
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Success")
            msg_box.setText(f"PDF generated successfully at:\n{message}")
            open_btn = msg_box.addButton("Open PDF", QMessageBox.ButtonRole.AcceptRole)
            msg_box.addButton(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            if msg_box.clickedButton() == open_btn:
                os.startfile(os.path.abspath(message))
        else:
            self.statusBar().showMessage("PDF Generation Failed!", 5000)
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {message}")

    def toggle_holy_highlighter(self, state):
        self.editor_panel.toggle_holy_highlighter(state)

    def toggle_focus_mode(self, checked):
        self.focus_mode_active = checked
        if checked:
            self.left_widget.hide()
            self.right_widget.hide()
            self.center_tabs.setTabVisible(1, False)
            self.center_tabs.setTabVisible(2, False)
            self.statusBar().showMessage("Focus Mode Active - Press ESC to exit", 5000)
        else:
            self.left_widget.show()
            self.right_widget.show()
            self.center_tabs.setTabVisible(1, True)
            self.center_tabs.setTabVisible(2, True)
            self.statusBar().showMessage("Ready")

    def toggle_preview_mode(self, checked):
        if checked:
            self.center_tabs.setCurrentIndex(2)
        else:
            self.center_tabs.setCurrentIndex(0)

    def on_theme_changed(self, index):
        themes = {
            1: ("Monday", "#2196F3"),
            2: ("Tuesday", "#4CAF50"),
            3: ("Wednesday", "#FF9800"),
            4: ("Thursday", "#9C27B0"),
            5: ("Friday", "#FFD700"),
            6: ("Saturday", "#C0C0C0"),
            7: ("Sunday", "#FFFFFF")
        }
        if index in themes:
            self.statusBar().showMessage(f"Theme applied: {themes[index][0]} Border", 3000)

    def choose_border_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.statusBar().showMessage(f"Border color selected: {color.name()}", 3000)

    def save_content_block(self, data):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM Chapters WHERE book_id = ? ORDER BY sequence_number DESC LIMIT 1", (book_id,))
            result = cursor.fetchone()
            if not result:
                QMessageBox.warning(self, "No Chapter", "Please create a chapter first!")
                return
            chapter_id = result[0]

        try:
            self.db.add_content_block(chapter_id, data)
            self.load_book_details(book_id)
            self.editor_panel.clear_fields()
            self.statusBar().showMessage("Content block saved successfully!", 3000)
            QMessageBox.information(self, "Success", "Content block saved!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

    def handle_export_md(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        book_title = selected.text().split(" - ")[1].replace(" ", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Markdown", f"{book_title}.md", "Markdown Files (*.md)"
        )

        if not file_path:
            return

        try:
            exporter = MarkdownExporter()
            exporter.export_book(book_id, file_path)
            self.statusBar().showMessage(f"Markdown exported to {file_path}", 5000)
            QMessageBox.information(self, "Success", f"Markdown exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

    def handle_export_draft_pdf(self):
        self.handle_pdf_generation()

    def handle_export_press_pdf(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        book_title = selected.text().split(" - ")[1].replace(" ", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Press-Ready PDF", f"{book_title}_press.pdf", "PDF Files (*.pdf)"
        )

        if not file_path:
            return

        self.statusBar().showMessage("Generating Press-Ready PDF (300 DPI CMYK)...", 5000)
        self.export_press_btn.setEnabled(False)

        class PressPDFWorker(QThread):
            finished = pyqtSignal(bool, str)
            def __init__(self, book_id, output_path, styles):
                super().__init__()
                self.book_id = book_id
                self.output_path = output_path
                self.styles = styles
            def run(self):
                try:
                    generator = PDFGenerator()
                    generator.generate_pdf(self.book_id, self.output_path, press_ready=True, styles=self.styles)
                    self.finished.emit(True, self.output_path)
                except Exception as e:
                    self.finished.emit(False, str(e))

        styles = self.get_current_styles()
        self.press_worker = PressPDFWorker(book_id, file_path, styles)
        self.press_worker.finished.connect(lambda success, msg: self.on_press_pdf_finished(success, msg, file_path))
        self.press_worker.start()

    def on_press_pdf_finished(self, success, message, file_path):
        self.export_press_btn.setEnabled(True)
        if success:
            self.statusBar().showMessage(f"Press-Ready PDF saved: {file_path}", 5000)
            QMessageBox.information(self, "Success", f"Press-Ready PDF exported!\n{file_path}")
        else:
            QMessageBox.critical(self, "Error", f"Failed: {message}")

    def handle_export_maktaba(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        book_title = selected.text().split(" - ")[1].replace(" ", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export .maktaba Package", f"{book_title}.maktaba", "Maktaba Files (*.maktaba)"
        )

        if not file_path:
            return

        try:
            content = self.db.get_book_content(book_id)
            maktaba_data = {
                "book_id": book_id,
                "content": content,
                "typography": {
                    "arabic_font": self.ar_font_combo.currentText(),
                    "arabic_size": self.ar_size_slider.value(),
                    "urdu_font": self.ur_font_combo.currentText(),
                    "urdu_size": self.ur_size_slider.value(),
                    "gujarati_font": self.guj_font_combo.currentText(),
                    "gujarati_size": self.guj_size_slider.value()
                },
                "margins": {
                    "top": self.top_margin.value(),
                    "bottom": self.bottom_margin.value(),
                    "left": self.left_margin.value(),
                    "right": self.right_margin.value(),
                    "gutter": self.gutter_margin.value()
                }
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(maktaba_data, f, indent=2, ensure_ascii=False)

            self.statusBar().showMessage(f".maktaba file exported: {file_path}", 5000)
            QMessageBox.information(self, "Success", f".maktaba file exported successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = MaktabaDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
