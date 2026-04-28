import os
import sys
import json
import base64
from io import BytesIO
import qrcode
from jinja2 import Environment, FileSystemLoader

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError as exc:
    HTML = None
    CSS = None
    WEASYPRINT_AVAILABLE = False
    WEASYPRINT_IMPORT_ERROR = exc

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.config import load_config
from src.data.database import DatabaseManager
from src.utils.tajweed_parser import TajweedEngine

class PDFGenerator:
    def __init__(self, template_dir=None, db_path=None):
        config = load_config()
        self.template_dir = str(template_dir or config.template_dir)
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.template = self.env.get_template("book_template.html")
        self.db = DatabaseManager(str(db_path or config.db_path))

    def generate_qr_base64(self, data: str) -> str:
        """Generates a QR Code and returns it as a Base64 PNG image string."""
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{img_str}"

    def generate_pdf(self, book_id: int, output_path: str, include_cover: bool = True, press_ready: bool = False, styles: dict = None):
        """Fetch book data and generate a PDF with Press-Ready Bleeds & Auto QR Codes."""
        if not WEASYPRINT_AVAILABLE:
            raise RuntimeError(
                "WeasyPrint is required for PDF export. Install/bundle WeasyPrint and its Windows GTK dependencies."
            ) from WEASYPRINT_IMPORT_ERROR
        
        # Set default styles if none provided
        if not styles:
            styles = {
                "margins": {"top": 20, "bottom": 20, "left": 15, "right": 15, "gutter": 10},
                "fonts": {
                    "arabic": "Amiri", "arabic_size": 24,
                    "urdu": "Jameel Noori Nastaliq", "urdu_size": 20,
                    "gujarati": "Noto Sans Gujarati", "gujarati_size": 16
                },
                "enable_tajweed": True
            }

        # 1. Fetch metadata
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, author, language, metadata FROM Books WHERE id = ?", (book_id,))
            book_info = cursor.fetchone()
            if not book_info: return
            
            book_metadata = {}
            if book_info['metadata']:
                book_metadata = json.loads(book_info['metadata']) if isinstance(book_info['metadata'], str) else book_info['metadata']
                
            is_rtl = book_info['language'] in ['ar', 'ur']
            
            # 1.5 Calculate Advanced Print Geometry (Gutter & Blank Pages)
            m = styles.get("margins", {})
            page_geometry = {
                "top": m.get("top", 20),
                "bottom": m.get("bottom", 20),
                "inside": m.get("left", 15) + m.get("gutter", 10), 
                "outside": m.get("right", 15),
                "chapter_break": "left" if is_rtl else "right"
            }

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
                    "chapter_type": block.get('chapter_type', 'Content Chapter'),
                    "blocks": [],
                    "qr_code_base64": "" # Placeholder for QR
                }
                chapters_data.append(current_chapter_dict)
            
            if block['block_id']:
                content_data = json.loads(block['content_data'])
                if styles.get("enable_tajweed") and content_data.get('ar'):
                    content_data['ar'] = TajweedEngine.apply_html(content_data['ar'])
                    
                current_chapter_dict['blocks'].append({
                    "block_id": block['block_id'],
                    "content_data": content_data,
                    "content_type": block['content_type'],
                    "footnotes": block.get("footnotes", [])
                })

        # 3. Auto Generate QR Codes based on Day/Track metadata
        for chapter in chapters_data:
            day_val = "All"
            track_val = "T1"
            if chapter['blocks']:
                # Get metadata from the first block of the chapter
                first_meta = chapter['blocks'][0].get('content_data', {}).get('metadata', {})
                day_val = first_meta.get('day', 'All').split(' ')[0]
                track_val = first_meta.get('track', 'T1')
            
            # Simulated Audio Link (Can be mapped to your YouTube/Cloud links later)
            audio_link = f"https://dalail-audio.maktaba.local/listen?book={book_id}&day={day_val}&track={track_val}"
            chapter['qr_code_base64'] = self.generate_qr_base64(audio_link)

        # 4. Render Templates
        full_html = self.template.render(
            book_title=book_info['title'],
            author=book_info['author'],
            book_metadata=book_metadata,
            chapters=chapters_data,
            margins=styles.get("margins"),
            page_geometry=page_geometry,
            is_rtl=is_rtl,
            fonts=styles.get("fonts"),
            press_ready=press_ready # Pass press_ready flag to CSS
        )
        
        # 5. Generate PDF
        base_url = self.template_dir
        
        HTML(string=full_html, base_url=base_url).write_pdf(
            output_path, 
            presentational_hints=True,
            zoom=1.0
        )
        print(f"PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    gen = PDFGenerator()
    os.makedirs("output", exist_ok=True)
    gen.generate_pdf(1, "output/dalail_press_ready_test.pdf", press_ready=True)
