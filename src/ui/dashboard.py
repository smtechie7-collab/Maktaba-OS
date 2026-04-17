import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QListWidget, 
                             QMessageBox, QFrame)
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

        self.book_list = QListWidget()
        self.load_books()
        sidebar.addWidget(self.book_list)
        
        main_layout.addLayout(sidebar, 2)

        # Right Panel (Actions)
        actions_panel = QVBoxLayout()
        actions_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        actions_label = QLabel("Actions")
        actions_label.setObjectName("header")
        actions_panel.addWidget(actions_label)

        self.gen_pdf_btn = QPushButton("Generate PDF")
        self.gen_pdf_btn.setObjectName("primaryBtn")
        self.gen_pdf_btn.clicked.connect(self.handle_pdf_generation)
        actions_panel.addWidget(self.gen_pdf_btn)

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.load_books)
        actions_panel.addWidget(self.refresh_btn)

        main_layout.addLayout(actions_panel, 1)

    def load_books(self):
        self.book_list.clear()
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM Books")
            for row in cursor.fetchall():
                self.book_list.addItem(f"{row['id']} - {row['title']}")

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
