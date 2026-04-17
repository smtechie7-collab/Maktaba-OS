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
    def __init__(self, template_dir="src/layout/templates"):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template("book_template.html")
        self.db = DatabaseManager("maktaba_production.db")

    def generate_pdf(self, book_id: int, output_path: str):
        """Fetch book data and generate a PDF."""
        logger.info(f"Starting PDF generation for Book ID: {book_id}")
        
        # 1. Fetch metadata
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, author FROM Books WHERE id = ?", (book_id,))
            book_info = cursor.fetchone()
            
            if not book_info:
                logger.error(f"Book with ID {book_id} not found.")
                return

        # 2. Fetch content using the centralized DatabaseManager method
        content_blocks = self.db.get_book_content(book_id)
        
        # Group blocks by chapter for the template
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

        # 3. Render HTML
        html_content = self.template.render(
            book_title=book_info['title'],
            author=book_info['author'],
            chapters=chapters_data
        )

        # 4. Generate PDF
        # WeasyPrint needs the base_url to find the CSS file
        base_url = os.path.dirname(os.path.abspath(__file__)) + "/templates/"
        HTML(string=html_content, base_url=base_url).write_pdf(output_path)
        
        logger.info(f"PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    gen = PDFGenerator()
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    gen.generate_pdf(1, "output/riyad_as_salihin_sample.pdf")
