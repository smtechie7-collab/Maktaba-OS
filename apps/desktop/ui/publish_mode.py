"""
Publish Mode widget for Maktaba-OS layout preview and export.
Implements QWebEngineView for live PDF/HTML preview and a property inspector.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QMessageBox, QSplitter, QSpinBox, QFormLayout
)
from PyQt6.QtCore import Qt

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None  # type: ignore

from core.commands.command_bus import CommandBus


class PublishModeWidget(QWidget):
    """Main widget for Publish Mode layout configuration and preview."""

    def __init__(self, command_bus: CommandBus, parent=None):
        super().__init__(parent)
        self.command_bus = command_bus
        self.current_book_id: Optional[int] = None
        self.init_ui()

    def init_ui(self):
        """Initialize the publish mode UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Publish Mode - Layout & Export")
        header_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(header_label)
        
        self.book_label = QLabel("No book loaded")
        header_layout.addWidget(self.book_label)
        header_layout.addStretch()

        self.export_btn = QPushButton("Export Document")
        self.export_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px 15px; border-radius: 4px;")
        self.export_btn.clicked.connect(self.export_document)
        header_layout.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Property Inspector
        inspector_widget = QWidget()
        inspector_layout = QFormLayout(inspector_widget)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["A4", "Letter", "Custom"])
        inspector_layout.addRow("Page Size:", self.format_combo)

        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 100)
        self.margin_spin.setValue(20)
        self.margin_spin.setSuffix(" mm")
        inspector_layout.addRow("Margin:", self.margin_spin)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(12)
        self.font_size_spin.setSuffix(" pt")
        inspector_layout.addRow("Base Font:", self.font_size_spin)
        
        update_preview_btn = QPushButton("Update Preview")
        update_preview_btn.clicked.connect(self.update_preview)
        inspector_layout.addRow("", update_preview_btn)

        splitter.addWidget(inspector_widget)

        # Right Panel: Live Preview Area
        self.preview_frame = QFrame()
        self.preview_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.preview_frame.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        preview_layout = QVBoxLayout(self.preview_frame)
        
        if WEBENGINE_AVAILABLE and QWebEngineView:
            self.preview_view = QWebEngineView()
            self.preview_view.setHtml("<html><body style='font-family: Arial; padding: 20px; color: #7f8c8d; text-align: center;'><h2>Layout Preview</h2><p>Load a book to see live rendering.</p></body></html>")
            preview_layout.addWidget(self.preview_view)
        else:
            self.preview_view = QLabel("Live preview requires PyQt6-WebEngine.\nPlease install it (pip install PyQt6-WebEngine) to enable real-time layout rendering.")
            self.preview_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(self.preview_view)
        
        splitter.addWidget(self.preview_frame)
        splitter.setSizes([250, 750])

        layout.addWidget(splitter)

    def load_book(self, book_id: int):
        """Load a book reference for export context and update preview."""
        self.current_book_id = book_id
        document = self.command_bus.document_engine.load_document(book_id)
        if document and document.children:
            self.book_label.setText(f"Book: {document.children[0].title}")
            self.update_preview()
        else:
            self.book_label.setText("Failed to load book")

    def update_preview(self):
        """Re-render the preview HTML reflecting current inspector settings."""
        if not self.current_book_id:
            return
            
        margin = self.margin_spin.value()
        font_size = self.font_size_spin.value()
        
        html_content = f"""
        <html>
        <body style='margin: {margin}mm; font-size: {font_size}pt; font-family: serif; line-height: 1.6;'>
            <div style='border: 1px dashed #ccc; padding: 20px; background-color: #fafafa;'>
                <h1 style='text-align: center; color: #2c3e50;'>Sample Render Frame</h1>
                <p style='text-align: justify;'>This is a live layout preview. When the full rendering pipeline (WeasyPrint/Puppeteer) is connected, your document nodes will automatically inject here, strictly respecting the {margin}mm bleed limits and {font_size}pt base typography rules.</p>
            </div>
        </body>
        </html>
        """
        if WEBENGINE_AVAILABLE and isinstance(self.preview_view, QWebEngineView):
            self.preview_view.setHtml(html_content)

    def export_document(self):
        """Trigger the document export pipeline."""
        if not self.current_book_id:
            QMessageBox.warning(self, "Export Error", "No book is loaded to export.")
            return
            
        QMessageBox.information(
            self, "Export Initiated", 
            "Rendering engine triggered.\n(PDF generation logic via headless engine pending)"
        )
