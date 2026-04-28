import sys
import os
import json
import re
import glob
import importlib.util
import copy

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QMessageBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
                             QTabWidget, QDockWidget, QFileDialog, QTextBrowser, QMenuBar, QMenu, QStackedWidget,
                             QListWidgetItem, QFrame, QStyle, QComboBox, QAbstractItemView, QSplitter, QProgressDialog,
                             QCheckBox, QGroupBox, QSlider, QFormLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QSize, QMimeData
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QPixmap, QIcon

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    WEB_ENGINE_AVAILABLE = True
except ImportError as e:
    WEB_ENGINE_AVAILABLE = False

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator
from src.layout.epub_generator import EPUBGenerator
from src.core.config import load_config
from src.core.errors import install_global_exception_handler
from src.ui.dialogs import BookDialog, ChapterDialog, BulkImportDialog, TemplateBuilderDialog, ExportDialog
from src.ui.components.editor_panel import EditorPanel
from src.ui.components.audio_panel import AudioPanel
from src.ui.components.properties_panel import PropertiesPanel
from src.ui.components.web_bridge import WebBridge
from src.ui.components.command_palette import CommandPalette
from src.ui.search_dialog import SearchReplaceDialog
from src.ui.workers import DbWorker
from src.ui.styles.style_loader import load_stylesheet
from src.utils.tajweed_parser import TajweedEngine

class BookCard(QFrame):
    """Custom Widget to display a Book in the Library Grid like a professional bookshelf card."""
    def __init__(self, title, author, lang, cover_path=None):
        super().__init__()
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.cover_label = QLabel()
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setFixedSize(140, 190)
        
        if cover_path and os.path.exists(cover_path):
            pixmap = QPixmap(cover_path)
            # Smooth scaling for professional image render
            self.cover_label.setPixmap(pixmap.scaled(140, 190, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            self.cover_label.setStyleSheet("border-radius: 6px; border: 1px solid #E2E8F0;")
        else:
            self.cover_label.setText("📘\nNo Cover")
            self.cover_label.setStyleSheet("background-color: #F1F5F9; border-radius: 6px; font-size: 24px; color: #94A3B8; border: 1px dashed #CBD5E1;")

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #0F172A;")

        self.meta_label = QLabel(f"{author[:15]} • {lang.upper()}")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self.meta_label.setStyleSheet("font-size: 11px; color: #64748B;")

        layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label, stretch=1)
        layout.addWidget(self.meta_label)

class AssetListWidget(QListWidget):
    def mimeData(self, items):
        mime_data = QMimeData()
        urls = []
        for item in items:
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:
                urls.append(QUrl(url))
        mime_data.setUrls(urls)
        return mime_data

class AssetManagerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Images")
        self.add_btn.setObjectName("secondaryBtn")
        self.add_btn.clicked.connect(self.add_images)
        toolbar.addWidget(QLabel("Drag & Drop into Preview"))
        toolbar.addStretch()
        toolbar.addWidget(self.add_btn)
        layout.addLayout(toolbar)
        
        self.list_widget = AssetListWidget()
        self.list_widget.setViewMode(QListWidget.ViewMode.IconMode)
        self.list_widget.setIconSize(QSize(90, 90))
        self.list_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list_widget.setDragEnabled(True)
        self.list_widget.setSpacing(10)
        self.list_widget.setStyleSheet("QListWidget { background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 6px; } QListWidget::item { padding: 5px; } QListWidget::item:selected { background: #E2E8F0; }")
        layout.addWidget(self.list_widget)
        
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assets_dir = os.path.join(app_dir, "assets", "images")
        os.makedirs(self.assets_dir, exist_ok=True)
        self.load_assets()
        
    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Images", "", "Images (*.png *.jpg *.jpeg *.svg)")
        import shutil
        for f in files:
            dest = os.path.join(self.assets_dir, os.path.basename(f))
            if not os.path.exists(dest) or f != dest:
                shutil.copy(f, dest)
        self.load_assets()
        
    def load_assets(self):
        self.list_widget.clear()
        for f in glob.glob(os.path.join(self.assets_dir, "*.*")):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                item = QListWidgetItem(QIcon(f), os.path.basename(f)[:12] + "...")
                item.setToolTip(os.path.basename(f))
                file_url = QUrl.fromLocalFile(f).toString()
                item.setData(Qt.ItemDataRole.UserRole, file_url)
                self.list_widget.addItem(item)

class VisualPropertyInspector(QGroupBox):
    properties_changed = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__("✨ Visual Typography Inspector", parent)
        layout = QFormLayout(self)
        
        self.drop_cap_slider = QSlider(Qt.Orientation.Horizontal)
        self.drop_cap_slider.setRange(0, 80)
        self.drop_cap_slider.setValue(0)
        self.drop_cap_slider.setToolTip("Size of the first letter (Drop Cap) in pts. 0 disables it.")
        self.drop_cap_slider.valueChanged.connect(self.properties_changed.emit)
        
        self.leading_slider = QSlider(Qt.Orientation.Horizontal)
        self.leading_slider.setRange(10, 40)
        self.leading_slider.setValue(14)
        self.leading_slider.setToolTip("Line height multiplier (Leading).")
        self.leading_slider.valueChanged.connect(self.properties_changed.emit)
        
        self.kerning_slider = QSlider(Qt.Orientation.Horizontal)
        self.kerning_slider.setRange(-5, 20)
        self.kerning_slider.setValue(0)
        self.kerning_slider.setToolTip("Letter spacing in pts (Kerning).")
        self.kerning_slider.valueChanged.connect(self.properties_changed.emit)
        
        layout.addRow("Drop Cap Size:", self.drop_cap_slider)
        layout.addRow("Line Height:", self.leading_slider)
        layout.addRow("Kerning (Spacing):", self.kerning_slider)
        
        self.setStyleSheet("QSlider::handle:horizontal { background: #176B87; width: 14px; margin: -4px 0; border-radius: 7px; } QSlider::groove:horizontal { background: #CBD5E1; height: 6px; border-radius: 3px; }")

    def get_values(self):
        return {
            "drop_cap": self.drop_cap_slider.value(),
            "leading": self.leading_slider.value() / 10.0,
            "kerning": self.kerning_slider.value()
        }

class PDFWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, book_id, output_path, styles=None):
        super().__init__()
        self.book_id = book_id; self.output_path = output_path; self.styles = styles
    def run(self):
        try:
            generator = PDFGenerator()
            generator.generate_pdf(self.book_id, self.output_path, styles=self.styles)
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class EPUBWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, book_id, output_path, styles=None):
        super().__init__()
        self.book_id = book_id; self.output_path = output_path; self.styles = styles
    def run(self):
        try:
            generator = EPUBGenerator()
            generator.generate_epub(self.book_id, self.output_path, styles=self.styles)
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class DOCXWorker(QThread):
    finished = pyqtSignal(bool, str)
    def __init__(self, book_id, output_path, styles=None):
        super().__init__()
        self.book_id = book_id; self.output_path = output_path; self.styles = styles
    def run(self):
        try:
            from src.layout.docx_generator import DOCXGenerator
            generator = DOCXGenerator()
            generator.generate_docx(self.book_id, self.output_path, styles=self.styles)
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class PreviewWorker(QThread):
    finished = pyqtSignal(int, bool, str)

    def __init__(self, request_id, book_id, db_path, template_dir, draft_data, styles, active_chapter_id=None, preview_mode="Full Book"):
        super().__init__()
        self.request_id = request_id
        self.book_id = book_id
        self.db_path = db_path
        self.template_dir = template_dir
        self.draft_data = draft_data
        self.styles = styles
        self.active_chapter_id = active_chapter_id
        self.preview_mode = preview_mode

    def run(self):
        try:
            from jinja2 import Environment, FileSystemLoader

            db = DatabaseManager(self.db_path)
            env = Environment(loader=FileSystemLoader(self.template_dir))
            template = env.get_template("book_template.html")

            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, author, language, metadata FROM Books WHERE id = ?", (self.book_id,))
                book_info = cursor.fetchone()
                
            book_metadata = {}
            is_rtl = False
            if book_info:
                is_rtl = book_info['language'] in ['ar', 'ur']
                if book_info['metadata']:
                    book_metadata = json.loads(book_info['metadata']) if isinstance(book_info['metadata'], str) else book_info['metadata']

            m = self.styles.get("margins", {})
            page_geometry = {
                "top": m.get("top", 20),
                "bottom": m.get("bottom", 20),
                "inside": m.get("left", 15) + m.get("gutter", 10),
                "outside": m.get("right", 15),
                "chapter_break": "left" if is_rtl else "right"
            }

            content_blocks = db.get_book_content(self.book_id)
            chapters_data = []
            current_chapter_id = None
            current_chapter_dict = None

            for block in content_blocks:
                if block['chapter_id'] != current_chapter_id:
                    current_chapter_id = block['chapter_id']
                    current_chapter_dict = {
                        "chapter_id": block['chapter_id'],
                        "chapter_title": block['chapter_title'],
                        "chapter_type": block.get('chapter_type', 'Content Chapter'),
                        "blocks": []
                    }
                    chapters_data.append(current_chapter_dict)

                if block['block_id']:
                    content_data = json.loads(block['content_data'])
                    if self.styles.get("enable_tajweed") and content_data.get('ar'):
                        content_data['ar'] = TajweedEngine.apply_html(content_data['ar'])
                        
                    current_chapter_dict['blocks'].append({
                        "block_id": block['block_id'],
                        "content_data": content_data,
                        "content_type": block['content_type'],
                        "footnotes": block.get('footnotes', [])
                    })

            if self.preview_mode == "Active Chapter" and self.active_chapter_id:
                chapters_data = [c for c in chapters_data if c["chapter_id"] == self.active_chapter_id]

            has_draft = any([
                self.draft_data.get('ar'),
                self.draft_data.get('ur'),
                self.draft_data.get('guj'),
                self.draft_data.get('en')
            ])

            if has_draft and chapters_data:
                target_chapter = None
                for chapter in chapters_data:
                    if chapter.get("chapter_id") == self.active_chapter_id:
                        target_chapter = chapter
                        break
                if target_chapter is None:
                    target_chapter = chapters_data[-1]
                    
                draft_copy = copy.deepcopy(self.draft_data)
                if self.styles.get("enable_tajweed") and draft_copy.get('ar'):
                    draft_copy['ar'] = TajweedEngine.apply_html(draft_copy['ar'])
                    
                target_chapter['blocks'].append({
                    "block_id": "draft",
                    "content_data": draft_copy,
                    "content_type": "text",
                    "footnotes": self.draft_data.get('footnotes', [])
                })

            html_content = template.render(
                book_title=book_info['title'] if book_info else "Preview",
                author=book_info['author'] if book_info else "",
                book_metadata=book_metadata,
                chapters=chapters_data,
                margins=self.styles.get("margins"),
                page_geometry=page_geometry,
                is_rtl=is_rtl,
                fonts=self.styles.get("fonts"),
                preview_mode=self.preview_mode,
                press_ready=self.styles.get("press_ready", False),
                theme=self.styles.get("theme"),
                enable_3d_flip=self.styles.get("enable_3d_flip", False)
            )
            self.finished.emit(self.request_id, True, html_content)
        except Exception as e:
            self.finished.emit(self.request_id, False, str(e))

class ProjectTreeWidget(QTreeWidget):
    """Custom Tree Widget that handles drag-and-drop rearranging logic."""
    order_changed = pyqtSignal(dict, dict, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event):
        dragged_item = self.currentItem()
        target_item = self.itemAt(event.position().toPoint())
        
        if not dragged_item or not target_item:
            event.ignore()
            return

        drag_data = dragged_item.data(0, Qt.ItemDataRole.UserRole)
        target_data = target_item.data(0, Qt.ItemDataRole.UserRole)
        
        if not drag_data or not target_data:
            event.ignore()
            return

        # Prevent dropping a chapter inside a block
        if drag_data['type'] == 'chapter' and target_data['type'] == 'block':
            event.ignore()
            return

        pos = self.dropIndicatorPosition()
        pos_str = "above" if pos == QAbstractItemView.DropIndicatorPosition.AboveItem else "below"
        
        super().dropEvent(event)
        self.order_changed.emit(drag_data, target_data, pos_str)

class MaktabaDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.db = DatabaseManager(str(self.config.db_path))
        self.current_book_id = None
        self.current_chapter_id = None
        self.selected_block_id = None
        self.all_books = []
        self.preview_request_id = 0
        self.preview_worker = None
        self.preview_pending = False
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(400)
        self.preview_timer.timeout.connect(self._start_live_preview)
        
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30000) # Auto-save every 30 seconds
        self.autosave_timer.timeout.connect(self.process_autosave)
        self.autosave_timer.start()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Maktaba-OS Studio | Pro V5.0 Edition")
        self.setMinimumSize(1400, 900)
        
        self.setStyleSheet(load_stylesheet("app.qss"))

        # --- MAIN UX ARCHITECTURE: THE STACK ---
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # ==========================================
        # PAGE 1: THE LIBRARY HOME SCREEN
        # ==========================================
        self.library_page = QWidget()
        self.library_layout = QVBoxLayout(self.library_page)
        self.library_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.library_layout.setContentsMargins(50, 50, 50, 50)

        lib_title = QLabel("Maktaba Studio")
        lib_title.setStyleSheet("font-size: 36px; font-weight: 800; color: #176B87; margin-bottom: 5px;")
        lib_subtitle = QLabel("Select a project or start a new book to begin authoring.")
        lib_subtitle.setStyleSheet("font-size: 16px; color: #52616B; margin-bottom: 30px;")
        
        self.library_layout.addWidget(lib_title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.library_layout.addWidget(lib_subtitle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Library Controls
        lib_controls = QHBoxLayout()
        self.book_search = QLineEdit()
        self.book_search.setPlaceholderText("Search your library...")
        self.book_search.setMinimumWidth(400)
        self.book_search.setStyleSheet("padding: 12px; font-size: 16px; border-radius: 8px;")
        self.book_search.textChanged.connect(self.apply_book_filter)
        
        self.add_book_btn = QPushButton("📄 Start New Book")
        self.add_book_btn.setObjectName("primaryBtn")
        self.add_book_btn.setStyleSheet("padding: 12px 24px; font-size: 16px; font-weight: bold;")
        self.add_book_btn.clicked.connect(self.show_add_book_dialog)

        self.lib_edit_btn = QPushButton("⚙️ Settings")
        self.lib_edit_btn.setObjectName("secondaryBtn")
        self.lib_edit_btn.setStyleSheet("padding: 12px 20px; font-size: 16px; font-weight: bold;")
        self.lib_edit_btn.setEnabled(False)
        self.lib_edit_btn.clicked.connect(self.show_edit_book_dialog)

        self.lib_delete_btn = QPushButton("🗑️ Delete")
        self.lib_delete_btn.setObjectName("dangerBtn")
        self.lib_delete_btn.setStyleSheet("padding: 12px 20px; font-size: 16px; font-weight: bold;")
        self.lib_delete_btn.setEnabled(False)
        self.lib_delete_btn.clicked.connect(self.delete_book_action)

        lib_controls.addStretch()
        lib_controls.addWidget(self.book_search)
        lib_controls.addWidget(self.add_book_btn)
        lib_controls.addWidget(self.lib_edit_btn)
        lib_controls.addWidget(self.lib_delete_btn)
        lib_controls.addStretch()
        self.library_layout.addLayout(lib_controls)

        self.book_list = QListWidget()
        self.book_list.setMaximumWidth(1000)
        self.book_list.setFlow(QListWidget.Flow.LeftToRight)
        self.book_list.setWrapping(True)
        self.book_list.setSpacing(20)
        self.book_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; outline: none; }
            QListWidget::item { 
                background: #FFFFFF; border-radius: 12px; border: 1px solid #E2E8F0; 
                margin: 5px;
            }
            QListWidget::item:selected { border: 2px solid #176B87; background: #F8FAFC; }
            QListWidget::item:hover { border: 1px solid #94A3B8; }
        """)
        self.book_list.itemDoubleClicked.connect(self.open_selected_book)
        self.book_list.itemSelectionChanged.connect(self.on_library_selection_changed)
        
        list_container = QHBoxLayout()
        list_container.addStretch()
        list_container.addWidget(self.book_list)
        list_container.addStretch()
        self.library_layout.addLayout(list_container)

        self.book_empty_label = QLabel("No books yet. Create a book to start.")
        self.book_empty_label.setStyleSheet("font-size: 16px; color: #888;")
        self.library_layout.addWidget(self.book_empty_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.library_layout.addStretch()

        self.central_stack.addWidget(self.library_page)

        # ==========================================
        # PAGE 2: THE AUTHORING STUDIO
        # ==========================================
        self.studio_page = QWidget()
        self.studio_layout = QVBoxLayout(self.studio_page)
        self.studio_layout.setContentsMargins(14, 12, 14, 14)
        self.studio_layout.setSpacing(10)

        self.studio_splitter = QSplitter(Qt.Orientation.Vertical)
        self.editor_panel = EditorPanel()
        self.editor_panel.save_requested.connect(self.save_content_block)
        self.editor_panel.text_changed_live.connect(self.apply_delta_preview)
        self.editor_panel.karaoke_sync_requested.connect(self.handle_karaoke_space_sync)
        self.build_command_bar()
        
        self.audio_panel = AudioPanel()
        self.audio_panel.audio_time_clicked.connect(self.handle_audio_sync_click)
        self.audio_panel.audio_time_updated.connect(self.handle_audio_playback_sync)
        
        self.audio_panel.hide() # Hide by default to maximize editing space
        self.studio_splitter.addWidget(self.editor_panel)
        self.studio_splitter.addWidget(self.audio_panel)
        self.studio_splitter.setStretchFactor(0, 7)
        self.studio_splitter.setStretchFactor(1, 3)
        self.studio_layout.addWidget(self.studio_splitter)
        self.central_stack.addWidget(self.studio_page)

        self.nav_dock = QDockWidget("Project Explorer", self)
        self.nav_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        
        # Clean Studio Navigation
        self.back_to_lib_btn = QPushButton("🏠 Return to Library")
        self.back_to_lib_btn.setObjectName("secondaryBtn")
        self.back_to_lib_btn.setStyleSheet("text-align: left; padding: 12px; font-size: 14px; border: none; border-bottom: 2px solid #CFD7DE; border-radius: 0px; margin-bottom: 10px;")
        self.back_to_lib_btn.clicked.connect(self.close_book_and_go_home)
        nav_layout.addWidget(self.back_to_lib_btn)

        structure_btn_layout = QHBoxLayout()
        self.add_chap_btn = QPushButton()
        self.add_chap_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.add_chap_btn.setToolTip("New Chapter")
        self.add_chap_btn.clicked.connect(self.show_add_chapter_dialog)
        self.edit_chap_btn = QPushButton("✏️")
        self.edit_chap_btn.setToolTip("Edit Chapter")
        self.edit_chap_btn.clicked.connect(self.show_edit_chapter_dialog)
        self.delete_chap_btn = QPushButton()
        self.delete_chap_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_chap_btn.setToolTip("Delete Chapter")
        self.delete_chap_btn.clicked.connect(self.delete_current_chapter)
        structure_btn_layout.addWidget(self.add_chap_btn)
        structure_btn_layout.addWidget(self.edit_chap_btn)
        structure_btn_layout.addWidget(self.delete_chap_btn)
        nav_layout.addLayout(structure_btn_layout)

        order_btn_layout = QHBoxLayout()
        self.chapter_up_btn = QPushButton()
        self.chapter_up_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.chapter_up_btn.setToolTip("Move Chapter Up")
        self.chapter_up_btn.clicked.connect(lambda: self.move_current_chapter(-1))
        self.chapter_down_btn = QPushButton()
        self.chapter_down_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.chapter_down_btn.setToolTip("Move Chapter Down")
        self.chapter_down_btn.clicked.connect(lambda: self.move_current_chapter(1))
        order_btn_layout.addWidget(self.chapter_up_btn)
        order_btn_layout.addWidget(self.chapter_down_btn)
        nav_layout.addLayout(order_btn_layout)

        block_btn_layout = QHBoxLayout()
        self.block_up_btn = QPushButton()
        self.block_up_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.block_up_btn.setToolTip("Move Block Up")
        self.block_up_btn.clicked.connect(lambda: self.move_selected_block(-1))
        self.block_down_btn = QPushButton()
        self.block_down_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        self.block_down_btn.setToolTip("Move Block Down")
        self.block_down_btn.clicked.connect(lambda: self.move_selected_block(1))
        self.duplicate_block_btn = QPushButton("📋")
        self.duplicate_block_btn.setToolTip("Duplicate Block")
        self.duplicate_block_btn.clicked.connect(self.duplicate_selected_block)
        self.delete_block_btn = QPushButton()
        self.delete_block_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_block_btn.setToolTip("Delete Block")
        self.delete_block_btn.clicked.connect(self.delete_selected_block)
        block_btn_layout.addWidget(self.block_up_btn)
        block_btn_layout.addWidget(self.block_down_btn)
        block_btn_layout.addWidget(self.duplicate_block_btn)
        block_btn_layout.addWidget(self.delete_block_btn)
        nav_layout.addLayout(block_btn_layout)

        self.chapter_tree = ProjectTreeWidget()
        self.chapter_tree.setHeaderLabels(["Book Structure"])
        self.chapter_tree.itemClicked.connect(self.handle_structure_click)
        self.chapter_tree.order_changed.connect(self.handle_tree_drag_drop)
        nav_layout.addWidget(self.chapter_tree)
        self.structure_empty_label = QLabel("No chapters yet. Add a chapter before saving content.")
        nav_layout.addWidget(self.structure_empty_label)

        self.nav_dock.setWidget(nav_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.nav_dock)

        self.preview_dock = QDockWidget("Live Interactive Preview", self)
        self.preview_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        
        preview_toolbar = QHBoxLayout()
        preview_toolbar.setContentsMargins(10, 5, 10, 5)
        preview_toolbar.addWidget(QLabel("Scope:"))
        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItems(["Full Book", "Active Chapter"])
        self.preview_mode_combo.currentTextChanged.connect(self.update_live_preview)
        preview_toolbar.addWidget(self.preview_mode_combo)
        
        self.flip_mode_check = QCheckBox("📖 3D Flip")
        self.flip_mode_check.setToolTip("Enable immersive 3D page flipping.")
        self.flip_mode_check.stateChanged.connect(self.update_live_preview)
        preview_toolbar.addWidget(self.flip_mode_check)
        
        preview_toolbar.addStretch()
        preview_layout.addLayout(preview_toolbar)
        
        if WEB_ENGINE_AVAILABLE:
            self.preview_browser = QWebEngineView()
            self.web_channel = QWebChannel()
            self.web_bridge = WebBridge()
            self.web_bridge.block_clicked.connect(self.load_block_for_editing)
            self.web_bridge.block_edited.connect(self.handle_preview_edit)
            self.web_channel.registerObject("pybridge", self.web_bridge)
            self.preview_browser.page().setWebChannel(self.web_channel)
        else:
            self.preview_browser = QTextBrowser()
            self.preview_browser.setOpenLinks(False)
            self.preview_browser.anchorClicked.connect(self.handle_preview_click)
        
        self.preview_browser.setHtml("<h2 style='color:#888; text-align:center; font-family:sans-serif;'>Select a book to see live preview...</h2>")
        
        preview_layout.addWidget(self.preview_browser)
        self.preview_dock.setWidget(preview_container)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.preview_dock)

        self.prop_dock = QDockWidget("Inspector & Properties", self)
        self.prop_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        prop_widget = QWidget()
        prop_layout = QVBoxLayout(prop_widget)
        
        self.properties_panel = PropertiesPanel()
        self.properties_panel.holy_checkbox.stateChanged.connect(self.editor_panel.toggle_holy_highlighter)
        self.properties_panel.tabs.currentChanged.connect(self.update_live_preview)
        self.properties_panel.properties_changed.connect(self.apply_style_delta_update)
        
        prop_layout.addWidget(self.properties_panel)

        self.visual_inspector = VisualPropertyInspector()
        self.visual_inspector.properties_changed.connect(self.apply_style_delta_update)
        prop_layout.addWidget(self.visual_inspector)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Default Theme", None)
        self.load_available_themes()
        self.theme_combo.currentIndexChanged.connect(self.apply_style_delta_update)
        prop_layout.addWidget(QLabel("<b>Book Theme:</b>"))
        prop_layout.addWidget(self.theme_combo)

        self.press_ready_checkbox = QCheckBox("Preview Press Ready Marks (Bleed & Crop)")
        self.press_ready_checkbox.setToolTip("Simulate crop marks in the Live Preview.")
        self.press_ready_checkbox.setStyleSheet("QCheckBox { margin-top: 10px; }")
        self.press_ready_checkbox.stateChanged.connect(self.update_live_preview)
        prop_layout.addWidget(self.press_ready_checkbox)

        self.publish_btn = QPushButton("🚀 Publish Project")
        self.publish_btn.setObjectName("primaryBtn")
        self.publish_btn.clicked.connect(self.show_export_dialog)
        prop_layout.addWidget(self.publish_btn)

        self.prop_dock.setWidget(prop_widget)
        
        self.assets_dock = QDockWidget("Image & Asset Manager", self)
        self.assets_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.asset_manager = AssetManagerPanel()
        self.assets_dock.setWidget(self.asset_manager)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.assets_dock)
        
        self.tabifyDockWidget(self.preview_dock, self.prop_dock)
        self.tabifyDockWidget(self.prop_dock, self.assets_dock)
        self.preview_dock.raise_()

        self.create_menu_bar()
        self.install_shortcuts()
        self.default_window_state = self.saveState()
        self.load_books()
        self.update_action_states()
        self.statusBar().showMessage("Maktaba Studio Ready.")
        self.show_library_view()
        
    def process_autosave(self):
        """Background autosave worker to protect unsaved work without freezing the UI."""
        if not self.current_book_id or not self.current_chapter_id: return
            
        if hasattr(self, 'editor_panel') and getattr(self.editor_panel, '_is_dirty', False):
            data = self.editor_panel.get_data()
            worker = DbWorker(self.db.save_draft, self.current_book_id, self.current_chapter_id, self.selected_block_id, data)
            worker.start()

    def show_library_view(self):
        """Hides the complex studio and shows only the clean library screen."""
        self.central_stack.setCurrentWidget(self.library_page)
        self.nav_dock.hide()
        self.preview_dock.hide()
        self.prop_dock.hide()
        if hasattr(self, 'command_bar'):
            self.command_bar.hide()
        self.statusBar().showMessage("Maktaba Library")

    def check_unsaved_changes(self) -> bool:
        """Checks if the editor has unsaved changes. Returns True if safe to proceed."""
        if hasattr(self, 'editor_panel') and getattr(self.editor_panel, '_is_dirty', False):
            reply = QMessageBox.warning(
                self,
                "Unsaved Changes",
                "You have unsaved changes in the current block. Do you want to discard them and continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return False
        return True

    def on_library_selection_changed(self):
        has_selection = len(self.book_list.selectedItems()) > 0
        self.lib_edit_btn.setEnabled(has_selection)
        self.lib_delete_btn.setEnabled(has_selection)

    def open_selected_book(self, item):
        """Transitions from the library into the authoring studio."""
        if not self.check_unsaved_changes(): return
        book_id = item.data(Qt.ItemDataRole.UserRole)
        self.open_book_by_id(book_id)

    def open_book_by_id(self, book_id):
        self.current_book_id = book_id
        self.current_chapter_id = None
        self.selected_block_id = None
        
        self.central_stack.setCurrentWidget(self.studio_page)
        self.nav_dock.show()
        self.preview_dock.show()
        self.prop_dock.show()
        self.command_bar.show()
        
        self.refresh_structure()
        self.update_live_preview()
        self.update_action_states()
        self.statusBar().showMessage(f"Opened Book #{book_id} in Studio Mode.")

    def close_book_and_go_home(self):
        """Closes the current project and returns to the library."""
        if not self.check_unsaved_changes(): return
        self.current_book_id = None
        self.current_chapter_id = None
        self.selected_block_id = None
        self.editor_panel.clear_fields()
        self.preview_browser.setHtml("<h2 style='color:#888; text-align:center;'>Select a book to see live preview...</h2>")
        self.show_library_view()

    def build_command_bar(self):
        self.command_bar = QFrame()
        self.command_bar.setObjectName("commandBar")
        layout = QHBoxLayout(self.command_bar)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        self.workspace_title = QLabel("Maktaba Studio")
        self.workspace_title.setObjectName("workspaceTitle")
        self.context_label = QLabel("No book selected")
        self.context_label.setObjectName("contextLabel")
        title_stack.addWidget(self.workspace_title)
        title_stack.addWidget(self.context_label)
        layout.addLayout(title_stack, stretch=2)

        self.command_palette_btn = QPushButton("🔍 Search or Command (Ctrl+K)")
        self.command_palette_btn.setObjectName("commandPaletteBtn")
        self.command_palette_btn.clicked.connect(self.show_command_palette)
        self.command_palette_btn.setStyleSheet("""
            QPushButton#commandPaletteBtn {
                text-align: left;
                padding: 6px 12px;
                color: #A0AEC0;
                background-color: #2D3748;
                border: 1px solid #4A5568;
                border-radius: 4px;
            }
            QPushButton#commandPaletteBtn:hover {
                background-color: #4A5568;
                color: #FFFFFF;
            }
        """)
        layout.addWidget(self.command_palette_btn, stretch=3)

        self.quick_chapter_btn = QPushButton("New Chapter")
        self.quick_chapter_btn.clicked.connect(self.show_add_chapter_dialog)
        self.quick_save_btn = QPushButton("Save Block")
        self.quick_save_btn.setObjectName("primaryBtn")
        self.quick_save_btn.clicked.connect(self.editor_panel.on_save_clicked)
        
        self.smart_paste_btn = QPushButton("⚡ Smart Paste Document")
        self.smart_paste_btn.setObjectName("secondaryBtn")
        self.smart_paste_btn.clicked.connect(self.show_bulk_import_dialog)
        
        self.find_replace_btn = QPushButton("🔍 Find & Replace")
        self.find_replace_btn.clicked.connect(self.show_find_replace_dialog)
        
        self.template_builder_btn = QPushButton("🎨 Theme Builder")
        self.template_builder_btn.clicked.connect(self.show_template_builder_dialog)
        
        layout.addWidget(self.quick_chapter_btn)
        layout.addWidget(self.smart_paste_btn)
        layout.addWidget(self.find_replace_btn)
        layout.addWidget(self.template_builder_btn)
        layout.addWidget(self.quick_save_btn)

        self.activity_label = QLabel("Ready")
        self.activity_label.setObjectName("activityPill")
        layout.addWidget(self.activity_label)
        self.studio_layout.insertWidget(0, self.command_bar)

    def install_shortcuts(self):
        shortcuts = [
            ("Ctrl+N", self.show_add_book_dialog),
            ("Ctrl+Shift+N", self.show_add_chapter_dialog),
            ("Ctrl+S", self.editor_panel.on_save_clicked),
            ("Ctrl+F", self.book_search.setFocus),
            ("Ctrl+K", self.show_command_palette),
            ("Ctrl+P", self.show_export_dialog),
            ("Ctrl+I", self.show_bulk_import_dialog),
            ("Ctrl+H", self.show_find_replace_dialog),
            ("Esc", self.editor_panel.clear_fields),
        ]
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)

    def show_command_palette(self):
        palette = CommandPalette(self)
        palette.command_executed.connect(self.execute_palette_command)
        
        # Center the palette
        palette.adjustSize()
        geo = palette.geometry()
        geo.moveCenter(self.geometry().center())
        palette.setGeometry(geo)
        
        palette.exec()

    def execute_palette_command(self, command):
        if command == "book":
            self.show_add_book_dialog()
        elif command == "chapter":
            self.show_add_chapter_dialog()
        elif command == "save":
            self.editor_panel.on_save_clicked()
        elif command == "restore_block":
            self.restore_selected_block()
        elif command == "publish":
            self.show_export_dialog()
        elif command == "import":
            self.show_bulk_import_dialog()
        elif command == "replace":
            self.show_find_replace_dialog()
        elif command == "search":
            self.book_search.setFocus()
        elif command == "library":
            self.close_book_and_go_home()
        elif command == "audio":
            is_visible = self.audio_panel.isVisible()
            self.audio_panel.setVisible(not is_visible)
            if not is_visible:
                self.audio_panel.setFocus()
        elif command == "focus":
            current_state = self.editor_panel.focus_mode_btn.isChecked()
            self.editor_panel.focus_mode_btn.setChecked(not current_state)
            self.editor_panel.toggle_focus_mode(not current_state)
        elif command == "highlighter":
            self.properties_panel.holy_checkbox.setChecked(not self.properties_panel.holy_checkbox.isChecked())
        else:
            self.book_search.setText(command)
            self.book_search.setFocus()

    def handle_audio_sync_click(self, time_sec):
        """Sends clicked audio timeline seconds to Editor Panel to auto-fill Karaoke mapping."""
        success = self.editor_panel.capture_audio_timestamp(time_sec)
        if success:
            self.statusBar().showMessage(f"🎤 Karaoke Sync: Timestamp {time_sec:.2f}s mapped to word!", 3000)
        else:
            self.statusBar().showMessage(f"Audio Timeline Scrubbed to {time_sec:.2f}s. (Open Word-by-Word Sync tab to map)", 3000)

    def handle_karaoke_space_sync(self):
        current_time = getattr(self.audio_panel, 'current_audio_time', 0.0)
        self.editor_panel.capture_audio_timestamp(current_time)
        self.statusBar().showMessage(f"🎤 Karaoke Continuous Sync: {current_time:.2f}s mapped via Spacebar!", 2000)

    def handle_audio_playback_sync(self, time_sec):
        """Continuously syncs the 3D book Live Preview Karaoke highlight with the playing audio."""
        if WEB_ENGINE_AVAILABLE and hasattr(self, 'preview_browser') and isinstance(self.preview_browser, QWebEngineView):
            self.preview_browser.page().runJavaScript(f"window.syncKaraoke({time_sec});")

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        view_menu = menu_bar.addMenu("View")
        view_menu.addAction(self.nav_dock.toggleViewAction())
        view_menu.addAction(self.preview_dock.toggleViewAction())
        view_menu.addAction(self.prop_dock.toggleViewAction())
        view_menu.addSeparator()
        restore_action = QAction("🔄 Restore Default Layout", self)
        restore_action.triggered.connect(self.restore_default_layout)
        view_menu.addAction(restore_action)

    def restore_default_layout(self):
        self.restoreState(self.default_window_state)
        self.nav_dock.show(); self.preview_dock.show(); self.prop_dock.show()

    def handle_preview_click(self, url: QUrl):
        url_str = url.toString()
        if url_str.startswith("block:"):
            block_id_str = url_str.split(":")[1]
            if block_id_str.isdigit():
                self.load_block_for_editing(int(block_id_str))

    def load_block_for_editing(self, block_id):
        if not self.current_book_id: return
        content = self.db.get_book_content(self.current_book_id)
        for block in content:
            if block['block_id'] == block_id:
                self.current_chapter_id = block['chapter_id']
                self.selected_block_id = block_id
                raw_data = block['content_data']
                data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                data_dict["footnotes"] = block.get("footnotes", [])
                
                # --- AUTO-SAVE RECOVERY CHECK ---
                draft = self.db.get_draft(self.current_book_id, self.current_chapter_id, self.selected_block_id)
                if draft:
                    reply = QMessageBox.question(
                        self, "Recover Draft?",
                        "An unsaved draft from a previous session exists for this block. Would you like to recover it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        data_dict = draft
                    else:
                        self.db.clear_draft(self.current_book_id, self.current_chapter_id, self.selected_block_id)
                        
                self.editor_panel.load_data_for_editing(block_id, data_dict)
                self.statusBar().showMessage(f"Loaded Block #{block_id} for editing.", 3000)
                break

    def handle_preview_edit(self, block_id, lang, new_text):
        """Saves text edited directly inside the HTML preview back to the DB."""
        if not self.current_book_id: return
        try:
            with self.db._get_connection() as conn:
                row = conn.execute("SELECT content_data FROM Content_Blocks WHERE id = ?", (block_id,)).fetchone()
                if row:
                    data = json.loads(row['content_data'])
                    if data.get(lang, "") != new_text:
                        data[lang] = new_text
                        self.db.update_content_block(block_id, data)
                        
                        # Live sync the left editor panel if the user has that specific block open
                        if self.selected_block_id == block_id:
                            self.editor_panel.blockSignals(True)
                            if lang in self.editor_panel.editors:
                                self.editor_panel.editors[lang].setPlainText(new_text)
                            self.editor_panel.blockSignals(False)
                        self.statusBar().showMessage(f"Live Edit Saved: Block #{block_id} ({lang.upper()})", 2000)
        except Exception as e:
            print(f"Live WYSIWYG edit failed: {e}")

    def apply_delta_preview(self):
        """Applies delta DOM updates to the 3D preview without rebuilding Jinja HTML. Solves CPU lag."""
        if not self.current_book_id: return
        
        if not WEB_ENGINE_AVAILABLE or not isinstance(self.preview_browser, QWebEngineView):
            self.update_live_preview()
            return

        block_id = self.editor_panel.current_editing_block_id or 'draft'
        data = self.editor_panel.get_data()

        if data.get('words'):
            # Karaoke Word-by-Word grids require full structural rebuilds
            self.update_live_preview()
            return

        js_func = """
        (function() {
            var blockId = '%s';
            var data = %s;
            
            var blockDiv = document.getElementById('block-' + blockId);
            if (!blockDiv) {
                return false; // Draft container doesn't exist yet, need full Jinja render
            }

            for (var lang in data) {
                if (['ar', 'ur', 'guj', 'en'].includes(lang)) {
                    var el = document.getElementById('text-' + blockId + '-' + lang);
                    var textContent = (typeof data[lang] === 'string') ? data[lang].trim() : "";
                    if (el) {
                        if (el.innerHTML !== textContent) {
                            el.innerHTML = textContent;
                        }
                    } else if (textContent !== '') {
                        // Element doesn't exist but has text now, needs full render to create the DOM node
                        return false;
                    }
                }
            }
            return true; // Delta applied perfectly!
        })();
        """ % (block_id, json.dumps(data))

        def callback(success):
            if not success:
                self.update_live_preview()

        self.preview_browser.page().runJavaScript(js_func, callback)

    def apply_style_delta_update(self):
        """Applies style property changes to the live preview via CSS variables without a full page reload."""
        if not WEB_ENGINE_AVAILABLE or not hasattr(self, 'preview_browser') or not isinstance(self.preview_browser, QWebEngineView):
            self.update_live_preview() # Fallback for non-webengine or if something is wrong
            return

        styles = self.properties_panel.get_styles()
        js_parts = []
        
        theme = self.theme_combo.currentData()
        if theme:
            if theme.get('primary_color'): js_parts.append(f"document.documentElement.style.setProperty('--primary-color', '{theme['primary_color']}');")
            if theme.get('bg_color'): js_parts.append(f"document.documentElement.style.setProperty('--bg-color', '{theme['bg_color']}');")
            if theme.get('text_color'): js_parts.append(f"document.documentElement.style.setProperty('--text-color', '{theme['text_color']}');")

        # Margins
        margins = styles.get('margins', {})
        for key, value in margins.items():
            js_parts.append(f"document.documentElement.style.setProperty('--margin-{key}', '{value}mm');")

        # Fonts
        fonts = styles.get('fonts', {})
        font_map = {
            'arabic': 'arabic', 'urdu': 'urdu', 'gujarati': 'gujarati', 'english': 'english'
        }
        prop_map = {
            'size': 'font-size', 'leading': 'line-height', 'kerning': 'letter-spacing', 'align': 'text-align'
        }

        for lang_key, lang_css in font_map.items():
            for prop_key, prop_css in prop_map.items():
                # e.g., fonts['arabic_size']
                full_key = f"{lang_key}_{prop_key}"
                if full_key in fonts:
                    value = fonts[full_key]
                    unit = 'pt' if prop_key in ['size', 'kerning'] else ''
                    css_var = f"--{lang_css}-{prop_css}"
                    js_parts.append(f"document.documentElement.style.setProperty('{css_var}', '{value}{unit}');")
            
            if lang_key in fonts:
                font_family = fonts[lang_key]
                if theme and lang_key == 'arabic' and theme.get('arabic_font'):
                    font_family = theme['arabic_font']
                elif theme and lang_key == 'english' and theme.get('english_font'):
                    font_family = theme['english_font']
                css_var = f"--{lang_css}-font-family"
                fallback = "'sans-serif'" if lang_key == 'gujarati' else "'serif'"
                js_parts.append(f"document.documentElement.style.setProperty('{css_var}', `'{font_family}', {fallback}`);")

        if hasattr(self, 'visual_inspector'):
            vals = self.visual_inspector.get_values()
            if vals['drop_cap'] > 0:
                js_parts.append(f"document.documentElement.style.setProperty('--drop-cap-size', '{vals['drop_cap']}pt');")
                js_parts.append(f"document.documentElement.style.setProperty('--drop-cap-float', 'left');")
                js_parts.append(f"document.documentElement.style.setProperty('--drop-cap-padding', '8px');")
            else:
                js_parts.append(f"document.documentElement.style.setProperty('--drop-cap-size', 'inherit');")
                js_parts.append(f"document.documentElement.style.setProperty('--drop-cap-float', 'none');")
                js_parts.append(f"document.documentElement.style.setProperty('--drop-cap-padding', '0px');")
                
            js_parts.append(f"document.documentElement.style.setProperty('--english-line-height', '{vals['leading']}');")
            js_parts.append(f"document.documentElement.style.setProperty('--english-letter-spacing', '{vals['kerning']}pt');")

        self.preview_browser.page().runJavaScript(" ".join(js_parts))

    def update_live_preview(self, *args):
        if not self.current_book_id: return
        self.preview_timer.start()

    def _start_live_preview(self):
        if not self.current_book_id:
            return

        if self.preview_worker and self.preview_worker.isRunning():
            self.preview_pending = True
            self.preview_request_id += 1
            return

        self.preview_request_id += 1
        request_id = self.preview_request_id
        draft_data = self.editor_panel.get_data()
        styles = self.properties_panel.get_styles()
        styles['press_ready'] = self.press_ready_checkbox.isChecked()
        styles['theme'] = self.theme_combo.currentData()
        styles['enable_3d_flip'] = self.flip_mode_check.isChecked() if hasattr(self, 'flip_mode_check') else False
        mode = self.preview_mode_combo.currentText() if hasattr(self, 'preview_mode_combo') else "Full Book"
        self.preview_worker = PreviewWorker(
            request_id=request_id,
            book_id=self.current_book_id,
            db_path=str(self.config.db_path),
            template_dir=str(self.config.template_dir),
            draft_data=draft_data,
            styles=styles,
            active_chapter_id=self.current_chapter_id,
            preview_mode=mode
        )
        self.preview_worker.finished.connect(self._handle_preview_finished)
        self.preview_worker.start()

    def _handle_preview_finished(self, request_id, success, message):
        if request_id == self.preview_request_id:
            if success:
                if WEB_ENGINE_AVAILABLE:
                    # Inject bridge script dynamically and pass base URL for assets
                    bridge_script = """
                    <script src='qrc:///qtwebchannel/qwebchannel.js'></script>
                    <script>
                        new QWebChannel(qt.webChannelTransport, function(channel){ window.pybridge = channel.objects.pybridge; });
                    </script>
                    """
                    self.preview_browser.setHtml(bridge_script + message, QUrl.fromLocalFile(str(self.config.template_dir) + "/"))
                else:
                    self.preview_browser.setHtml(message)
            else:
                print(f"Live Preview Error: {message}")

        if self.preview_pending:
            self.preview_pending = False
            self.preview_timer.start()

    def load_books(self):
        self.book_list.setEnabled(False)
        self.statusBar().showMessage("Loading library...")
        self._load_books_worker = DbWorker(self.db.list_books)
        self._load_books_worker.finished.connect(self._on_books_loaded)
        self._load_books_worker.error.connect(lambda e: self.statusBar().showMessage(f"Failed to load books: {e}"))
        self._load_books_worker.start()

    def _on_books_loaded(self, books):
        self.all_books = books
        self.book_list.setEnabled(True)
        self.apply_book_filter()
        self.statusBar().clearMessage()

    def apply_book_filter(self):
        search_term = self.book_search.text().strip().lower() if hasattr(self, "book_search") else ""
        previous_book_id = self.current_book_id
        filtered_books = []
        for row in self.all_books:
            haystack = " ".join([
                str(row.get("title") or ""),
                str(row.get("author") or ""),
                str(row.get("language") or ""),
            ]).lower()
            if not search_term or search_term in haystack:
                filtered_books.append(row)

        self.book_list.blockSignals(True)
        self.book_list.clear()
        selected_row_index = None
        for index, row in enumerate(filtered_books):
            cover_path = ""
            metadata = row.get("metadata")
            if metadata:
                try:
                    meta_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                    cover_path = meta_dict.get("cover_image", "")
                except: pass
                
            item = QListWidgetItem()
            # Professional Book Card Dimensions
            item.setSizeHint(QSize(180, 280))
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.book_list.addItem(item)
            
            card = BookCard(
                title=row.get("title") or "Untitled",
                author=row.get("author") or "Unknown",
                lang=row.get("language") or "en",
                cover_path=cover_path
            )
            self.book_list.setItemWidget(item, card)
            
            if row["id"] == previous_book_id:
                selected_row_index = index

        self.book_list.blockSignals(False)
        if self.all_books and not filtered_books:
            self.book_empty_label.setText("No books match the current search.")
        else:
            self.book_empty_label.setText("No books yet. Create a book to start.")
        self.book_empty_label.setVisible(len(filtered_books) == 0)

    def show_add_book_dialog(self):
        dialog = BookDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            new_book_id = self.db.add_book(
                data['title'], data['author'], data['language'],
                publisher=data['publisher'], category=data['category'], notes=data['notes'], metadata=data['metadata']
            )
            
            # UX Fix: Auto-create 'Chapter 1' so the user doesn't face a blank canvas
            self.db.add_chapter(new_book_id, "Chapter 1", 1, "Content Chapter")
            
            self.load_books()
            
            # Auto-open the newly created book in the studio
            self.open_book_by_id(new_book_id)

    def show_edit_book_dialog(self):
        target_id = self.current_book_id
        if self.central_stack.currentWidget() == self.library_page:
            selected = self.book_list.selectedItems()
            if selected: target_id = selected[0].data(Qt.ItemDataRole.UserRole)
            
        if not target_id:
            return QMessageBox.warning(self, "Error", "Select a book first.")
            
        book = self.db.get_book(target_id)
        if not book:
            return QMessageBox.warning(self, "Error", "Selected book was not found.")
            
        dialog = BookDialog(self, book)
        if dialog.exec():
            data = dialog.get_data()
            self.db.update_book(
                target_id, data['title'], data['author'], data['language'],
                publisher=data['publisher'], category=data['category'], notes=data['notes'], metadata=data['metadata']
            )
            self.load_books()
            self.update_context_summary()

    def delete_book_action(self):
        target_id = self.current_book_id
        if self.central_stack.currentWidget() == self.library_page:
            selected = self.book_list.selectedItems()
            if selected: target_id = selected[0].data(Qt.ItemDataRole.UserRole)
            
        if not target_id:
            return QMessageBox.warning(self, "Error", "Select a book first.")
        reply = QMessageBox.question(
            self,
            "Delete Book",
            "Delete this book and all chapters/blocks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_book(target_id)
        self.load_books()
        if self.current_book_id == target_id:
            self.close_book_and_go_home()

    def show_add_chapter_dialog(self):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Open a book first.")
        dialog = ChapterDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            # Passing chapter TYPE to database now
            self.current_chapter_id = self.db.add_chapter(self.current_book_id, data['title'], data['sequence'], data['type'])
            self.refresh_structure()
            self.update_action_states()

    def show_edit_chapter_dialog(self):
        if not self.current_chapter_id:
            return QMessageBox.warning(self, "Error", "Select a chapter first.")
        chapter = self.db.get_chapter(self.current_chapter_id)
        if not chapter:
            return QMessageBox.warning(self, "Error", "Selected chapter was not found.")
        dialog = ChapterDialog(self, chapter)
        if dialog.exec():
            data = dialog.get_data()
            self.db.update_chapter(self.current_chapter_id, data['title'], data['sequence'], data['type'])
            self.refresh_structure()
            self.update_action_states()

    def delete_current_chapter(self):
        if not self.current_chapter_id:
            return QMessageBox.warning(self, "Error", "Select a chapter first.")
        reply = QMessageBox.question(
            self,
            "Delete Chapter",
            "Delete this chapter and all its content blocks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.nav_dock.setEnabled(False)
        self.statusBar().showMessage("Deleting chapter...", 0)
        self._del_chap_worker = DbWorker(self.db.delete_chapter, self.current_chapter_id)
        self._del_chap_worker.finished.connect(self._on_delete_chapter_finished)
        self._del_chap_worker.start()

    def _on_delete_chapter_finished(self, _):
        self.nav_dock.setEnabled(True)
        self.current_chapter_id = None
        self.selected_block_id = None
        self.refresh_structure()
        self.update_action_states()
        self.statusBar().showMessage("Chapter deleted.", 3000)

    def move_current_chapter(self, direction):
        if not self.current_chapter_id:
            return QMessageBox.warning(self, "Error", "Select a chapter first.")
            
        self.nav_dock.setEnabled(False)
        self._move_chap_worker = DbWorker(self.db.move_chapter, self.current_chapter_id, direction)
        self._move_chap_worker.finished.connect(self._on_move_chapter_finished)
        self._move_chap_worker.start()

    def _on_move_chapter_finished(self, _):
        self.nav_dock.setEnabled(True)
        self.refresh_structure()
        self.update_action_states()

    def handle_tree_drag_drop(self, drag_data, target_data, pos_str):
        self.statusBar().showMessage("Reordering structure...", 2000)
        self.chapter_tree.setEnabled(False)
        
        self._reorder_worker = DbWorker(self._execute_reorder, drag_data, target_data, pos_str)
        self._reorder_worker.finished.connect(self._on_reorder_finished)
        self._reorder_worker.error.connect(self._on_reorder_error)
        self._reorder_worker.start()

    def _execute_reorder(self, drag_data, target_data, pos_str):
        drag_type = drag_data.get('type')
        target_type = target_data.get('type')
        if drag_type == 'chapter' and target_type == 'chapter':
            self.db.reorder_chapter(drag_data['id'], target_data['id'], pos_str)
        elif drag_type == 'block' and target_type == 'block':
            self.db.reorder_block(drag_data['id'], target_data['id'], pos_str)
        elif drag_type == 'block' and target_type == 'chapter':
            self.db.reorder_block_to_chapter(drag_data['id'], target_data['id'])
        return True

    def _on_reorder_finished(self, result):
        self.chapter_tree.setEnabled(True)
        self.refresh_structure()
        self.update_live_preview()
        self.statusBar().showMessage("Reordering successful.", 3000)

    def _on_reorder_error(self, err_msg):
        self.chapter_tree.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to reorder: {err_msg}")
        self.refresh_structure()

    def _fetch_structure_data(self, book_id):
        """Runs on the background thread to fetch heavy tree data."""
        if not book_id: return [], []
        content = self.db.get_book_content(book_id)
        chapter_rows = self.db.list_chapters(book_id)
        return content, chapter_rows

    def refresh_structure(self):
        if not self.current_book_id:
            self.chapter_tree.clear()
            self.structure_empty_label.setVisible(True)
            return

        self.chapter_tree.setEnabled(False)
        self.structure_empty_label.setText("Loading structure...")
        self.structure_empty_label.setVisible(True)
        
        self._load_structure_worker = DbWorker(self._fetch_structure_data, self.current_book_id)
        self._load_structure_worker.finished.connect(self._on_structure_loaded)
        self._load_structure_worker.error.connect(lambda e: self.statusBar().showMessage(f"Failed to load structure: {e}"))
        self._load_structure_worker.start()

    def _on_structure_loaded(self, result):
        content, chapter_rows = result
        self.chapter_tree.clear()
        self.chapter_tree.setEnabled(True)

        known_chapter_ids = {chapter["id"] for chapter in chapter_rows}
        if self.current_chapter_id not in known_chapter_ids:
            self.current_chapter_id = None
        if not self.current_chapter_id and chapter_rows:
            self.current_chapter_id = chapter_rows[0]["id"]

        chapters = {}
        chapter_block_counts = {}
        known_block_ids = {block["block_id"] for block in content if block["block_id"]}
        if self.selected_block_id not in known_block_ids:
            self.selected_block_id = None

        for chapter in chapter_rows:
            chapter_block_counts[chapter["id"]] = chapter["active_block_count"]

        for block in content:
            chapter_id = block['chapter_id']
            chap_title = block['chapter_title']
            chap_type = block.get('chapter_type', 'Chapter')
            if chapter_id not in chapters:
                # Tree now shows if it's a Cover or Chapter
                count = chapter_block_counts.get(chapter_id, 0)
                prefix = "* " if chapter_id == self.current_chapter_id else ""
                chap_item = QTreeWidgetItem(self.chapter_tree, [f"{prefix}{chap_title} [{chap_type}] ({count} blocks)"])
                chap_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "chapter", "id": chapter_id})
                chap_item.setExpanded(True)
                chapters[chapter_id] = chap_item
            
            if block['block_id']:
                block_data = json.loads(block['content_data'])
                preview_text = block_data.get('ar', block_data.get('en', 'Empty Block'))[:30] + "..."
                block_item = QTreeWidgetItem(chapters[chapter_id], [preview_text])
                block_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "block",
                    "id": block["block_id"],
                    "chapter_id": chapter_id
                })
                if block["block_id"] == self.selected_block_id:
                    self.chapter_tree.setCurrentItem(block_item)

        if self.current_chapter_id and not self.selected_block_id:
            item = chapters.get(self.current_chapter_id)
            if item:
                self.chapter_tree.setCurrentItem(item)
        
        if not chapter_rows:
            self.structure_empty_label.setText("No chapters found.\nClick 'New Chapter' above to begin.")
        self.structure_empty_label.setVisible(len(chapter_rows) == 0)
        self.update_action_states()

    def handle_structure_click(self, item, column):
        if not self.check_unsaved_changes(): return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not payload:
            return
        if payload.get("type") == "chapter":
            self.current_chapter_id = payload["id"]
            self.selected_block_id = None
            self.statusBar().showMessage(f"Active chapter set to #{self.current_chapter_id}.", 3000)
            self.refresh_structure()
            self.update_live_preview()
        elif payload.get("type") == "block":
            self.current_chapter_id = payload["chapter_id"]
            self.selected_block_id = payload["id"]
            self.load_block_for_editing(self.selected_block_id)
            self.statusBar().showMessage(f"Selected block #{self.selected_block_id}.", 3000)
            self.update_live_preview()
        self.update_action_states()

    def save_content_block(self, data):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Select a book.")
        update_id = data.pop('update_block_id', None)
        footnotes = data.pop('footnotes', [])
        
        self.editor_panel.setEnabled(False)
        self.statusBar().showMessage("Saving to database...")
        
        self._save_worker = DbWorker(self._execute_save, update_id, self.current_chapter_id, data, footnotes, self.current_book_id)
        self._save_worker.finished.connect(self._on_save_finished)
        self._save_worker.error.connect(self._on_save_error)
        self._save_worker.start()

    def _execute_save(self, update_id, chapter_id, data, footnotes, book_id):
        if update_id:
            self.db.update_content_block(update_id, data)
            block_id = update_id
            action = "update"
        else:
            if not chapter_id: raise ValueError("Select a target chapter first.")
            block_id = self.db.add_content_block(chapter_id, data)
            action = "insert"
        self.db.sync_footnotes(block_id, footnotes)
        self.db.clear_draft(book_id, chapter_id, update_id) # Clear draft upon successful save
        return {"action": action, "id": block_id, "chapter_id": chapter_id}

    def _on_save_finished(self, result):
        self.statusBar().showMessage(f"Block #{result['id']} {'Updated' if result['action'] == 'update' else 'Saved'}!", 3000)
        if result["action"] == "insert": self.selected_block_id = result["id"]
        self.refresh_structure() 
        self.editor_panel.setEnabled(True)

    def _on_save_error(self, err_msg):
        self.editor_panel.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Failed to save: {err_msg}")

    def delete_selected_block(self):
        if not self.selected_block_id:
            return QMessageBox.warning(self, "Error", "Select a block first.")
        reply = QMessageBox.question(
            self,
            "Delete Block",
            "Delete this content block?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        self.nav_dock.setEnabled(False)
        self._del_block_worker = DbWorker(self.db.soft_delete_content_block, self.selected_block_id)
        self._del_block_worker.finished.connect(self._on_delete_block_finished)
        self._del_block_worker.start()

    def _on_delete_block_finished(self, _):
        self.nav_dock.setEnabled(True)
        self.selected_block_id = None
        self.editor_panel.clear_fields()
        self.refresh_structure()
        self.update_live_preview()

    def duplicate_selected_block(self):
        if not self.selected_block_id:
            return QMessageBox.warning(self, "Error", "Select a block first.")
        new_id = self.db.duplicate_content_block(self.selected_block_id)
        if new_id:
            self.selected_block_id = new_id
            self.statusBar().showMessage(f"Duplicated block as #{new_id}.", 3000)
        self.refresh_structure()
        self.update_live_preview()

    def move_selected_block(self, direction):
        if not self.selected_block_id:
            return QMessageBox.warning(self, "Error", "Select a block first.")
            
        self.nav_dock.setEnabled(False)
        self._move_block_worker = DbWorker(self.db.move_content_block, self.selected_block_id, direction)
        self._move_block_worker.finished.connect(self._on_move_block_finished)
        self._move_block_worker.start()

    def _on_move_block_finished(self, _):
        self.nav_dock.setEnabled(True)
        self.refresh_structure()
        self.update_live_preview()

    def restore_selected_block(self):
        if not self.selected_block_id:
            return QMessageBox.warning(self, "Error", "Select a block from the Project Explorer first.")
            
        reply = QMessageBox.question(
            self, "Restore Block", 
            "Are you sure you want to undo and restore the previous version of this block?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes: 
            return
            
        if self.db.restore_previous_block_version(self.selected_block_id):
            self.statusBar().showMessage(f"Block #{self.selected_block_id} restored to previous version.", 3000)
            self.load_block_for_editing(self.selected_block_id)
            self.refresh_structure()
            self.update_live_preview()
        else:
            QMessageBox.information(self, "No History", "No previous versions found for this block.")

    def update_context_summary(self):
        if not hasattr(self, "context_label"):
            return
        if not self.current_book_id:
            self.context_label.setText("No book selected")
            if hasattr(self, "activity_label"):
                self.activity_label.setText("Ready")
            return

        book = self.db.get_book(self.current_book_id)
        book_title = book["title"] if book else f"Book #{self.current_book_id}"
        parts = [book_title]
        if self.current_chapter_id:
            chapter = self.db.get_chapter(self.current_chapter_id)
            chapter_title = chapter["title"] if chapter else f"Chapter #{self.current_chapter_id}"
            parts.append(chapter_title)
        if self.selected_block_id:
            parts.append(f"Block #{self.selected_block_id}")
        self.context_label.setText(" / ".join(parts))
        if hasattr(self, "activity_label"):
            self.activity_label.setText("Editing" if self.selected_block_id else "Ready")

    def update_action_states(self):
        has_book = self.current_book_id is not None
        has_chapter = self.current_chapter_id is not None
        has_block = self.selected_block_id is not None

        self.add_chap_btn.setEnabled(has_book)
        self.edit_chap_btn.setEnabled(has_chapter)
        self.delete_chap_btn.setEnabled(has_chapter)
        self.chapter_up_btn.setEnabled(has_chapter)
        self.chapter_down_btn.setEnabled(has_chapter)
        self.publish_btn.setEnabled(has_book)
        self.block_up_btn.setEnabled(has_block)
        self.block_down_btn.setEnabled(has_block)
        self.duplicate_block_btn.setEnabled(has_block)
        self.delete_block_btn.setEnabled(has_block)
        if hasattr(self, "quick_chapter_btn"):
            self.quick_chapter_btn.setEnabled(has_book)
        if hasattr(self, "quick_save_btn"):
            self.quick_save_btn.setEnabled(has_book and has_chapter)
        if hasattr(self, "smart_paste_btn"):
            self.smart_paste_btn.setEnabled(has_book and has_chapter)
        if hasattr(self, "find_replace_btn"):
            self.find_replace_btn.setEnabled(has_book)
        self.update_context_summary()
        
        # UX Fix: Disable the editor completely if no chapter is selected to prevent confusion
        if hasattr(self, "editor_panel"):
            self.editor_panel.setEnabled(has_chapter)

    def show_template_builder_dialog(self):
        dialog = TemplateBuilderDialog(self)
        if dialog.exec():
            theme = dialog.get_theme_data()
            
            # Save to assets/themes/ folder
            app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            themes_dir = os.path.join(app_dir, "assets", "themes")
            os.makedirs(themes_dir, exist_ok=True)
            
            file_name = f"{theme['name'].replace(' ', '_').lower()}.json"
            with open(os.path.join(themes_dir, file_name), 'w', encoding='utf-8') as f:
                json.dump(theme, f, indent=4)
                
            self.theme_combo.addItem(theme['name'], theme)
            self.theme_combo.setCurrentIndex(self.theme_combo.count() - 1)
            QMessageBox.information(self, "Theme Exported", f"Theme '{theme['name']}' saved successfully to:\n{themes_dir}/{file_name}")

    def load_available_themes(self):
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        themes_dir = os.path.join(app_dir, "assets", "themes")
        if not os.path.exists(themes_dir): return
        for file in glob.glob(os.path.join(themes_dir, "*.json")):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    theme = json.load(f)
                    self.theme_combo.addItem(theme.get('name', os.path.basename(file)), theme)
            except Exception:
                pass

    def load_importer_plugins(self):
        """Dynamically loads custom parser scripts from the plugins directory."""
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        plugins_dir = os.path.join(app_dir, "plugins", "importers")
        os.makedirs(plugins_dir, exist_ok=True)
        
        plugins = {}
        for file in glob.glob(os.path.join(plugins_dir, "*.py")):
            name = os.path.basename(file)[:-3]
            spec = importlib.util.spec_from_file_location(name, file)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                if hasattr(mod, "parse_import"):
                    plugins[name] = mod
            except Exception as e:
                print(f"Failed to load plugin {name}: {e}")
        return plugins

    def show_bulk_import_dialog(self):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Select a book.")
        if not self.current_chapter_id: return QMessageBox.warning(self, "Error", "Select a chapter from the Project Explorer first to paste into.")
        
        plugins = self.load_importer_plugins()
        dialog = BulkImportDialog(self, plugins)
        if dialog.exec():
            data = dialog.get_data()
            self.statusBar().showMessage("Parsing and importing massive document... Please wait.")
            self.studio_splitter.setEnabled(False) # Lock UI to prevent interference
            
            self._import_worker = DbWorker(self._execute_bulk_import, self.current_chapter_id, data)
            self._import_worker.finished.connect(self._on_bulk_import_finished)
            self._import_worker.error.connect(self._on_bulk_import_error)
            self._import_worker.start()

    def _execute_bulk_import(self, chapter_id, data):
        plugin = data.get('format')
        if plugin and hasattr(plugin, 'parse_import'):
            blocks = plugin.parse_import(data['text'], data['metadata'])
            imported = 0
            for b in blocks:
                self.db.add_content_block(chapter_id, b)
                imported += 1
            return imported
            
        separator_pattern = data['separator'].replace('\\n', '\n')
        blocks = re.split(r'\n\s*\n', data['text'].strip()) if separator_pattern == '\n\n' else data['text'].strip().split(separator_pattern)
        
        imported = 0
        for block in blocks:
            lines = block.strip().split("\n")
            if not lines: continue
            
            block_data = {"ar": "", "ur": "", "guj": "", "en": "", "reference": "", "metadata": data['metadata']}
            for line in lines:
                line = line.strip()
                if not line: continue
                if re.search(r'[\u0a80-\u0aff]', line): block_data["guj"] = line
                elif re.search(r'^[a-zA-Z0-9\s.,!?\'"-]+$', line): block_data["en"] = line
                elif re.search(r'[\u0600-\u06ff]', line):
                    if not block_data["ar"]: block_data["ar"] = line
                    else: block_data["ur"] = line
                else:
                    if not block_data["ar"]: block_data["ar"] = line
            
            if any([block_data["ar"], block_data["ur"], block_data["guj"], block_data["en"]]):
                self.db.add_content_block(chapter_id, block_data)
                imported += 1
        return imported

    def _on_bulk_import_finished(self, imported):
        self.studio_splitter.setEnabled(True)
        self.refresh_structure()
        self.update_live_preview()
        QMessageBox.information(self, "Imported", f"{imported} blocks successfully extracted and added.")
        self.statusBar().showMessage(f"Bulk import complete: {imported} blocks added.", 5000)

    def _on_bulk_import_error(self, err_msg):
        self.studio_splitter.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Bulk import failed: {err_msg}")

    def show_find_replace_dialog(self):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Open a book first.")
        
        dialog = SearchReplaceDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if not data.get("search"): return
            
            self.statusBar().showMessage(f"Replacing '{data['search']}' across the book... Please wait.", 0)
            self.central_stack.setEnabled(False) # Lock UI during global operation
            
            self._replace_worker = DbWorker(self.db.global_replace, data["search"], data["replace"], data.get("language"), self.current_book_id)
            self._replace_worker.finished.connect(self._on_replace_finished)
            self._replace_worker.error.connect(self._on_replace_error)
            self._replace_worker.start()
            
    def _on_replace_finished(self, updated_count):
        self.central_stack.setEnabled(True)
        self.refresh_structure()
        self.update_live_preview()
        QMessageBox.information(self, "Find & Replace Complete", f"Successfully updated {updated_count} blocks.")
        self.statusBar().showMessage(f"Global Replace complete: {updated_count} blocks updated.", 5000)

    def _on_replace_error(self, err_msg):
        self.central_stack.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Find & Replace failed: {err_msg}")

    def show_export_dialog(self):
        if not self.current_book_id: return
        
        dialog = ExportDialog(self)
        if dialog.exec():
            options = dialog.get_options()
            fmt = options['format']
            
            ext = "epub" if fmt == "epub" else "docx" if fmt == "docx" else "pdf"
            file_filter = "ePub Files (*.epub)" if fmt == "epub" else "Word Documents (*.docx)" if fmt == "docx" else "PDF Files (*.pdf)"
            
            file_path, _ = QFileDialog.getSaveFileName(self, f"Save {ext.upper()}", f"book.{ext}", file_filter)
            if not file_path: return
            
            styles = self.properties_panel.get_styles()
            styles['theme'] = self.theme_combo.currentData()
            styles['enable_tajweed'] = options['enable_tajweed']
            styles['include_footnotes'] = options['include_footnotes']
            styles['include_cover'] = options['include_cover']
            styles['press_ready'] = (fmt == "pdf_print")
            
            if fmt == "epub":
                self.epub_progress = QProgressDialog("Generating Digital ePub...\nStructuring metadata and chapters.", None, 0, 0, self)
                self.epub_progress.setWindowTitle("Exporting ePub")
                self.epub_progress.setWindowModality(Qt.WindowModality.WindowModal)
                self.epub_progress.setCancelButton(None)
                self.epub_progress.show()
                
                self.statusBar().showMessage("Building ePub Engine...")
                self.epub_worker = EPUBWorker(self.current_book_id, file_path, styles)
                self.epub_worker.finished.connect(self._on_epub_finished)
                self.epub_worker.start()
            elif fmt == "docx":
                self.docx_progress = QProgressDialog("Generating Word Document...\nApplying RTL shaping and styles.", None, 0, 0, self)
                self.docx_progress.setWindowTitle("Exporting DOCX")
                self.docx_progress.setWindowModality(Qt.WindowModality.WindowModal)
                self.docx_progress.setCancelButton(None)
                self.docx_progress.show()
                
                self.statusBar().showMessage("Building DOCX Engine...")
                self.docx_worker = DOCXWorker(self.current_book_id, file_path, styles)
                self.docx_worker.finished.connect(self._on_docx_finished)
                self.docx_worker.start()
            else:
                self.pdf_progress = QProgressDialog("Generating PDF...\nThis may take a few minutes for large books.", None, 0, 0, self)
                self.pdf_progress.setWindowTitle("Exporting PDF")
                self.pdf_progress.setWindowModality(Qt.WindowModality.WindowModal)
                self.pdf_progress.setCancelButton(None)
                self.pdf_progress.show()
                
                self.statusBar().showMessage("Building PDF Engine...")
                self.worker = PDFWorker(self.current_book_id, file_path, styles)
                self.worker.finished.connect(self._on_pdf_finished)
                self.worker.start()

    def _on_pdf_finished(self, success, message):
        if hasattr(self, 'pdf_progress'):
            self.pdf_progress.accept()
            
        if success:
            QMessageBox.information(self, "Done", f"PDF successfully exported to:\n{message}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF:\n{message}")

    def _on_epub_finished(self, success, message):
        if hasattr(self, 'epub_progress'):
            self.epub_progress.accept()
            
        if success:
            QMessageBox.information(self, "Done", f"ePub successfully exported to:\n{message}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to generate ePub:\n{message}")

    def _on_docx_finished(self, success, message):
        if hasattr(self, 'docx_progress'):
            self.docx_progress.accept()
            
        if success:
            QMessageBox.information(self, "Done", f"DOCX successfully exported to:\n{message}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to generate DOCX:\n{message}")

def main():
    install_global_exception_handler()
    app = QApplication(sys.argv)
    window = MaktabaDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
