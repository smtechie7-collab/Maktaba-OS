import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QMessageBox, QFrame, QLineEdit, QDialog, QFormLayout,
                             QComboBox, QTextEdit, QSpinBox, QFileDialog, QTreeWidget,
                             QTreeWidgetItem, QSplitter)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator

class PDFWorker(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, book_id, output_path):
        super().__init__()
        self.book_id = book_id
        self.output_path = output_path

    def run(self):
        try:
            generator = PDFGenerator()
            generator.generate_pdf(self.book_id, self.output_path)
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
        
        self.ur_input = QTextEdit()
        self.ur_input.setPlaceholderText("Urdu translation here...")
        self.ur_input.setMaximumHeight(100)
        
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

class MaktabaDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager("maktaba_production.db")
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Maktaba-OS | Digital Publishing Dashboard")
        self.setMinimumSize(900, 600)
        
        # Apply Dark Theme
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QListWidget { 
                background-color: #1e1e1e; 
                border: 1px solid #333; 
                border-radius: 5px; 
                padding: 10px;
                font-size: 14px;
            }
            QListWidget::item { padding: 10px; border-bottom: 1px solid #222; }
            QListWidget::item:selected { background-color: #3d5afe; color: white; border-radius: 3px; }
            QPushButton { 
                background-color: #333; 
                border: none; 
                padding: 12px; 
                border-radius: 5px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #444; }
            QPushButton#primaryBtn { background-color: #3d5afe; }
            QPushButton#primaryBtn:hover { background-color: #536dfe; }
            QLabel#header { font-size: 24px; font-weight: bold; color: #3d5afe; margin-bottom: 20px; }
            QLineEdit { 
                background-color: #1e1e1e; 
                border: 1px solid #333; 
                padding: 8px; 
                border-radius: 5px; 
                margin-bottom: 10px;
            }
        """)

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Use QSplitter for resizable panels
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # Left Sidebar (Book List)
        sidebar_widget = QWidget()
        sidebar = QVBoxLayout(sidebar_widget)
        header_label = QLabel("📚 Books")
        header_label.setObjectName("header")
        sidebar.addWidget(header_label)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search books...")
        self.search_bar.textChanged.connect(self.load_books)
        sidebar.addWidget(self.search_bar)

        self.add_book_btn = QPushButton("+ Add New Book")
        self.add_book_btn.setObjectName("primaryBtn")
        self.add_book_btn.clicked.connect(self.show_add_book_dialog)
        sidebar.addWidget(self.add_book_btn)

        self.book_list = QListWidget()
        self.book_list.itemSelectionChanged.connect(self.handle_selection_change)
        self.load_books()
        sidebar.addWidget(self.book_list)
        
        self.splitter.addWidget(sidebar_widget)

        # Middle Panel (Chapter Tree)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        content_header = QLabel("📖 Structure")
        content_header.setObjectName("header")
        content_layout.addWidget(content_header)

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["Title", "Type"])
        self.chapter_tree.setColumnWidth(0, 250)
        content_layout.addWidget(self.chapter_tree)

        self.splitter.addWidget(content_widget)

        # Right Panel (Details & Actions)
        right_panel_widget = QWidget()
        right_panel = QVBoxLayout(right_panel_widget)
        
        # Metadata Section
        self.metadata_label = QLabel("Details")
        self.metadata_label.setObjectName("header")
        right_panel.addWidget(self.metadata_label)

        self.details_area = QLabel("Select a book to see details")
        self.details_area.setWordWrap(True)
        self.details_area.setStyleSheet("background-color: #1e1e1e; padding: 15px; border-radius: 5px; border: 1px solid #333;")
        right_panel.addWidget(self.details_area)

        right_panel.addSpacing(20)

        # Actions Section
        actions_label = QLabel("Actions")
        actions_label.setObjectName("header")
        right_panel.addWidget(actions_label)

        self.gen_pdf_btn = QPushButton("Generate PDF")
        self.gen_pdf_btn.setObjectName("primaryBtn")
        self.gen_pdf_btn.clicked.connect(self.handle_pdf_generation)
        right_panel.addWidget(self.gen_pdf_btn)

        self.add_chapter_btn = QPushButton("+ Add Chapter")
        self.add_chapter_btn.clicked.connect(self.show_add_chapter_dialog)
        right_panel.addWidget(self.add_chapter_btn)

        self.add_content_btn = QPushButton("+ Add Content Block")
        self.add_content_btn.clicked.connect(self.show_add_content_dialog)
        right_panel.addWidget(self.add_content_btn)

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.load_books)
        right_panel.addWidget(self.refresh_btn)

        right_panel.addStretch()
        self.splitter.addWidget(right_panel_widget)

        # Initialize Status Bar
        self.statusBar().showMessage("Ready")

    def load_books(self):
        search_query = self.search_bar.text().lower()
        self.book_list.clear()
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, author FROM Books")
            for row in cursor.fetchall():
                display_text = f"{row['id']} - {row['title']}"
                # Handle potential None in author
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
                self.load_book_details(book_id) # Refresh tree
                QMessageBox.information(self, "Success", f"Chapter '{data['title']}' added successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add chapter: {str(e)}")

    def show_add_content_dialog(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        
        # We need to know which chapter to add content to. 
        # For simplicity, we'll fetch the latest chapter or ask the user.
        # Let's fetch available chapters for this book.
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM Chapters WHERE book_id = ? ORDER BY sequence_number", (book_id,))
            chapters = cursor.fetchall()
            
        if not chapters:
            QMessageBox.warning(self, "No Chapters", "Please create a chapter first!")
            return

        # Simple chapter selection dialog
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
                    self.load_book_details(book_id) # Refresh tree
                    QMessageBox.information(self, "Success", "Content block added successfully!")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to add content: {str(e)}")

    def handle_selection_change(self):
        selected = self.book_list.currentItem()
        if not selected:
            self.details_area.setText("Select a book to see details")
            self.chapter_tree.clear()
            return

        book_id = int(selected.text().split(" - ")[0])
        self.load_book_details(book_id)

    def load_book_details(self, book_id):
        # 1. Update Metadata View
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Books WHERE id = ?", (book_id,))
            book = cursor.fetchone()
            
            metadata_str = f"<b>Title:</b> {book['title']}<br>"
            metadata_str += f"<b>Author:</b> {book['author']}<br>"
            metadata_str += f"<b>Language:</b> {book['language']}<br>"
            metadata_str += f"<b>Created:</b> {book['created_at']}<br>"
            self.details_area.setText(metadata_str)

        # 2. Update Chapter Tree (Visual Hierarchy)
        self.chapter_tree.clear()
        content = self.db.get_book_content(book_id)
        
        chapters = {}
        for block in content:
            chap_title = block['chapter_title']
            if chap_title not in chapters:
                chap_item = QTreeWidgetItem(self.chapter_tree, [chap_title, "Chapter"])
                chap_item.setExpanded(True)
                chapters[chap_title] = chap_item
            
            # Add content blocks as sub-items
            block_data = json.loads(block['content_data'])
            preview_text = block_data.get('ar', block_data.get('ur', block_data.get('en', 'Text Block')))[:30] + "..."
            QTreeWidgetItem(chapters[chap_title], [preview_text, "Content"])

    def handle_pdf_generation(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        book_title = selected.text().split(" - ")[1].replace(" ", "_")
        
        # UI/UX Improvement: Let user select where to save the PDF
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", f"{book_title}.pdf", "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return

        self.gen_pdf_btn.setEnabled(False)
        self.gen_pdf_btn.setText("Generating...")
        self.statusBar().showMessage(f"Generating PDF for Book ID {book_id}...")
        
        # Run generation in a separate thread to keep UI responsive
        self.worker = PDFWorker(book_id, file_path)
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

def main():
    app = QApplication(sys.argv)
    window = MaktabaDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
