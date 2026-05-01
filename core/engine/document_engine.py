import json
from typing import Dict, Any, List
from pydantic import ValidationError

from core.schema.document import DocumentRoot


class DocumentEngine:
    """
    The Core Engine responsible for loading, validating, and managing
    the Maktaba-OS Document Model. Enforces Law 1 & Law 2 of the Constitution.
    """

    def __init__(self, db_manager=None):
        self.db_manager = db_manager

    def load_document(self, book_id: int) -> DocumentRoot:
        """Load a document from persistence."""
        if self.db_manager is None:
            raise RuntimeError("Database manager is required to load documents")
        return self.db_manager.load_document(book_id)

    def list_books(self) -> List[Dict[str, Any]]:
        """List all books from persistence."""
        if self.db_manager is None:
            raise RuntimeError("Database manager is required to list books")
        return self.db_manager.list_books()

    def save_document(self, book_id: int, document: DocumentRoot) -> bool:
        """Save a document to persistence."""
        if self.db_manager is None:
            raise RuntimeError("Database manager is required to save documents")
        return self.db_manager.save_document(book_id, document)

    @staticmethod
    def load_from_dict(data: Dict[str, Any]) -> DocumentRoot:
        """
        Validates and loads a raw dictionary into the strict DocumentRoot schema.
        Throws a ValueError if the schema is violated (e.g., missing translation_l3).
        """
        try:
            # model_validate is Pydantic v2's strict validation method
            return DocumentRoot.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Schema Validation Failed. Invalid node structure:\n{e}")

    @staticmethod
    def load_from_json(json_str: str) -> DocumentRoot:
        """
        Parses a JSON string and validates it against the Document schema.
        """
        try:
            data = json.loads(json_str)
            return DocumentEngine.load_from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format. Could not parse string:\n{e}")

    @staticmethod
    def export_to_dict(document: DocumentRoot) -> Dict[str, Any]:
        """
        Serializes the validated document back to a plain dictionary.
        """
        return document.model_dump()

    @staticmethod
    def export_to_json(document: DocumentRoot) -> str:
        """
        Serializes the validated document back to a formatted JSON string.
        """
        return document.model_dump_json(indent=2)

    @staticmethod
    def create_empty_document() -> DocumentRoot:
        """
        Initializes a fresh, empty document root.
        """
        return DocumentRoot(children=[])
