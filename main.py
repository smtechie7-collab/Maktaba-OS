import argparse
import os
import sys
import logging
from src.data.database import DatabaseManager
from src.layout.pdf_generator import PDFGenerator
from src.audio.processor import AudioProcessor
from src.ui.dashboard import main as launch_gui

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Maktaba-OS")

def list_books(db: DatabaseManager):
    """List all books in the database."""
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, author, language FROM Books")
        books = cursor.fetchall()
        
        print("\n📚 Available Books in Maktaba-OS:")
        print("-" * 50)
        for book in books:
            print(f"ID: {book['id']} | Title: {book['title']} | Author: {book['author']} | Lang: {book['language']}")
        print("-" * 50)

def main():
    parser = argparse.ArgumentParser(description="Maktaba-OS: Islamic Digital Publishing Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: list
    subparsers.add_parser("list", help="List all books in the database")

    # Command: export-pdf
    pdf_parser = subparsers.add_parser("export-pdf", help="Generate a PDF for a specific book")
    pdf_parser.add_argument("--id", type=int, required=True, help="Book ID to export")
    pdf_parser.add_argument("--output", type=str, default="output/book_export.pdf", help="Output PDF path")

    # Command: process-audio
    audio_parser = subparsers.add_parser("process-audio", help="Merge and normalize audio files")
    audio_parser.add_argument("--input", nargs="+", required=True, help="List of input audio files")
    audio_parser.add_argument("--output", type=str, required=True, help="Output merged audio path")

    # Command: gui
    subparsers.add_parser("gui", help="Launch the Maktaba-OS Dashboard")

    args = parser.parse_args()

    db = DatabaseManager("maktaba_production.db")

    if args.command == "list":
        list_books(db)

    elif args.command == "export-pdf":
        os.makedirs("output", exist_ok=True)
        generator = PDFGenerator()
        generator.generate_pdf(args.id, args.output)

    elif args.command == "process-audio":
        processor = AudioProcessor()
        processor.process_chapters(args.input, args.output)

    elif args.command == "gui":
        launch_gui()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
