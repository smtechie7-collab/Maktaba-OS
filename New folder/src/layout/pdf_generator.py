import os
import sys
import json
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.data.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger("PDFGenerator")

class PDFGenerator:
    def __init__(self, template_dir="src/layout/templates", db_path="maktaba_production.db"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template("book_template.html")
        self.cover_template = self.env.get_template("cover_template.html")
        self.db = DatabaseManager(db_path)

    def generate_pdf(self, book_id: int, output_path: str, include_cover: bool = True, press_ready: bool = False, styles: dict = None):
        """Fetch book data and generate a PDF with optional custom styles."""
        logger.info(f"Starting PDF generation for Book ID: {book_id} (Press-Ready: {press_ready})")
        
        # Set default styles if none provided
        if not styles:
            styles = {
                "margins": {"top": 20, "bottom": 20, "left": 15, "right": 15, "gutter": 10},
                "fonts": {
                    "arabic": "Amiri", "arabic_size": 24,
                    "urdu": "Jameel Noori Nastaliq", "urdu_size": 20,
                    "gujarati": "Noto Sans Gujarati", "gujarati_size": 16
                },
                "theme_border_image": None
            }

        # 1. Fetch metadata
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, author FROM Books WHERE id = ?", (book_id,))
            book_info = cursor.fetchone()
            
            if not book_info:
                logger.error(f"Book with ID {book_id} not found.")
                return

        # 2. Fetch content optimized
        content_blocks = self.db.get_book_content(book_id)
        
        chapters_data = []
        current_chapter_id = None
        current_chapter_dict = None
        
        for block in content_blocks:
            if block['chapter_id'] != current_chapter_id:
                current_chapter_id = block['chapter_id']
                current_chapter_dict = {
                    "chapter_title": block['chapter_title'],
                    "blocks": []
                }
                chapters_data.append(current_chapter_dict)
            
            current_chapter_dict['blocks'].append({
                "content_data": json.loads(block['content_data']),
                "content_type": block['content_type'],
                "footnotes": block['footnotes']
            })

        # 3. Render Templates
        full_html = ""
        
        # Add a wrapper for press-ready styles
        press_class = "press-ready" if press_ready else ""
        full_html += f'<div class="{press_class}">'

        if include_cover:
            logger.info("Rendering cover page...")
            full_html += self.cover_template.render(
                book_title=book_info['title'],
                author=book_info['author']
            )
            full_html += '<div style="page-break-after: always;"></div>'

        logger.info("Rendering main content...")
        full_html += self.template.render(
            book_title=book_info['title'],
            author=book_info['author'],
            chapters=chapters_data,
            margins=styles.get("margins"),
            fonts=styles.get("fonts"),
            theme_border_image=styles.get("theme_border_image")
        )
        
        full_html += '</div>'

        # 4. Generate PDF
        base_url = os.path.dirname(os.path.abspath(__file__)) + "/templates/"
        # For Press-Ready, we might need to adjust DPI or CMYK handling
        # WeasyPrint handles DPI via resolution parameter in write_pdf
        HTML(string=full_html, base_url=base_url).write_pdf(
            output_path, 
            presentational_hints=True,
            # 300 DPI for press-ready
            zoom=1.0 if not press_ready else 1.0 # WeasyPrint zoom is relative
        )
        
        logger.info(f"PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    gen = PDFGenerator()
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    gen.generate_pdf(1, "output/riyad_as_salihin_sample.pdf")
