import os
import sys
import json

try:
    import ebooklib
    from ebooklib import epub
    EBOOKLIB_AVAILABLE = True
except ImportError as exc:
    EBOOKLIB_AVAILABLE = False
    EBOOKLIB_ERROR = exc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.config import load_config
from src.data.database import DatabaseManager
from src.utils.tajweed_parser import TajweedEngine

class EPUBGenerator:
    def __init__(self, db_path=None):
        config = load_config()
        self.db = DatabaseManager(str(db_path or config.db_path))

    def generate_epub(self, book_id: int, output_path: str, styles: dict = None):
        if not EBOOKLIB_AVAILABLE:
            raise RuntimeError("EbookLib is required for ePub export. Please run 'pip install EbookLib'.")

        if not styles:
            styles = {"enable_tajweed": True}

        # 1. Fetch metadata
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, author, language, metadata FROM Books WHERE id = ?", (book_id,))
            book_info = cursor.fetchone()
            if not book_info: return

        book = epub.EpubBook()
        book.set_identifier(f"maktaba-os-book-{book_id}")
        book.set_title(book_info['title'] or "Untitled Book")
        book.set_language(book_info['language'] or "en")
        
        if book_info['author']:
            book.add_author(book_info['author'])

        # 2. Fetch content
        content_blocks = self.db.get_book_content(book_id)
        chapters_data = []
        current_chapter_id = None
        current_chapter_dict = None
        
        for block in content_blocks:
            if block['chapter_id'] != current_chapter_id:
                current_chapter_id = block['chapter_id']
                current_chapter_dict = {"title": block['chapter_title'], "blocks": []}
                chapters_data.append(current_chapter_dict)
            
            if block['block_id']:
                content_data = json.loads(block['content_data'])
                if styles.get("enable_tajweed") and content_data.get('ar'):
                    content_data['ar'] = TajweedEngine.apply_html(content_data['ar'])
                    
                current_chapter_dict['blocks'].append({
                    "content_data": content_data,
                    "footnotes": block.get("footnotes", [])
                })

        # 3. Create Chapters
        epub_chapters = []
        is_rtl = book_info['language'] in ['ar', 'ur']
        dir_attr = 'dir="rtl"' if is_rtl else 'dir="ltr"'

        for i, chap in enumerate(chapters_data):
            file_name = f"chapter_{i+1}.xhtml"
            c = epub.EpubHtml(title=chap["title"], file_name=file_name, lang=book_info['language'])
            
            html_content = f'''<html xmlns="http://www.w3.org/1999/xhtml" {dir_attr}>
            <head>
                <title>{chap["title"]}</title>
                <style>
                    body {{ font-family: serif; line-height: 1.8; padding: 5%; }}
                    .arabic {{ font-size: 1.8em; text-align: right; margin-bottom: 15px; font-family: "Amiri", serif; direction: rtl; }}
                    .urdu {{ font-size: 1.4em; text-align: right; margin-bottom: 15px; font-family: "Jameel Noori Nastaliq", serif; direction: rtl; }}
                    .gujarati {{ font-size: 1.2em; text-align: left; margin-bottom: 15px; }}
                    .english {{ text-align: left; margin-bottom: 15px; direction: ltr; }}
                    .footnotes {{ font-size: 0.9em; border-top: 1px solid #ccc; margin-top: 20px; padding-top: 10px; color: #555; }}
                    .tajweed {{ font-weight: bold; }}
                </style>
            </head>
            <body>
                <h2>{chap["title"]}</h2>
            '''
            
            for block in chap["blocks"]:
                data = block["content_data"]
                html_content += '<div class="block" style="margin-bottom: 25px;">'
                
                if data.get('ar'): html_content += f'<div class="arabic">{data["ar"]}</div>'
                if data.get('ur'): html_content += f'<div class="urdu">{data["ur"]}</div>'
                if data.get('guj'): html_content += f'<div class="gujarati">{data["guj"]}</div>'
                if data.get('en'): html_content += f'<div class="english">{data["en"]}</div>'
                
                if block.get("footnotes"):
                    html_content += '<div class="footnotes">'
                    for fn in block["footnotes"]:
                        marker = fn.get("marker", "*")
                        fn_content = fn.get("content", {})
                        fn_texts = [v for k, v in fn_content.items() if v]
                        fn_text = " / ".join(fn_texts)
                        html_content += f'<p><sup>{marker}</sup> {fn_text}</p>'
                    html_content += '</div>'
                    
                html_content += '</div>'
            
            html_content += '</body></html>'
            c.content = html_content
            book.add_item(c)
            epub_chapters.append(c)

        # 4. Finalize Structure
        book.toc = tuple(epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav'] + epub_chapters
        
        # 5. Output
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
        epub.write_epub(output_path, book, {})