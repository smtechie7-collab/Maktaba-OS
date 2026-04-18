import sqlite3
import json
import os
import sys
from typing import Dict, Any, List, Optional

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.logger import setup_logger

logger = setup_logger("Database")

class DatabaseManager:
    def __init__(self, db_path: str = "maktaba.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the database with the required tables."""
        logger.info(f"Initializing database at {self.db_path}")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Books Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    author TEXT,
                    language TEXT DEFAULT 'en',
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 2. Chapters Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER,
                    title TEXT NOT NULL,
                    sequence_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES Books (id) ON DELETE CASCADE
                )
            ''')

            # 3. Content_Blocks Table (Hybrid JSON Storage)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Content_Blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id INTEGER,
                    content_type TEXT DEFAULT 'text', -- text, image, audio
                    content_data JSON NOT NULL,      -- Stores Arabic, Urdu, etc. in JSON
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chapter_id) REFERENCES Chapters (id) ON DELETE CASCADE
                )
            ''')

            # 4. Footnotes Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Footnotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    block_id INTEGER,
                    marker TEXT,              -- e.g., "1", "*", "a"
                    content JSON NOT NULL,    -- Multilingual footnote content
                    FOREIGN KEY (block_id) REFERENCES Content_Blocks (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
        logger.info("Database initialization complete.")

    def add_book(self, title: str, author: str = None, language: str = 'en', metadata: Dict = None) -> int:
        """Add a new book to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Books (title, author, language, metadata) VALUES (?, ?, ?, ?)",
                (title, author, language, json.dumps(metadata) if metadata else None)
            )
            return cursor.lastrowid

    def add_chapter(self, book_id: int, title: str, sequence: int) -> int:
        """Add a chapter to a book."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Chapters (book_id, title, sequence_number) VALUES (?, ?, ?)",
                (book_id, title, sequence)
            )
            return cursor.lastrowid

    def add_content_block(self, chapter_id: int, content_data: Dict[str, Any], content_type: str = 'text') -> int:
        """Add a content block (e.g., Arabic text with Urdu translation) in JSON format."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Content_Blocks (chapter_id, content_type, content_data) VALUES (?, ?, ?)",
                (chapter_id, content_type, json.dumps(content_data))
            )
            return cursor.lastrowid

    def add_footnote(self, block_id: int, content: Dict[str, Any], marker: str = None) -> int:
        """Add a footnote linked to a content block."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Footnotes (block_id, marker, content) VALUES (?, ?, ?)",
                (block_id, marker, json.dumps(content))
            )
            return cursor.lastrowid

    def get_book_content(self, book_id: int) -> List[Dict[str, Any]]:
        """Fetch all chapters and content for a specific book optimized to avoid N+1 queries."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Fetch Chapters and Blocks in one go
            query = '''
                SELECT c.id as chapter_id, c.title as chapter_title, 
                       cb.id as block_id, cb.content_data, cb.content_type
                FROM Chapters c
                JOIN Content_Blocks cb ON c.id = cb.chapter_id
                WHERE c.book_id = ? AND cb.is_active = 1
                ORDER BY c.sequence_number ASC, cb.id ASC
            '''
            cursor.execute(query, (book_id,))
            blocks = [dict(row) for row in cursor.fetchall()]
            
            if not blocks:
                return []

            # 2. Fetch all Footnotes for all blocks in this book in ONE query
            block_ids = [b['block_id'] for b in blocks]
            placeholders = ', '.join(['?'] * len(block_ids))
            fn_query = f"SELECT block_id, marker, content FROM Footnotes WHERE block_id IN ({placeholders})"
            cursor.execute(fn_query, block_ids)
            
            # Map footnotes to their blocks
            footnotes_map = {}
            for fn in cursor.fetchall():
                bid = fn['block_id']
                if bid not in footnotes_map:
                    footnotes_map[bid] = []
                footnotes_map[bid].append({
                    "marker": fn['marker'],
                    "content": json.loads(fn['content'])
                })
            
            # 3. Attach footnotes to blocks
            for block in blocks:
                block['footnotes'] = footnotes_map.get(block['block_id'], [])
                
            return blocks

if __name__ == "__main__":
    # Test initialization
    db = DatabaseManager("test_maktaba.db")
    book_id = db.add_book("Test Islamic Book", "Author Name", "ar")
    chap_id = db.add_chapter(book_id, "Introduction", 1)
    db.add_content_block(chap_id, {
        "ar": "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ",
        "ur": "اللہ کے نام سے شروع جو بڑا مہربان نہایت رحم والا ہے",
        "gu": "અલ્લાહના નામથી શરૂ જે ઘણો દયાળુ અને અત્યંત કૃપાળુ છે"
    })
    print(f"Sample data added to test_maktaba.db. Book ID: {book_id}")
