"""
Structured document templates for Maktaba-OS.

Templates are stored as JSON-compatible document specs with placeholder values.
Generation substitutes placeholder context and validates the result through the
canonical DocumentEngine, producing a real DocumentRoot rather than a loose blob.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from string import Template
from typing import Any, Dict, List, Optional

from core.engine.document_engine import DocumentEngine
from core.schema.document import DocumentRoot


@dataclass
class DocumentTemplate:
    """Stored reusable document template."""
    id: int
    organization_id: Optional[int]
    name: str
    description: Optional[str]
    template_spec: Dict[str, Any]
    created_by: Optional[int]
    created_at: datetime
    is_active: bool


class DocumentTemplateManager:
    """Stores templates and generates validated documents from them."""

    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self._ensure_schema()

    def _ensure_schema(self):
        """Ensure template storage schema exists."""
        with self.db:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS DocumentTemplates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER,
                    name TEXT NOT NULL,
                    description TEXT,
                    template_json TEXT NOT NULL,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (created_by) REFERENCES Users(id),
                    UNIQUE(organization_id, name)
                )
            """)

    def create_template(
        self,
        name: str,
        template_spec: Dict[str, Any],
        organization_id: Optional[int] = None,
        description: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> DocumentTemplate:
        """Create and validate a reusable document template."""
        self._validate_template_spec(template_spec)
        with self.db:
            cursor = self.db.execute("""
                INSERT INTO DocumentTemplates
                (organization_id, name, description, template_json, created_by)
                VALUES (?, ?, ?, ?, ?)
            """, (
                organization_id,
                name,
                description,
                json.dumps(template_spec, ensure_ascii=False),
                created_by,
            ))

        return self.get_template(cursor.lastrowid)

    def get_template(self, template_id: int) -> Optional[DocumentTemplate]:
        """Get a template by ID."""
        row = self.db.execute("""
            SELECT id, organization_id, name, description, template_json, created_by, created_at, is_active
            FROM DocumentTemplates
            WHERE id = ?
        """, (template_id,)).fetchone()

        if not row:
            return None

        return DocumentTemplate(
            id=row[0],
            organization_id=row[1],
            name=row[2],
            description=row[3],
            template_spec=json.loads(row[4]),
            created_by=row[5],
            created_at=datetime.fromisoformat(row[6]),
            is_active=bool(row[7]),
        )

    def list_templates(self, organization_id: Optional[int] = None) -> List[DocumentTemplate]:
        """List active templates, optionally scoped to an organization."""
        if organization_id is None:
            cursor = self.db.execute("""
                SELECT id, organization_id, name, description, template_json, created_by, created_at, is_active
                FROM DocumentTemplates
                WHERE is_active = 1
                ORDER BY created_at DESC, id DESC
            """)
        else:
            cursor = self.db.execute("""
                SELECT id, organization_id, name, description, template_json, created_by, created_at, is_active
                FROM DocumentTemplates
                WHERE is_active = 1 AND organization_id = ?
                ORDER BY created_at DESC, id DESC
            """, (organization_id,))

        return [
            DocumentTemplate(
                id=row[0],
                organization_id=row[1],
                name=row[2],
                description=row[3],
                template_spec=json.loads(row[4]),
                created_by=row[5],
                created_at=datetime.fromisoformat(row[6]),
                is_active=bool(row[7]),
            )
            for row in cursor.fetchall()
        ]

    def archive_template(self, template_id: int) -> bool:
        """Soft-delete a template."""
        with self.db:
            cursor = self.db.execute("""
                UPDATE DocumentTemplates
                SET is_active = 0
                WHERE id = ?
            """, (template_id,))
            return cursor.rowcount > 0

    def generate_document(self, template_id: int, context: Dict[str, Any]) -> DocumentRoot:
        """Generate a validated document from a stored template."""
        template = self.get_template(template_id)
        if not template or not template.is_active:
            raise ValueError(f"Active template not found: {template_id}")

        rendered_spec = self.render_template_spec(template.template_spec, context)
        return DocumentEngine.load_from_dict(rendered_spec)

    def generate_book_from_template(
        self,
        db_manager,
        template_id: int,
        context: Dict[str, Any],
        title: str,
        author: Optional[str] = None,
    ) -> int:
        """Create a book and save generated template content into it."""
        document = self.generate_document(template_id, context)
        book_id = db_manager.create_book(title=title, author=author)
        db_manager.save_document(book_id, document)
        return book_id

    def render_template_spec(self, template_spec: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Render placeholder values inside a template spec."""
        rendered = self._render_value(template_spec, context)
        if not isinstance(rendered, dict):
            raise ValueError("Rendered template spec must be a dictionary")
        return rendered

    def _validate_template_spec(self, template_spec: Dict[str, Any]):
        """Validate static template shape before storage."""
        if not isinstance(template_spec, dict):
            raise ValueError("Template spec must be a dictionary")
        if template_spec.get("type") != "document":
            raise ValueError("Template spec root type must be 'document'")
        if "children" not in template_spec or not isinstance(template_spec["children"], list):
            raise ValueError("Template spec must include a children list")

    def _render_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """Recursively render strings inside JSON-compatible values."""
        if isinstance(value, str):
            return Template(value).safe_substitute(context)
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        if isinstance(value, dict):
            return {
                key: self._render_value(item, context)
                for key, item in value.items()
            }
        return value
