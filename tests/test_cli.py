from apps.desktop.main import build_parser, export_html
from core.schema.document import ChapterNode, DocumentRoot, MultilingualBlock
from infrastructure.database.manager import DatabaseManager


def test_export_html_writes_document(tmp_path):
    db = DatabaseManager(tmp_path / "cli.db")
    book_id = db.create_book("CLI Export Book", "Author")
    db.save_document(
        book_id,
        DocumentRoot(
            children=[
                ChapterNode(
                    title="Chapter 1",
                    children=[
                        MultilingualBlock(
                            block_type="paragraph",
                            en="Exported text",
                        )
                    ],
                )
            ]
        ),
    )
    output_path = tmp_path / "exports" / "book.html"

    export_html(db, book_id, str(output_path))

    html = output_path.read_text(encoding="utf-8")
    assert "<title>CLI Export Book</title>" in html
    assert "Exported text" in html


def test_cli_parser_supports_ui_flag():
    parser = build_parser()
    args = parser.parse_args(["--ui"])

    assert args.ui is True
    assert args.command is None
