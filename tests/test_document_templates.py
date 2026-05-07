"""
Tests for template-based document generation.
"""

import sqlite3

import pytest

from core.schema.document import DocumentRoot, MultilingualBlock, ParagraphNode
from infrastructure.database.manager import DatabaseManager
from modules.templates import DocumentTemplateManager


@pytest.fixture
def template_manager():
    """Create a template manager with an in-memory database."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", ("author", "hash"))
    conn.commit()
    return DocumentTemplateManager(conn)


def sample_template_spec():
    """Return a reusable multilingual publication template."""
    return {
        "type": "document",
        "children": [
            {
                "type": "chapter",
                "title": "$chapter_title",
                "children": [
                    {
                        "type": "paragraph",
                        "text": "Prepared for $audience."
                    },
                    {
                        "type": "multilingual_block",
                        "block_type": "paragraph",
                        "ar": "$arabic_text",
                        "ur": "$urdu_text",
                        "gu": "$gujarati_text",
                        "en": "$english_text"
                    }
                ]
            }
        ]
    }


def test_create_and_generate_document_from_template(template_manager):
    """Template generation should return a validated DocumentRoot."""
    template = template_manager.create_template(
        name="Khutbah Draft",
        template_spec=sample_template_spec(),
        organization_id=1,
        created_by=1,
    )

    document = template_manager.generate_document(
        template.id,
        {
            "chapter_title": "Mercy",
            "audience": "students",
            "arabic_text": "بسم الله",
            "urdu_text": "شروع اللہ کے نام سے",
            "gujarati_text": "અલ્લાહના નામે",
            "english_text": "In the name of Allah",
        }
    )

    assert isinstance(document, DocumentRoot)
    assert document.children[0].title == "Mercy"
    assert isinstance(document.children[0].children[0], ParagraphNode)
    assert document.children[0].children[0].text == "Prepared for students."
    assert isinstance(document.children[0].children[1], MultilingualBlock)
    assert document.children[0].children[1].en == "In the name of Allah"


def test_template_listing_and_archive(template_manager):
    """Templates should be listable and soft-archivable."""
    first = template_manager.create_template("First", sample_template_spec(), organization_id=1)
    template_manager.create_template("Second", sample_template_spec(), organization_id=2)

    assert [template.name for template in template_manager.list_templates(organization_id=1)] == ["First"]

    assert template_manager.archive_template(first.id) is True
    assert template_manager.list_templates(organization_id=1) == []


def test_invalid_template_spec_is_rejected(template_manager):
    """Invalid root templates should fail before storage."""
    with pytest.raises(ValueError, match="root type"):
        template_manager.create_template(
            name="Broken",
            template_spec={"type": "chapter", "children": []},
        )


def test_generated_document_must_match_schema(template_manager):
    """Template output still has to satisfy the document schema."""
    template = template_manager.create_template(
        name="Invalid Block",
        template_spec={
            "type": "document",
            "children": [
                {
                    "type": "chapter",
                    "title": "Broken",
                    "children": [{"type": "unknown_block", "text": "Nope"}],
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="Schema Validation Failed"):
        template_manager.generate_document(template.id, {})


def test_generate_book_from_template_persists_document(tmp_path):
    """Generated template content should be saveable as a real book."""
    template_db = sqlite3.connect(":memory:")
    template_manager = DocumentTemplateManager(template_db)
    template = template_manager.create_template("Book", sample_template_spec())

    db_manager = DatabaseManager(tmp_path / "library.db")
    book_id = template_manager.generate_book_from_template(
        db_manager=db_manager,
        template_id=template.id,
        context={
            "chapter_title": "Opening",
            "audience": "reviewers",
            "arabic_text": "",
            "urdu_text": "",
            "gujarati_text": "",
            "english_text": "Draft body",
        },
        title="Generated Book",
        author="Template System",
    )

    books = db_manager.list_books()
    document = db_manager.load_document(book_id)

    assert books[0]["title"] == "Generated Book"
    assert document.children[0].title == "Opening"
    assert document.children[0].children[1].en == "Draft body"
