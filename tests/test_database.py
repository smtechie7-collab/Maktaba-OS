import pytest
from pathlib import Path

from infrastructure.database.manager import DatabaseManager
from core.schema.document import (
    DocumentRoot,
    ChapterNode,
    ParagraphNode,
    InterlinearBlock,
    InterlinearToken
)

@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Provides a fresh DatabaseManager instance using a temporary file."""
    db_path = tmp_path / "test_maktaba.db"
    return DatabaseManager(db_path)

def test_book_creation_and_listing(temp_db: DatabaseManager):
    """Test that creating a book creates metadata and an empty DocumentRoot."""
    book_id = temp_db.create_book(title="Test Book", author="Test Author")
    assert book_id is not None
    
    books = temp_db.list_books()
    assert len(books) == 1
    assert books[0]["title"] == "Test Book"
    assert books[0]["author"] == "Test Author"
    
    # Ensure the new book was initialized with a valid, empty DocumentRoot
    empty_doc = temp_db.load_document(book_id)
    assert isinstance(empty_doc, DocumentRoot)
    assert len(empty_doc.children) == 0

def test_save_and_load_strict_document(temp_db: DatabaseManager):
    """
    Test that the database can successfully store and retrieve a 
    deeply nested, strongly-typed Pydantic document model.
    """
    book_id = temp_db.create_book("Pydantic Test Book")
    
    # 1. Build a strict schema document
    doc = DocumentRoot(
        children=[
            ChapterNode(
                title="Chapter 1",
                children=[
                    ParagraphNode(text="This is a standard paragraph node."),
                    InterlinearBlock(
                        tokens=[
                            InterlinearToken(
                                source_l1="بِسْمِ",
                                transliteration_l2="bismi",
                                translation_l3="In the name"
                            )
                        ]
                    )
                ]
            )
        ]
    )
    
    # 2. Save the document
    assert temp_db.save_document(book_id, doc) is True
    
    # 3. Load and verify types and data integrity
    loaded_doc = temp_db.load_document(book_id)
    assert loaded_doc is not None
    assert len(loaded_doc.children) == 1
    
    chapter = loaded_doc.children[0]
    assert isinstance(chapter, ChapterNode)
    assert chapter.title == "Chapter 1"
    assert len(chapter.children) == 2
    
    interlinear_block = chapter.children[1]
    assert isinstance(interlinear_block, InterlinearBlock)
    assert interlinear_block.tokens[0].source_l1 == "بِسْمِ"

def test_save_document_increments_version(temp_db: DatabaseManager):
    """Saving a document should advance the persisted document version."""
    book_id = temp_db.create_book("Versioned Book")
    original_version = temp_db.get_document_version(book_id)

    doc = DocumentRoot(
        children=[
            ChapterNode(
                title="Chapter 1",
                children=[ParagraphNode(text="Versioned text")],
            )
        ]
    )

    assert temp_db.save_document(book_id, doc) is True
    assert temp_db.get_document_version(book_id) == original_version + 1

def test_save_document_returns_false_for_missing_book(temp_db: DatabaseManager):
    """Saving to a missing book id must report failure instead of silently succeeding."""
    doc = DocumentRoot(children=[])

    assert temp_db.save_document(99999, doc) is False
    assert temp_db.get_document_version(99999) is None

def test_delete_book(temp_db: DatabaseManager):
    """Verify deleting a book removes it and prevents its document from being loaded."""
    book_id = temp_db.create_book("To Be Deleted")
    assert len(temp_db.list_books()) == 1
    
    temp_db.delete_book(book_id)
    assert len(temp_db.list_books()) == 0
    assert temp_db.load_document(book_id) is None
