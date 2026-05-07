"""
Publish Mode widget for Maktaba-OS layout preview and export.
Implements QWebEngineView for live PDF/HTML preview and a property inspector.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QMessageBox, QSplitter, QSpinBox, QFormLayout,
    QSlider, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None  # type: ignore

from core.commands.command_bus import CommandBus
from modules.export.pdf_generator import PDFGenerator


class PublishModeWidget(QWidget):
    """Main widget for Publish Mode layout configuration and preview."""

    def __init__(self, command_bus: CommandBus, parent=None):
        super().__init__(parent)
        self.command_bus = command_bus
        self.current_book_id: Optional[int] = None
        
        # Auto-update timer for smooth preview (60fps)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_preview)
        self.update_timer.setInterval(1000 // 60)  # ~60fps
        
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

        self.export_btn = QPushButton("Export PDF")
        self.export_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px 15px; border-radius: 4px;")
        self.export_btn.clicked.connect(self.export_pdf)
        header_layout.addWidget(self.export_btn)
        
        self.export_epub_btn = QPushButton("Export EPUB")
        self.export_epub_btn.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; padding: 6px 15px; border-radius: 4px;")
        self.export_epub_btn.clicked.connect(self.export_epub)
        header_layout.addWidget(self.export_epub_btn)
        
        self.export_md_btn = QPushButton("Export Markdown")
        self.export_md_btn.setStyleSheet("background-color: #3498db; color: white; font-weight: bold; padding: 6px 15px; border-radius: 4px;")
        self.export_md_btn.clicked.connect(self.export_markdown)
        header_layout.addWidget(self.export_md_btn)
        
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
        
        self.show_bleed_check = QCheckBox("Show Bleed Marks")
        self.show_bleed_check.setChecked(True)
        inspector_layout.addRow("", self.show_bleed_check)
        
        update_preview_btn = QPushButton("Update Preview")
        update_preview_btn.clicked.connect(self.update_preview)
        inspector_layout.addRow("", update_preview_btn)
        
        # Connect controls to auto-update
        self.format_combo.currentTextChanged.connect(self.start_auto_update)
        self.margin_spin.valueChanged.connect(self.start_auto_update)
        self.font_size_spin.valueChanged.connect(self.start_auto_update)
        self.show_bleed_check.toggled.connect(self.start_auto_update)

        splitter.addWidget(inspector_widget)

        # Right Panel: Live Preview Area
        self.preview_frame = QFrame()
        self.preview_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.preview_frame.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        preview_layout = QVBoxLayout(self.preview_frame)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_label = QLabel("Zoom:")
        zoom_layout.addWidget(zoom_label)
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        zoom_layout.addWidget(self.zoom_slider)
        
        self.zoom_label = QLabel("100%")
        zoom_layout.addWidget(self.zoom_label)
        
        fit_width_btn = QPushButton("Fit Width")
        fit_width_btn.clicked.connect(self.fit_to_width)
        zoom_layout.addWidget(fit_width_btn)
        
        zoom_layout.addStretch()
        preview_layout.addLayout(zoom_layout)
        
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
        # Stop auto-update after rendering
        self.update_timer.stop()
        
        if not self.current_book_id:
            return
            
        margin = self.margin_spin.value()
        font_size = self.font_size_spin.value()
        show_bleed = self.show_bleed_check.isChecked()
        
        bleed_style = ""
        if show_bleed:
            bleed_style = f"""
                position: relative;
                border: 2px dashed #e74c3c;
                padding: {margin}mm;
                background: linear-gradient(45deg, #f8f9fa 25%, transparent 25%), 
                            linear-gradient(-45deg, #f8f9fa 25%, transparent 25%), 
                            linear-gradient(45deg, transparent 75%, #f8f9fa 75%), 
                            linear-gradient(-45deg, transparent 75%, #f8f9fa 75%);
                background-size: 20px 20px;
                background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
            """
        else:
            bleed_style = f"margin: {margin}mm; padding: 0;"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{
                    {bleed_style}
                    font-size: {font_size}pt;
                    font-family: serif;
                    line-height: 1.6;
                    color: #2c3e50;
                }}
                .content {{
                    border: 1px solid #bdc3c7;
                    padding: 20px;
                    background-color: white;
                    min-height: 400px;
                }}
                .bleed-mark {{
                    position: absolute;
                    top: -{margin}mm;
                    left: -{margin}mm;
                    right: -{margin}mm;
                    bottom: -{margin}mm;
                    border: 1px solid #e74c3c;
                    pointer-events: none;
                    z-index: -1;
                }}
            </style>
        </head>
        <body>
            {"<div class='bleed-mark'></div>" if show_bleed else ""}
            <div class='content'>
                <h1 style='text-align: center; color: #2c3e50; margin-bottom: 30px;'>Document Preview</h1>
                <p style='text-align: justify; margin-bottom: 20px;'>
                    This live preview shows how your document will appear when exported. 
                    The layout respects {margin}mm margins and {font_size}pt base typography.
                    {"Bleed marks indicate the printable area boundary." if show_bleed else ""}
                </p>
                <p style='text-align: justify;'>
                    When connected to the full rendering pipeline, your actual document content 
                    will be injected here with proper multilingual text shaping and layout.
                </p>
            </div>
        </body>
        </html>
        """
        if WEBENGINE_AVAILABLE and isinstance(self.preview_view, QWebEngineView):
            self.preview_view.setHtml(html_content)

    def start_auto_update(self):
        """Start the auto-update timer for smooth preview updates."""
        if not self.update_timer.isActive():
            self.update_timer.start()

    def update_zoom(self, value):
        """Update the zoom level of the preview."""
        self.zoom_label.setText(f"{value}%")
        if WEBENGINE_AVAILABLE and isinstance(self.preview_view, QWebEngineView):
            self.preview_view.setZoomFactor(value / 100.0)

    def fit_to_width(self):
        """Fit the preview to the available width."""
        # Calculate zoom to fit content width
        # This is a simplified implementation - real fit-to-width would measure content
        available_width = self.preview_frame.width() - 40  # Account for padding
        target_zoom = min(100, (available_width / 800) * 100)  # Assume 800px content width
        self.zoom_slider.setValue(int(target_zoom))
        self.update_zoom(int(target_zoom))

    def export_pdf(self):
        """Trigger the document export pipeline."""
        if not self.current_book_id:
            QMessageBox.warning(self, "Export Error", "No book is loaded to export.")
            return
            
        # Get export settings from UI
        page_format = self.format_combo.currentText()
        margin = self.margin_spin.value()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export PDF",
            "",
            "PDF Files (*.pdf);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            self.status_label.setText("Generating PDF... please wait.")
            QApplication.processEvents()  # Force UI update
            
            # Load document and generate HTML
            document = self.command_bus.document_engine.load_document(self.current_book_id)
            if not document or not document.children:
                raise ValueError("Document has no content to export")
                
            pdf_generator = PDFGenerator()
            html_content = pdf_generator.render_document_html(
                document, 
                title=document.children[0].title if document.children else "Untitled"
            )
            
            # Export to PDF
            output_path = pdf_generator.export_pdf(
                html_content, 
                Path(file_path),
                page_format=page_format,
                margin_mm=margin
            )
            
            self.status_label.setText(f"PDF exported successfully to {output_path.name}")
            QMessageBox.information(
                self, "Export Complete", 
                f"Document exported to PDF:\n{output_path}"
            )
            
        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Export Error", error_msg)

    def export_epub(self):
        """Export document as EPUB."""
        if not self.current_book_id:
            QMessageBox.warning(self, "Export Error", "No book is loaded to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export EPUB", "", "EPUB files (*.epub)"
        )
        if not file_path:
            return
        
        try:
            self.status_label.setText("Generating EPUB... please wait.")
            QApplication.processEvents()  # Force UI update
            
            # Load document and export
            document = self.command_bus.document_engine.load_document(self.current_book_id)
            if not document or not document.children:
                raise ValueError("Document has no content to export")
                
            from modules.export.pdf_generator import PDFGenerator
            generator = PDFGenerator()
            output_path = generator.export_epub(
                document, 
                Path(file_path), 
                title=document.children[0].title if document.children else "Untitled"
            )
            
            self.status_label.setText(f"EPUB exported successfully to {output_path.name}")
            QMessageBox.information(self, "Export Complete", f"EPUB exported to {output_path}")
        except Exception as e:
            error_msg = f"EPUB export failed: {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Export Error", error_msg)

    def export_markdown(self):
        """Export document as Markdown."""
        if not self.current_book_id:
            QMessageBox.warning(self, "Export Error", "No book is loaded to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Markdown", "", "Markdown files (*.md)"
        )
        if not file_path:
            return
        
        try:
            self.status_label.setText("Generating Markdown... please wait.")
            QApplication.processEvents()  # Force UI update
            
            # Load document and export
            document = self.command_bus.document_engine.load_document(self.current_book_id)
            if not document or not document.children:
                raise ValueError("Document has no content to export")
                
            from modules.export.pdf_generator import PDFGenerator
            generator = PDFGenerator()
            output_path = generator.export_markdown(document, Path(file_path))
            
            self.status_label.setText(f"Markdown exported successfully to {output_path.name}")
            QMessageBox.information(self, "Export Complete", f"Markdown exported to {output_path}")
        except Exception as e:
            error_msg = f"Markdown export failed: {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Export Error", error_msg)
