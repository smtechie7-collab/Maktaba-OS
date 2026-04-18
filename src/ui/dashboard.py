import sys
import os
import json
import re

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QListWidget,
                             QMessageBox, QLineEdit, QTreeWidget, QTreeWidgetItem,
                             QTabWidget, QDockWidget, QFileDialog, QTextBrowser, QMenuBar, QMenu)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QAction

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    WEB_ENGINE_AVAILABLE = True
except ImportError as e:
    WEB_ENGINE_AVAILABLE = False

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator
from src.ui.dialogs import BookDialog, ChapterDialog, BulkImportDialog
from src.ui.components.editor_panel import EditorPanel
from src.ui.components.audio_panel import AudioPanel
from src.ui.components.properties_panel import PropertiesPanel
from src.ui.components.web_bridge import WebBridge

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

class MaktabaDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager("maktaba_production.db")
        self.current_book_id = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Maktaba-OS Studio | Pro V5.0 Edition")
        self.setMinimumSize(1400, 900)
        
        self.setStyleSheet("""
            QMainWindow { background-color: #F3F4F6; }
            QWidget { color: #000000; font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 13px; }
            QLabel { font-weight: bold; color: #111111; }
            QDockWidget { font-weight: bold; color: #000000; font-size: 14px; }
            QDockWidget::title { background: #E5E7EB; text-align: left; padding: 8px; border: 1px solid #D1D5DB; color: #000000; }
            QListWidget, QTreeWidget { background-color: #FFFFFF; border: 2px solid #A0A0A0; color: #000000; font-weight: 600; font-size: 14px; padding: 5px; border-radius: 4px; }
            QListWidget::item, QTreeWidget::item { padding: 10px; border-bottom: 1px solid #E5E7EB; }
            QListWidget::item:selected, QTreeWidget::item:selected { background-color: #0066CC; color: #FFFFFF; }
            QPushButton { background-color: #E5E7EB; border: 1px solid #9CA3AF; padding: 8px; border-radius: 4px; color: #000000; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #D1D5DB; }
            QPushButton#primaryBtn { background-color: #0066CC; color: white; border: none; font-size: 14px;}
            QPushButton#primaryBtn:hover { background-color: #0052A3; }
            QLineEdit, QTextEdit, QTextBrowser { background-color: #FFFFFF; border: 2px solid #A0A0A0; padding: 6px; border-radius: 3px; color: #000000; font-weight: bold; }
            QLineEdit:focus, QTextEdit:focus, QTextBrowser:focus { border: 2px solid #0066CC; }
            QTabWidget::pane { border: 2px solid #A0A0A0; background: #F9FAFB; }
            QTabBar::tab { background: #E5E7EB; color: #333333; padding: 10px 20px; border: 1px solid #A0A0A0; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }
            QTabBar::tab:selected { background: #0066CC; color: #FFFFFF; }
            QMenuBar { background-color: #E5E7EB; color: #000000; font-weight: bold; font-size: 13px; border-bottom: 1px solid #A0A0A0; }
            QMenuBar::item { padding: 6px 12px; background: transparent; }
            QMenuBar::item:selected { background-color: #D1D5DB; }
            QMenu { background-color: #FFFFFF; color: #000000; border: 1px solid #A0A0A0; font-weight: bold; }
            QMenu::item { padding: 8px 24px; }
            QMenu::item:selected { background-color: #0066CC; color: #FFFFFF; }
        """)

        self.central_tabs = QTabWidget()
        self.editor_panel = EditorPanel()
        self.editor_panel.save_requested.connect(self.save_content_block)
        self.editor_panel.text_changed_live.connect(self.update_live_preview)
        
        self.central_tabs.addTab(self.editor_panel, "📝 Maktaba Editor")
        self.audio_panel = AudioPanel()
        self.central_tabs.addTab(self.audio_panel, "🎵 Audio Engine")
        self.setCentralWidget(self.central_tabs)

        self.nav_dock = QDockWidget("Project Explorer", self)
        self.nav_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        nav_widget = QWidget()
        nav_layout = QVBoxLayout(nav_widget)
        
        btn_layout = QHBoxLayout()
        self.add_book_btn = QPushButton("+ Book")
        self.add_book_btn.clicked.connect(self.show_add_book_dialog)
        self.add_chap_btn = QPushButton("+ Element")
        self.add_chap_btn.clicked.connect(self.show_add_chapter_dialog)
        btn_layout.addWidget(self.add_book_btn); btn_layout.addWidget(self.add_chap_btn)
        nav_layout.addLayout(btn_layout)

        self.bulk_import_btn = QPushButton("📥 Smart Bulk Import")
        self.bulk_import_btn.setObjectName("primaryBtn")
        self.bulk_import_btn.clicked.connect(self.show_bulk_import_dialog)
        nav_layout.addWidget(self.bulk_import_btn)

        self.book_list = QListWidget()
        self.book_list.itemSelectionChanged.connect(self.handle_selection_change)
        nav_layout.addWidget(QLabel("Library Books:"))
        nav_layout.addWidget(self.book_list)

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["Book Structure"])
        self.chapter_tree.itemClicked.connect(self.update_live_preview)
        nav_layout.addWidget(self.chapter_tree)

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
        self.gen_pdf_btn = QPushButton("📄 Build Press PDF")
        self.gen_pdf_btn.setObjectName("primaryBtn")
        self.gen_pdf_btn.clicked.connect(self.handle_pdf_generation)
        prop_layout.addWidget(self.gen_pdf_btn)

        self.prop_dock.setWidget(prop_widget)
        self.tabifyDockWidget(self.preview_dock, self.prop_dock)
        self.preview_dock.raise_()

        self.create_menu_bar()
        self.default_window_state = self.saveState()
        self.load_books()
        self.statusBar().showMessage("Maktaba Studio Ready.")

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
                raw_data = block['content_data']
                data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                self.editor_panel.load_data_for_editing(block_id, data_dict)
                self.statusBar().showMessage(f"Loaded Block #{block_id} for editing.", 3000)
                break

    def update_live_preview(self):
        if not self.current_book_id: return
        try:
            from jinja2 import Environment, FileSystemLoader
            template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/layout/templates'))
            env = Environment(loader=FileSystemLoader(template_dir))
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
        self.book_list.clear()
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM Books")
            for row in cursor.fetchall():
                self.book_list.addItem(f"{row['id']} - {row['title']}")

    def show_add_book_dialog(self):
        dialog = BookDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            self.db.add_book(data['title'], data['author'], data['language'])
            self.load_books()

    def show_add_chapter_dialog(self):
        selected = self.book_list.currentItem()
        if not selected: return QMessageBox.warning(self, "Error", "Select a book first.")
        book_id = int(selected.text().split(" - ")[0])
        dialog = ChapterDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            # Passing chapter TYPE to database now
            self.db.add_chapter(book_id, data['title'], data['sequence'], data['type'])
            self.handle_selection_change()

    def handle_selection_change(self):
        selected = self.book_list.currentItem()
        if not selected: 
            self.current_book_id = None
            return
            
        self.current_book_id = int(selected.text().split(" - ")[0])
        self.chapter_tree.clear()
        content = self.db.get_book_content(self.current_book_id)
        
        chapters = {}
        for block in content:
            chap_title = block['chapter_title']
            chap_type = block.get('chapter_type', 'Chapter')
            if chap_title not in chapters:
                # Tree now shows if it's a Cover or Chapter
                chap_item = QTreeWidgetItem(self.chapter_tree, [f"{chap_title} [{chap_type}]"])
                chap_item.setExpanded(True)
                chapters[chap_title] = chap_item
            
            if block['block_id']:
                block_data = json.loads(block['content_data'])
                preview_text = block_data.get('ar', block_data.get('en', 'Empty Block'))[:30] + "..."
                QTreeWidgetItem(chapters[chap_title], [preview_text])
            
        self.update_live_preview()

    def save_content_block(self, data):
        if not self.current_book_id: return QMessageBox.warning(self, "Error", "Select a book.")
        update_id = data.pop('update_block_id', None)
        try:
            if update_id:
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE Content_Blocks SET content_data = ?, version = version + 1 WHERE id = ?", 
                        (json.dumps(data), update_id)
                    )
                self.statusBar().showMessage(f"Block #{update_id} Updated!", 3000)
            else:
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM Chapters WHERE book_id = ? ORDER BY sequence_number DESC LIMIT 1", (self.current_book_id,))
                    result = cursor.fetchone()
                    if not result: return QMessageBox.warning(self, "Error", "Create a chapter first.")
                    chapter_id = result[0]
                self.db.add_content_block(chapter_id, data)
                self.statusBar().showMessage("New block saved!", 3000)

            self.handle_selection_change() 
            self.editor_panel.clear_fields()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")

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
    app = QApplication(sys.argv)
    window = MaktabaDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()