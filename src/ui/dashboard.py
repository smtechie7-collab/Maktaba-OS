import sys
import os
import json
import re

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QMessageBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
                             QTabWidget, QDockWidget, QFileDialog, QTextBrowser, QMenuBar, QMenu,
                             QListWidgetItem, QFrame)
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

    def __init__(self, request_id, book_id, db_path, template_dir, draft_data, styles, active_chapter_id=None):
        super().__init__()
        self.request_id = request_id
        self.book_id = book_id
        self.db_path = db_path
        self.template_dir = template_dir
        self.draft_data = draft_data
        self.styles = styles
        self.active_chapter_id = active_chapter_id

    def run(self):
        try:
            from jinja2 import Environment, FileSystemLoader

            db = DatabaseManager(self.db_path)
            env = Environment(loader=FileSystemLoader(self.template_dir))
            template = env.get_template("book_template.html")

            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT title, author FROM Books WHERE id = ?", (self.book_id,))
                book_info = cursor.fetchone()

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

        self.main_surface = QWidget()
        self.main_layout = QVBoxLayout(self.main_surface)
        self.main_layout.setContentsMargins(14, 12, 14, 14)
        self.main_layout.setSpacing(10)

        self.central_tabs = QTabWidget()
        self.editor_panel = EditorPanel()
        self.editor_panel.save_requested.connect(self.save_content_block)
        self.editor_panel.text_changed_live.connect(self.update_live_preview)
        self.build_command_bar()
        
        self.central_tabs.addTab(self.editor_panel, "📝 Maktaba Editor")
        self.audio_panel = AudioPanel()
        self.central_tabs.addTab(self.audio_panel, "🎵 Audio Engine")
        self.main_layout.addWidget(self.central_tabs)
        self.setCentralWidget(self.main_surface)
        self.central_tabs.setTabText(0, "Editor")
        self.central_tabs.setTabText(1, "Audio")

        self.nav_dock = QDockWidget("Project Explorer", self)
        self.nav_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        
        btn_layout = QHBoxLayout()
        self.add_book_btn = QPushButton("+ Book")
        self.add_book_btn.clicked.connect(self.show_add_book_dialog)
        self.edit_book_btn = QPushButton("Edit")
        self.edit_book_btn.clicked.connect(self.show_edit_book_dialog)
        self.delete_book_btn = QPushButton("Delete")
        self.delete_book_btn.clicked.connect(self.delete_current_book)
        btn_layout.addWidget(self.add_book_btn)
        btn_layout.addWidget(self.edit_book_btn)
        btn_layout.addWidget(self.delete_book_btn)
        nav_layout.addLayout(btn_layout)

        structure_btn_layout = QHBoxLayout()
        self.add_chap_btn = QPushButton("+ Chapter")
        self.add_chap_btn.clicked.connect(self.show_add_chapter_dialog)
        self.edit_chap_btn = QPushButton("Edit")
        self.edit_chap_btn.clicked.connect(self.show_edit_chapter_dialog)
        self.delete_chap_btn = QPushButton("Delete")
        self.delete_chap_btn.clicked.connect(self.delete_current_chapter)
        structure_btn_layout.addWidget(self.add_chap_btn)
        structure_btn_layout.addWidget(self.edit_chap_btn)
        structure_btn_layout.addWidget(self.delete_chap_btn)
        nav_layout.addLayout(structure_btn_layout)

        order_btn_layout = QHBoxLayout()
        self.chapter_up_btn = QPushButton("Chapter Up")
        self.chapter_up_btn.clicked.connect(lambda: self.move_current_chapter(-1))
        self.chapter_down_btn = QPushButton("Chapter Down")
        self.chapter_down_btn.clicked.connect(lambda: self.move_current_chapter(1))
        order_btn_layout.addWidget(self.chapter_up_btn)
        order_btn_layout.addWidget(self.chapter_down_btn)
        nav_layout.addLayout(order_btn_layout)

        block_btn_layout = QHBoxLayout()
        self.block_up_btn = QPushButton("Block Up")
        self.block_up_btn.clicked.connect(lambda: self.move_selected_block(-1))
        self.block_down_btn = QPushButton("Block Down")
        self.block_down_btn.clicked.connect(lambda: self.move_selected_block(1))
        self.duplicate_block_btn = QPushButton("Duplicate")
        self.duplicate_block_btn.clicked.connect(self.duplicate_selected_block)
        self.delete_block_btn = QPushButton("Delete Block")
        self.delete_block_btn.clicked.connect(self.delete_selected_block)
        block_btn_layout.addWidget(self.block_up_btn)
        block_btn_layout.addWidget(self.block_down_btn)
        block_btn_layout.addWidget(self.duplicate_block_btn)
        block_btn_layout.addWidget(self.delete_block_btn)
        nav_layout.addLayout(block_btn_layout)

        self.bulk_import_btn = QPushButton("Smart Bulk Import")
        self.bulk_import_btn.setObjectName("primaryBtn")
        self.bulk_import_btn.clicked.connect(self.show_bulk_import_dialog)
        nav_layout.addWidget(self.bulk_import_btn)

        self.book_search = QLineEdit()
        self.book_search.setPlaceholderText("Search books...")
        self.book_search.textChanged.connect(self.apply_book_filter)
        nav_layout.addWidget(self.book_search)

        self.book_list = QListWidget()
        self.book_list.itemSelectionChanged.connect(self.handle_selection_change)
        nav_layout.addWidget(QLabel("Library Books:"))
        nav_layout.addWidget(self.book_list)
        self.book_empty_label = QLabel("No books yet. Create a book to start.")
        nav_layout.addWidget(self.book_empty_label)

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
        
        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenLinks(False)
        self.preview_browser.anchorClicked.connect(self.handle_preview_click)
        self.preview_browser.setHtml("<h2 style='color:#888; text-align:center;'>Select a book to see live preview...</h2>")
        
        self.preview_dock.setWidget(self.preview_browser)
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

        self.command_input = QLineEdit()
        self.command_input.setObjectName("commandInput")
        self.command_input.setPlaceholderText("Command or search")
        self.command_input.returnPressed.connect(self.execute_quick_command)
        layout.addWidget(self.command_input, stretch=3)

        self.quick_book_btn = QPushButton("New Book")
        self.quick_book_btn.clicked.connect(self.show_add_book_dialog)
        self.quick_chapter_btn = QPushButton("New Chapter")
        self.quick_chapter_btn.clicked.connect(self.show_add_chapter_dialog)
        self.quick_save_btn = QPushButton("Save Block")
        self.quick_save_btn.setObjectName("primaryBtn")
        self.quick_save_btn.clicked.connect(self.editor_panel.on_save_clicked)
        layout.addWidget(self.quick_book_btn)
        layout.addWidget(self.quick_chapter_btn)
        layout.addWidget(self.quick_save_btn)

        self.activity_label = QLabel("Ready")
        self.activity_label.setObjectName("activityPill")
        layout.addWidget(self.activity_label)
        self.main_layout.addWidget(self.command_bar)

    def install_shortcuts(self):
        shortcuts = [
            ("Ctrl+N", self.show_add_book_dialog),
            ("Ctrl+Shift+N", self.show_add_chapter_dialog),
            ("Ctrl+S", self.editor_panel.on_save_clicked),
            ("Ctrl+F", self.book_search.setFocus),
            ("Ctrl+K", self.command_input.setFocus),
            ("Ctrl+P", self.handle_pdf_generation),
            ("Ctrl+I", self.show_bulk_import_dialog),
            ("Esc", self.editor_panel.clear_fields),
        ]
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)

    def execute_quick_command(self):
        command = self.command_input.text().strip()
        lowered = command.lower()
        if not command:
            return

        if lowered in {"new book", "book", "/book"}:
            self.command_input.clear()
            self.show_add_book_dialog()
        elif lowered in {"new chapter", "chapter", "/chapter"}:
            self.command_input.clear()
            self.show_add_chapter_dialog()
        elif lowered in {"save", "save block", "/save"}:
            self.command_input.clear()
            self.editor_panel.on_save_clicked()
        elif lowered in {"pdf", "export pdf", "/pdf"}:
            self.command_input.clear()
            self.handle_pdf_generation()
        elif lowered in {"import", "bulk import", "/import"}:
            self.command_input.clear()
            self.show_bulk_import_dialog()
        else:
            self.book_search.setText(command)
            self.book_search.setFocus()

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
        self.preview_worker = PreviewWorker(
            request_id=request_id,
            book_id=self.current_book_id,
            db_path=str(self.config.db_path),
            template_dir=str(self.config.template_dir),
            draft_data=draft_data,
            styles=styles,
            active_chapter_id=self.current_chapter_id
        )
        self.preview_worker.finished.connect(self._handle_preview_finished)
        self.preview_worker.start()

    def _handle_preview_finished(self, request_id, success, message):
        if request_id == self.preview_request_id:
            if success:
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
                cursor.execute("SELECT title, author FROM Books WHERE id = ?", (self.current_book_id,))
                book_info = cursor.fetchone()
                
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
                chapters=chapters_data, margins=styles.get("margins"), fonts=styles.get("fonts")
            )
            self.preview_browser.setHtml(html_content)
        except Exception as e:
            print(f"Live Preview Error: {e}")

    def load_books(self):
        self.all_books = self.db.list_books()
        self.apply_book_filter()

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
        if selected_row_index is not None:
            self.book_list.setCurrentRow(selected_row_index)
        elif filtered_books:
            self.book_list.setCurrentRow(0)
        else:
            self.current_book_id = None
            self.current_chapter_id = None
            self.selected_block_id = None
            self.chapter_tree.clear()
            self.structure_empty_label.setVisible(True)
            self.preview_browser.setHtml("<h2 style='color:#888; text-align:center;'>Create or select a book to see live preview...</h2>")
            self.update_action_states()

    def show_add_book_dialog(self):
        dialog = BookDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            self.current_book_id = self.db.add_book(data['title'], data['author'], data['language'])
            self.load_books()

    def show_edit_book_dialog(self):
        if not self.current_book_id:
            return QMessageBox.warning(self, "Error", "Select a book first.")
        book = self.db.get_book(self.current_book_id)
        if not book:
            return QMessageBox.warning(self, "Error", "Selected book was not found.")
        dialog = BookDialog(self, book)
        if dialog.exec():
            data = dialog.get_data()
            self.db.update_book(self.current_book_id, data['title'], data['author'], data['language'])
            self.load_books()

    def delete_current_book(self):
        if not self.current_book_id:
            return QMessageBox.warning(self, "Error", "Select a book first.")
        reply = QMessageBox.question(
            self,
            "Delete Book",
            "Delete this book and all chapters/blocks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_book(self.current_book_id)
        self.current_book_id = None
        self.current_chapter_id = None
        self.selected_block_id = None
        self.chapter_tree.clear()
        self.load_books()
        self.preview_browser.setHtml("<h2 style='color:#888; text-align:center;'>Select a book to see live preview...</h2>")
        self.update_action_states()

    def show_add_chapter_dialog(self):
        selected = self.book_list.currentItem()
        if not selected: return QMessageBox.warning(self, "Error", "Select a book first.")
        book_id = selected.data(Qt.ItemDataRole.UserRole)
        dialog = ChapterDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            # Passing chapter TYPE to database now
            self.current_chapter_id = self.db.add_chapter(book_id, data['title'], data['sequence'], data['type'])
            self.handle_selection_change()

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
            self.handle_selection_change()

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
        self.handle_selection_change()

    def move_current_chapter(self, direction):
        if not self.current_chapter_id:
            return QMessageBox.warning(self, "Error", "Select a chapter first.")
        self.db.move_chapter(self.current_chapter_id, direction)
        self.handle_selection_change()

    def handle_selection_change(self):
        selected = self.book_list.currentItem()
        if not selected: 
            self.current_book_id = None
            self.current_chapter_id = None
            self.selected_block_id = None
            self.update_action_states()
            return
            
        selected_book_id = selected.data(Qt.ItemDataRole.UserRole)
        if selected_book_id != self.current_book_id:
            self.current_book_id = selected_book_id
            self.current_chapter_id = None
            self.selected_block_id = None
        self.refresh_structure()
        self.update_live_preview()
        self.update_action_states()

    def refresh_structure(self):
        self.chapter_tree.clear()
        content = self.db.get_book_content(self.current_book_id)
        chapter_rows = self.db.list_chapters(self.current_book_id)
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

        self.edit_book_btn.setEnabled(has_book)
        self.delete_book_btn.setEnabled(has_book)
        self.add_chap_btn.setEnabled(has_book)
        self.edit_chap_btn.setEnabled(has_chapter)
        self.delete_chap_btn.setEnabled(has_chapter)
        self.chapter_up_btn.setEnabled(has_chapter)
        self.chapter_down_btn.setEnabled(has_chapter)
        self.bulk_import_btn.setEnabled(has_book and has_chapter)
        self.gen_pdf_btn.setEnabled(has_book)
        self.block_up_btn.setEnabled(has_block)
        self.block_down_btn.setEnabled(has_block)
        self.duplicate_block_btn.setEnabled(has_block)
        self.delete_block_btn.setEnabled(has_block)
        if hasattr(self, "quick_chapter_btn"):
            self.quick_chapter_btn.setEnabled(has_book)
        if hasattr(self, "quick_save_btn"):
            self.quick_save_btn.setEnabled(has_book and has_chapter)
        self.update_context_summary()

    def show_bulk_import_dialog(self):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Select a book.")
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM Chapters WHERE book_id = ? ORDER BY sequence_number", (self.current_book_id,))
            chapters = cursor.fetchall()
            if not chapters: return
        
        items = [f"{c['id']} - {c['title']}" for c in chapters]
        from PyQt6.QtWidgets import QInputDialog
        item, ok = QInputDialog.getItem(self, "Select Chapter", "Bulk Import to:", items, 0, False)
        
        if ok and item:
            chapter_id = int(item.split(" - ")[0])
            dialog = BulkImportDialog(self)
            if dialog.exec():
                data = dialog.get_data()
                blocks = re.split(r'\n\s*\n', data['text'].strip())
                imported = 0
                for block in blocks:
                    lines = block.strip().split("\n")
                    if not lines: continue
                    block_data = {"ar": "", "ur": "", "guj": "", "en": "", "reference": "", "metadata": data['metadata']}
                    for line in lines:
                        line = line.strip()
                        if re.search(r'[\u0a80-\u0aff]', line): block_data["guj"] = line
                        elif re.search(r'^[a-zA-Z0-9\s.,!?\'"-]+$', line): block_data["en"] = line
                        elif re.search(r'[\u0600-\u06ff]', line):
                            if not block_data["ar"]: block_data["ar"] = line
                            else: block_data["ur"] = line
                        else:
                            if not block_data["ar"]: block_data["ar"] = line
                    self.db.add_content_block(chapter_id, block_data)
                    imported += 1
                self.handle_selection_change()
                QMessageBox.information(self, "Imported", f"{imported} blocks processed.")

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
