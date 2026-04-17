import os
import sys
import json

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.data.database import DatabaseManager
from src.utils.logger import setup_logger

logger = setup_logger("MarkdownExporter")

class MarkdownExporter:
    def __init__(self, db_path="maktaba_production.db"):
        self.db = DatabaseManager(db_path)

    def export_book(self, book_id: int, output_path: str):
        """Export book content to a Markdown file."""
        logger.info(f"Starting Markdown export for Book ID: {book_id}")
        
        # 1. Fetch metadata
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, author FROM Books WHERE id = ?", (book_id,))
            book_info = cursor.fetchone()
            
            if not book_info:
                logger.error(f"Book with ID {book_id} not found.")
                return

        # 2. Fetch content
        content_blocks = self.db.get_book_content(book_id)
        
        md_content = f"# {book_info['title']}\n"
        md_content += f"**Author:** {book_info['author']}\n\n"
        md_content += "---\n\n"

        current_chapter = None
        for block in content_blocks:
            if block['chapter_title'] != current_chapter:
                current_chapter = block['chapter_title']
                md_content += f"## {current_chapter}\n\n"
            
            data = json.loads(block['content_data'])
            
            if 'ar' in data:
                md_content += f"**Arabic:** {data['ar']}\n\n"
            if 'ur' in data:
                md_content += f"**Urdu:** {data['ur']}\n\n"
            if 'en' in data:
                md_content += f"**English:** {data['en']}\n\n"
            
            # Add footnotes if any
            if block.get('footnotes'):
                md_content += "**Footnotes:**\n"
                for fn in block['footnotes']:
                    marker = fn['marker'] if fn['marker'] else "*"
                    fn_data = fn['content']
                    md_content += f"- [{marker}] "
                    if 'ar' in fn_data: md_content += f"(AR) {fn_data['ar']} "
                    if 'ur' in fn_data: md_content += f"(UR) {fn_data['ur']} "
                    md_content += "\n"
                md_content += "\n"

            md_content += "---\n\n"

        # 3. Save to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        logger.info(f"Markdown successfully exported to: {output_path}")

if __name__ == "__main__":
    exporter = MarkdownExporter()
    exporter.export_book(2, "output/book_export.md")
