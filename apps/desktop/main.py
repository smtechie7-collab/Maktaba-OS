import argparse
import logging
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))

# UI import moved to conditional import
from infrastructure.config.app_config import load_config
from infrastructure.database.manager import DatabaseManager
from modules.export import PDFGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Maktaba-OS-Desktop")


def ensure_output_parent(output_path: str):
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def list_books(db: DatabaseManager):
    """List all books in the database using the new manager."""
    books = db.list_books()

    if not books:
        print("\nNo books found in the Maktaba-OS library.")
        print('You can create one using: python main.py create-book --title "My Book"')
        return

    print("\nAvailable Books in Maktaba-OS:")
    print("-" * 70)
    print(f"{'ID':<5} | {'Title':<30} | {'Author':<25}")
    print("-" * 70)
    for book in books:
        print(
            f"{book['id']:<5} | {book['title']:<30} | "
            f"{book.get('author', 'N/A'):<25}"
        )
    print("-" * 70)


def export_html(db: DatabaseManager, book_id: int, output_path: str):
    """Export a stored book document to an HTML file."""
    document = db.load_document(book_id)
    if document is None:
        raise SystemExit(f"No active book found with ID: {book_id}")

    books = {book["id"]: book for book in db.list_books()}
    title = books.get(book_id, {}).get("title", f"Book {book_id}")
    html = PDFGenerator().render_document_html(document, title=title)

    ensure_output_parent(output_path)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Exported HTML for book {book_id} to {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maktaba-OS: Islamic Digital Publishing Engine CLI")
    parser.add_argument("--ui", action="store_true", help="Launch the Maktaba-OS Desktop Application")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("list", help="List all books in the database")

    export_html_parser = subparsers.add_parser("export-html", help="Export a book to HTML")
    export_html_parser.add_argument("--id", type=int, required=True, help="Book ID to export")
    export_html_parser.add_argument("--output", type=str, required=True, help="Output HTML path")

    subparsers.add_parser("export-pdf", help="[DISABLED] Generate a PDF for a specific book")
    subparsers.add_parser("export-md", help="[DISABLED] Export a book to Markdown")
    subparsers.add_parser("process-audio", help="[DISABLED] Merge and normalize audio files")
    subparsers.add_parser("gui", help="Launch the Maktaba-OS Desktop Application")

    create_parser = subparsers.add_parser("create-book", help="Create a new empty book")
    create_parser.add_argument("--title", type=str, required=True, help="Title of the book")
    create_parser.add_argument("--author", type=str, required=False, help="Author of the book")

    return parser


def main():
    config = load_config()
    parser = build_parser()
    args = parser.parse_args()
    db = DatabaseManager(config.db_path)

    if args.command == "list":
        list_books(db)
    elif args.command == "export-html":
        export_html(db, args.id, args.output)
    elif args.command == "create-book":
        book_id = db.create_book(title=args.title, author=args.author)
        print(f"Successfully created book '{args.title}' with ID: {book_id}")
    elif args.command == "gui" or args.ui:
        from apps.desktop.ui.main_window import main as launch_ui
        launch_ui()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
