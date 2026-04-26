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

def test_database_uses_wal_and_migrations(test_db):
    """Verify production pragmas and schema migration tracking are active."""
    with test_db._get_connection() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert foreign_keys == 1
    assert version == test_db.CURRENT_SCHEMA_VERSION

def test_chapter_type_migration_column_exists(test_db):
    """The chapter_type schema change must be applied by a named migration."""
    with test_db._get_connection() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(Chapters)").fetchall()]

    assert "chapter_type" in columns

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
    
    # Empty chapters are preserved for the editor tree, but inactive blocks are hidden.
    results = test_db.get_book_content(book_id)
    assert len(results) == 1
    assert results[0]["block_id"] is None

def test_book_update_and_delete(test_db):
    book_id = test_db.add_book("Draft", "Author", "en")
    test_db.update_book(book_id, "Final", "Editor", "multi")

    book = test_db.get_book(book_id)
    assert book["title"] == "Final"
    assert book["author"] == "Editor"
    assert book["language"] == "multi"

    test_db.delete_book(book_id)
    assert test_db.get_book(book_id) is None

def test_chapter_update_delete_and_move(test_db):
    book_id = test_db.add_book("Book")
    first = test_db.add_chapter(book_id, "First", 1)
    second = test_db.add_chapter(book_id, "Second", 2)

    test_db.update_chapter(first, "Opening", 1, "Title Page")
    assert test_db.get_chapter(first)["title"] == "Opening"

    test_db.move_chapter(second, -1)
    chapters = test_db.list_chapters(book_id)
    assert [chapter["id"] for chapter in chapters] == [second, first]

    test_db.delete_chapter(first)
    chapters = test_db.list_chapters(book_id)
    assert [chapter["id"] for chapter in chapters] == [second]

def test_block_duplicate_soft_delete_and_move(test_db):
    book_id = test_db.add_book("Book")
    chap_id = test_db.add_chapter(book_id, "Chapter", 1)
    first = test_db.add_content_block(chap_id, {"en": "First"})
    second = test_db.add_content_block(chap_id, {"en": "Second"})

    test_db.move_content_block(second, -1)
    content = [row for row in test_db.get_book_content(book_id) if row["block_id"]]
    assert [row["block_id"] for row in content] == [second, first]

    duplicate = test_db.duplicate_content_block(second)
    assert duplicate is not None
    test_db.soft_delete_content_block(second)

    content = [row for row in test_db.get_book_content(book_id) if row["block_id"]]
    assert [row["block_id"] for row in content] == [first, duplicate]
