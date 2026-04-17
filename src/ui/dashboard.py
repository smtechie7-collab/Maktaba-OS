import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QMessageBox, QFrame, QLineEdit)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator

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

        # Left Sidebar (Book List)
        sidebar = QVBoxLayout()
        header_label = QLabel("📚 Books")
        header_label.setObjectName("header")
        sidebar.addWidget(header_label)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search books...")
        self.search_bar.textChanged.connect(self.load_books)
        sidebar.addWidget(self.search_bar)

        self.book_list = QListWidget()
        self.book_list.itemSelectionChanged.connect(self.handle_selection_change)
        self.load_books()
        sidebar.addWidget(self.book_list)
        
        main_layout.addLayout(sidebar, 1)

        # Right Panel (Details & Actions)
        right_panel = QVBoxLayout()
        
        # Metadata Section
        self.metadata_label = QLabel("Book Details")
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

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.load_books)
        right_panel.addWidget(self.refresh_btn)

        right_panel.addStretch()
        main_layout.addLayout(right_panel, 2)

    def load_books(self):
        search_query = self.search_bar.text().lower()
        self.book_list.clear()
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, author FROM Books")
            for row in cursor.fetchall():
                display_text = f"{row['id']} - {row['title']}"
                if search_query in display_text.lower() or search_query in row['author'].lower():
                    self.book_list.addItem(display_text)

    def handle_selection_change(self):
        selected = self.book_list.currentItem()
        if not selected:
            self.details_area.setText("Select a book to see details")
            return

        book_id = int(selected.text().split(" - ")[0])
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Books WHERE id = ?", (book_id,))
            book = cursor.fetchone()
            
            metadata_str = f"<b>Title:</b> {book['title']}<br>"
            metadata_str += f"<b>Author:</b> {book['author']}<br>"
            metadata_str += f"<b>Language:</b> {book['language']}<br>"
            metadata_str += f"<b>Created:</b> {book['created_at']}<br>"
            
            self.details_area.setText(metadata_str)

    def handle_pdf_generation(self):
        selected = self.book_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a book first!")
            return

        book_id = int(selected.text().split(" - ")[0])
        output_name = f"output/book_{book_id}.pdf"
        
        try:
            self.gen_pdf_btn.setEnabled(False)
            self.gen_pdf_btn.setText("Generating...")
            QApplication.processEvents() # Keep UI responsive
            
            os.makedirs("output", exist_ok=True)
            generator = PDFGenerator()
            generator.generate_pdf(book_id, output_name)
            
            QMessageBox.information(self, "Success", f"PDF generated successfully at:\n{output_name}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate PDF: {str(e)}")
        finally:
            self.gen_pdf_btn.setEnabled(True)
            self.gen_pdf_btn.setText("Generate PDF")

def main():
    app = QApplication(sys.argv)
    window = MaktabaDashboard()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
