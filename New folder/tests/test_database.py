import pytest
import json

def test_add_book(test_db):
    """Test adding a book to the database."""
    book_id = test_db.add_book("Test Book", "Test Author", "ar", {"category": "Test"})
    assert book_id == 1
    
    with test_db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title, author FROM Books WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        assert row['title'] == "Test Book"
        assert row['author'] == "Test Author"

def test_add_chapter_and_content(test_db):
    """Test chapter and content block insertion."""
    book_id = test_db.add_book("Book 1")
    chap_id = test_db.add_chapter(book_id, "Chapter 1", 1)
    
    content_data = {"ar": "السلام عليكم", "en": "Hello"}
    content_id = test_db.add_content_block(chap_id, content_data)
    
    assert content_id == 1
    
    # Fetch content
    results = test_db.get_book_content(book_id)
    assert len(results) == 1
    assert results[0]['chapter_title'] == "Chapter 1"
    
    # JSON data check
    fetched_data = json.loads(results[0]['content_data'])
    assert fetched_data['ar'] == "السلام عليكم"
    assert fetched_data['en'] == "Hello"

def test_soft_delete(test_db):
    """Verify soft delete functionality (is_active flag)."""
    book_id = test_db.add_book("Delete Test")
    chap_id = test_db.add_chapter(book_id, "Chap", 1)
    test_db.add_content_block(chap_id, {"text": "Will hide this"})
    
    # Deactivate block
    with test_db._get_connection() as conn:
        conn.execute("UPDATE Content_Blocks SET is_active = 0 WHERE chapter_id = ?", (chap_id,))
        conn.commit()
    
    # Should return 0 results because is_active = 0
    results = test_db.get_book_content(book_id)
    assert len(results) == 0
