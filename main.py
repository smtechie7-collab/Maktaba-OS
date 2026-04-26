import argparse
import os
import sys
import logging

from src.audio.processor import AudioProcessor
from src.core.config import load_config
from src.core.errors import install_global_exception_handler
from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator
from src.ui.dashboard import main as launch_gui
from src.utils.md_exporter import MarkdownExporter


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Maktaba-OS")


def ensure_output_parent(output_path: str):
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def list_books(db: DatabaseManager):
    """List all books in the database."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, author, language FROM Books")
        books = cursor.fetchall()

        print("\nAvailable Books in Maktaba-OS:")
        print("-" * 50)
        for book in books:
            print(
                f"ID: {book['id']} | Title: {book['title']} | "
                f"Author: {book['author']} | Lang: {book['language']}"
            )
        print("-" * 50)


def main():
    install_global_exception_handler()
    config = load_config()
    parser = argparse.ArgumentParser(description="Maktaba-OS: Islamic Digital Publishing Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    subparsers.add_parser("list", help="List all books in the database")

    pdf_parser = subparsers.add_parser("export-pdf", help="Generate a PDF for a specific book")
    pdf_parser.add_argument("--id", type=int, required=True, help="Book ID to export")
    pdf_parser.add_argument(
        "--output",
        type=str,
        default=str(config.output_dir / "book_export.pdf"),
        help="Output PDF path",
    )

    md_parser = subparsers.add_parser("export-md", help="Export a book to Markdown")
    md_parser.add_argument("--id", type=int, required=True, help="Book ID to export")
    md_parser.add_argument(
        "--output",
        type=str,
        default=str(config.output_dir / "book_export.md"),
        help="Output MD path",
    )

    audio_parser = subparsers.add_parser("process-audio", help="Merge and normalize audio files")
    audio_parser.add_argument("--input", nargs="+", required=True, help="List of input audio files")
    audio_parser.add_argument("--output", type=str, required=True, help="Output merged audio path")

    subparsers.add_parser("gui", help="Launch the Maktaba-OS Dashboard")

    args = parser.parse_args()
    db = DatabaseManager(str(config.db_path))

    if args.command == "list":
        list_books(db)
    elif args.command == "export-pdf":
        ensure_output_parent(args.output)
        generator = PDFGenerator()
        generator.generate_pdf(args.id, args.output)
    elif args.command == "export-md":
        ensure_output_parent(args.output)
        exporter = MarkdownExporter()
        exporter.export_book(args.id, args.output)
    elif args.command == "process-audio":
        processor = AudioProcessor()
        processor.process_chapters(args.input, args.output)
    elif args.command == "gui":
        launch_gui()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
