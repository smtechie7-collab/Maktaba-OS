import pytest
import json

def test_schema_migrations(temp_db):
    """Ensure the database initializes with the latest schema version."""
    with temp_db._get_connection() as conn:
        version = temp_db._schema_version(conn)
        assert version == 6  # Current Schema Version

def test_book_crud(temp_db):
    """Test creating, reading, updating, and deleting a book."""
    book_id = temp_db.add_book(title="Riyad as-Salihin", author="Imam an-Nawawi", language="ar")
    assert book_id is not None
    
    book = temp_db.get_book(book_id)
    assert book["title"] == "Riyad as-Salihin"
    assert book["author"] == "Imam an-Nawawi"
    
    temp_db.update_book(book_id, title="Riyad as-Salihin (Updated)", author="Imam an-Nawawi")
    updated_book = temp_db.get_book(book_id)
    assert updated_book["title"] == "Riyad as-Salihin (Updated)"
    
    temp_db.delete_book(book_id)
    assert temp_db.get_book(book_id) is None

def test_soft_delete_and_history_triggers(temp_db):
    """Verify the 'Sacredness of Data' commandments: updates trigger history, deletes are soft."""
    book_id = temp_db.add_book("Audit Log Test")
    chapter_id = temp_db.add_chapter(book_id, "Chapter 1", 1)
    
    block_id = temp_db.add_content_block(chapter_id, {"ar": "Original Content"})
    
    # Update to trigger the SQLite History AFTER UPDATE trigger
    temp_db.update_content_block(block_id, {"ar": "Modified Content"})
    
    with temp_db._get_connection() as conn:
        # 1. Verify history was archived
        history = conn.execute("SELECT content_data FROM Content_Blocks_History WHERE block_id = ?", (block_id,)).fetchall()
        assert len(history) == 1
        archived_data = json.loads(history[0]["content_data"])
        assert archived_data["ar"] == "Original Content"
        
        # 2. Verify soft delete works
        temp_db.soft_delete_content_block(block_id)
        block = conn.execute("SELECT is_active FROM Content_Blocks WHERE id = ?", (block_id,)).fetchone()
        assert block["is_active"] == 0

def test_autosave_draft_system(temp_db):
    """Test that background drafts are safely persisted and cleared upon intentional save."""
    book_id = temp_db.add_book("Draft Test")
    chapter_id = temp_db.add_chapter(book_id, "Draft Chapter", 1)
    block_id = temp_db.add_content_block(chapter_id, {"ar": "Saved Block"})
    
    draft_data = {"ar": "Unsaved edits... user computer crashes now!"}
    temp_db.save_draft(book_id, chapter_id, block_id, draft_data)
    
    # Recover Draft
    recovered = temp_db.get_draft(book_id, chapter_id, block_id)
    assert recovered is not None
    assert recovered["ar"] == draft_data["ar"]
    
    temp_db.clear_draft(book_id, chapter_id, block_id)
    assert temp_db.get_draft(book_id, chapter_id, block_id) is None