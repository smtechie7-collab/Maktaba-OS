import sys
import os
import json
import re

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QMessageBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
                             QTabWidget, QDockWidget, QFileDialog, QTextBrowser, QMenuBar, QMenu, QStackedWidget,
                             QListWidgetItem, QFrame, QStyle, QComboBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    WEB_ENGINE_AVAILABLE = True
except ImportError as e:
    WEB_ENGINE_AVAILABLE = False

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator
from src.core.config import load_config
from src.core.errors import install_global_exception_handler
from src.ui.dialogs import BookDialog, ChapterDialog, BulkImportDialog
from src.ui.components.editor_panel import EditorPanel
from src.ui.components.audio_panel import AudioPanel
from src.ui.components.properties_panel import PropertiesPanel
from src.ui.components.web_bridge import WebBridge
from src.ui.components.command_palette import CommandPalette
from src.ui.workers import DbWorker
from src.ui.styles.style_loader import load_stylesheet

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
                cursor.execute("SELECT title, author, metadata FROM Books WHERE id = ?", (self.book_id,))
                book_info = cursor.fetchone()
                
            book_metadata = {}
            if book_info and book_info['metadata']:
                book_metadata = json.loads(book_info['metadata']) if isinstance(book_info['metadata'], str) else book_info['metadata']

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
                    current_chapter_dict['blocks'].append({
                        "block_id": block['block_id'],
                        "content_data": json.loads(block['content_data']),
                        "content_type": block['content_type']
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
                target_chapter['blocks'].append({
                    "block_id": "draft",
                    "content_data": self.draft_data,
                    "content_type": "text"
                })

            html_content = template.render(
                book_title=book_info['title'] if book_info else "Preview",
                author=book_info['author'] if book_info else "",
                book_metadata=book_metadata,
                chapters=chapters_data,
                margins=self.styles.get("margins"),
                fonts=self.styles.get("fonts")
            )
            self.finished.emit(self.request_id, True, html_content)
        except Exception as e:
            self.finished.emit(self.request_id, False, str(e))

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
        self.book_list.setMaximumWidth(800)
        self.book_list.setStyleSheet("""
            QListWidget { font-size: 16px; padding: 10px; border-radius: 10px; border: 2px solid #CFD7DE; }
            QListWidget::item { padding: 15px; border-bottom: 1px solid #EEF1F4; }
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

        self.central_tabs = QTabWidget()
        self.editor_panel = EditorPanel()
        self.editor_panel.save_requested.connect(self.save_content_block)
        self.editor_panel.text_changed_live.connect(self.update_live_preview)
        self.build_command_bar()
        
        self.central_tabs.addTab(self.editor_panel, "📝 Maktaba Editor")
        self.audio_panel = AudioPanel()
        self.central_tabs.addTab(self.audio_panel, "🎵 Audio Engine")
        self.studio_layout.addWidget(self.central_tabs)
        self.central_stack.addWidget(self.studio_page)
        
        self.central_tabs.setTabText(0, "Editor")
        self.central_tabs.setTabText(1, "Audio")

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

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["Book Structure"])
        self.chapter_tree.itemClicked.connect(self.handle_structure_click)
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
        
        prop_layout.addWidget(self.properties_panel)
        self.gen_pdf_btn = QPushButton("Build Press PDF")
        self.gen_pdf_btn.setObjectName("primaryBtn")
        self.gen_pdf_btn.clicked.connect(self.handle_pdf_generation)
        prop_layout.addWidget(self.gen_pdf_btn)

        self.prop_dock.setWidget(prop_widget)
        self.tabifyDockWidget(self.preview_dock, self.prop_dock)
        self.preview_dock.raise_()

        self.create_menu_bar()
        self.install_shortcuts()
        self.default_window_state = self.saveState()
        self.load_books()
        self.update_action_states()
        self.statusBar().showMessage("Maktaba Studio Ready.")
        self.show_library_view()

    def show_library_view(self):
        """Hides the complex studio and shows only the clean library screen."""
        self.central_stack.setCurrentWidget(self.library_page)
        self.nav_dock.hide()
        self.preview_dock.hide()
        self.prop_dock.hide()
        if hasattr(self, 'command_bar'):
            self.command_bar.hide()
        self.statusBar().showMessage("Maktaba Library")

    def on_library_selection_changed(self):
        has_selection = len(self.book_list.selectedItems()) > 0
        self.lib_edit_btn.setEnabled(has_selection)
        self.lib_delete_btn.setEnabled(has_selection)

    def open_selected_book(self, item):
        """Transitions from the library into the authoring studio."""
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
        
        layout.addWidget(self.quick_chapter_btn)
        layout.addWidget(self.smart_paste_btn)
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
            ("Ctrl+P", self.handle_pdf_generation),
            ("Ctrl+I", self.show_bulk_import_dialog),
            ("Esc", self.editor_panel.clear_fields),
        ]
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)

    def show_command_palette(self):
        palette = CommandPalette(self)
        palette.command_selected.connect(self.execute_palette_command)
        
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
        elif command == "pdf":
            self.handle_pdf_generation()
        elif command == "import":
            self.show_bulk_import_dialog()
        elif command == "search":
            self.book_search.setFocus()
        else:
            self.book_search.setText(command)
            self.book_search.setFocus()

    def execute_quick_command(self):
        pass # Obsolete, removed usage

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
                    bridge_script = "<script src='qrc:///qtwebchannel/qwebchannel.js'></script><script>new QWebChannel(qt.webChannelTransport, function(channel){ window.pybridge = channel.objects.pybridge; });</script>"
                    self.preview_browser.setHtml(bridge_script + message, QUrl.fromLocalFile(str(self.config.template_dir) + "/"))
                else:
                    self.preview_browser.setHtml(message)
            else:
                print(f"Live Preview Error: {message}")

        if self.preview_pending:
            self.preview_pending = False
            self.preview_timer.start()

    def update_live_preview_sync(self):
        if not self.current_book_id: return
        try:
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader(str(self.config.template_dir)))
            template = env.get_template("book_template.html")
            
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, author, metadata FROM Books WHERE id = ?", (self.current_book_id,))
                book_info = cursor.fetchone()
                
            book_metadata = {}
            if book_info and book_info['metadata']:
                book_metadata = json.loads(book_info['metadata']) if isinstance(book_info['metadata'], str) else book_info['metadata']
                
            content_blocks = self.db.get_book_content(self.current_book_id)
            chapters_data = []
            current_chapter_id = None
            current_chapter_dict = None
            
            for block in content_blocks:
                if block['chapter_id'] != current_chapter_id:
                    current_chapter_id = block['chapter_id']
                    current_chapter_dict = {
                        "chapter_title": block['chapter_title'], 
                        "chapter_type": block.get('chapter_type', 'Content Chapter'),
                        "blocks": []
                    }
                    chapters_data.append(current_chapter_dict)
                
                if block['block_id']:
                    current_chapter_dict['blocks'].append({
                        "block_id": block['block_id'],
                        "content_data": json.loads(block['content_data']),
                        "content_type": block['content_type']
                    })
                
            draft_data = self.editor_panel.get_data()
            has_draft = any([draft_data.get('ar'), draft_data.get('ur'), draft_data.get('guj'), draft_data.get('en')])
            
            if has_draft and chapters_data:
                chapters_data[-1]['blocks'].append({
                    "block_id": "draft",
                    "content_data": draft_data,
                    "content_type": "text"
                })

            styles = self.properties_panel.get_styles()
            html_content = template.render(
                book_title=book_info['title'] if book_info else "Preview",
                author=book_info['author'] if book_info else "",
                book_metadata=book_metadata,
                chapters=chapters_data, margins=styles.get("margins"), fonts=styles.get("fonts")
            )
            self.preview_browser.setHtml(html_content)
        except Exception as e:
            print(f"Live Preview Error: {e}")

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
            author = f" | {row['author']}" if row.get("author") else ""
            item = QListWidgetItem(f"{row['id']} - {row['title']}{author}")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.book_list.addItem(item)
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
        self.db.delete_chapter(self.current_chapter_id)
        self.current_chapter_id = None
        self.selected_block_id = None
        self.refresh_structure()
        self.update_action_states()

    def move_current_chapter(self, direction):
        if not self.current_chapter_id:
            return QMessageBox.warning(self, "Error", "Select a chapter first.")
        self.db.move_chapter(self.current_chapter_id, direction)
        self.refresh_structure()
        self.update_action_states()

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
        try:
            if update_id:
                self.db.update_content_block(update_id, data)
                self.statusBar().showMessage(f"Block #{update_id} Updated!", 3000)
            else:
                if not self.current_chapter_id:
                    return QMessageBox.warning(self, "Error", "Select a target chapter first.")
                self.selected_block_id = self.db.add_content_block(self.current_chapter_id, data)
                self.statusBar().showMessage(f"New block saved to chapter #{self.current_chapter_id}.", 3000)

            self.refresh_structure() 
            self.editor_panel.clear_fields()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

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
        self.db.soft_delete_content_block(self.selected_block_id)
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
        self.db.move_content_block(self.selected_block_id, direction)
        self.refresh_structure()
        self.update_live_preview()

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
        self.gen_pdf_btn.setEnabled(has_book)
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
        self.update_context_summary()
        
        # UX Fix: Disable the editor completely if no chapter is selected to prevent confusion
        if hasattr(self, "editor_panel"):
            self.editor_panel.setEnabled(has_chapter)

    def show_bulk_import_dialog(self):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Select a book.")
        if not self.current_chapter_id: return QMessageBox.warning(self, "Error", "Select a chapter from the Project Explorer first to paste into.")
        
        dialog = BulkImportDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            
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
                
                # Only insert if at least one language field was populated
                if any([block_data["ar"], block_data["ur"], block_data["guj"], block_data["en"]]):
                    self.db.add_content_block(self.current_chapter_id, block_data)
                    imported += 1
            
            self.refresh_structure()
            self.update_live_preview()
            QMessageBox.information(self, "Imported", f"{imported} blocks successfully extracted and added to Chapter #{self.current_chapter_id}.")

    def handle_pdf_generation(self):
        if not self.current_book_id: return
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "book.pdf", "PDF Files (*.pdf)")
        if not file_path: return
        self.statusBar().showMessage("Building PDF Engine...")
        styles = self.properties_panel.get_styles()
        self.worker = PDFWorker(self.current_book_id, file_path, styles)
        self.worker.finished.connect(lambda s, m: QMessageBox.information(self, "Done", m) if s else QMessageBox.critical(self, "Error", m))
        self.worker.start()

def main():
    install_global_exception_handler()
    app = QApplication(sys.argv)
    window = MaktabaDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
