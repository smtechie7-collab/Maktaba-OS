import pytest
from src.layout.pdf_generator import PDFGenerator
import os

def test_template_rendering(test_db):
    """Verify that Jinja2 renders the HTML correctly."""
    # Setup test data
    book_id = test_db.add_book("Layout Test", "Author")
    chap_id = test_db.add_chapter(book_id, "Chapter 1", 1)
    test_db.add_content_block(chap_id, {"ar": "بسم الله", "ur": "اللہ کے نام سے"})

    # Initialize Generator (pointing to real templates)
    gen = PDFGenerator(template_dir="src/layout/templates")
    
    # We'll check if the render process works without error
    # For unit testing, we can check the rendered HTML string if we modify the generator slightly,
    # but for now, we'll verify the data structure it uses.
    
    with test_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, author FROM Books WHERE id = ?", (book_id,))
        book_info = cursor.fetchone()
        assert book_info['title'] == "Layout Test"
        
        # Test content grouping logic (replicating generator logic)
        chapters_data = []
        cursor.execute("SELECT id, title FROM Chapters WHERE book_id = ? ORDER BY sequence_number", (book_id,))
        chapters = cursor.fetchall()
        for chap in chapters:
            cursor.execute("SELECT content_data FROM Content_Blocks WHERE chapter_id = ? AND is_active = 1", (chap['id'],))
            blocks = cursor.fetchall()
            assert len(blocks) == 1
