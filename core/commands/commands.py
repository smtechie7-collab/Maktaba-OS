"""
Command pattern implementation for Maktaba-OS.
All UI interactions flow through commands to maintain separation of concerns.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from core.schema.document import DocumentRoot
from infrastructure.database.manager import DatabaseManager
from core.engine.document_engine import DocumentEngine


@dataclass
class CommandResult:
    """Result of executing a command."""
    success: bool
    data: Any = None
    error_message: Optional[str] = None


class Command(ABC):
    """Base class for all commands in the system."""

    def __init__(self, document_engine: DocumentEngine):
        self.document_engine = document_engine
        self._executed = False
        self._undo_data: Optional[Any] = None

    @abstractmethod
    def execute(self) -> CommandResult:
        """Execute the command."""
        pass

    @abstractmethod
    def undo(self) -> CommandResult:
        """Undo the command if possible."""
        pass

    def can_undo(self) -> bool:
        """Check if this command can be undone."""
        return self._executed and getattr(self, "_original_document", None) is not None


class CreateBookCommand(Command):
    """Command to create a new book's metadata entry."""

    def __init__(self, document_engine: DocumentEngine, title: str, author: Optional[str] = None):
        super().__init__(document_engine)
        self.title = title
        self.author = author
        self._book_id: Optional[int] = None

    def execute(self) -> CommandResult:
        """Execute the command."""
        if self._executed:
            return CommandResult(False, error_message="Command already executed")

        try:
            # The command, as part of the application layer, is allowed to orchestrate
            # lower-level components via the engine.
            db_manager: DatabaseManager = self.document_engine.db_manager
            self._book_id = db_manager.create_book(title=self.title, author=self.author)
            self._executed = True
            return CommandResult(True, data={'book_id': self._book_id})
        except Exception as e:
            return CommandResult(False, error_message=f"Failed to create book: {e}")

    def undo(self) -> CommandResult:
        """Undo the command by deleting the created book."""
        if not self.can_undo():
            return CommandResult(False, error_message="Cannot undo: command not executed or book_id not set.")

        try:
            db_manager: DatabaseManager = self.document_engine.db_manager
            db_manager.delete_book(self._book_id)
            self._executed = False
            return CommandResult(True)
        except Exception as e:
            return CommandResult(False, error_message=f"Failed to undo create book: {e}")

    def can_undo(self) -> bool:
        return self._executed and self._book_id is not None


class DocumentCommand(Command):
    """Base class for commands that modify documents."""

    def __init__(self, document_engine: DocumentEngine, book_id: int):
        super().__init__(document_engine)
        self.book_id = book_id
        self._original_document: Optional[DocumentRoot] = None

    def _load_document(self) -> Optional[DocumentRoot]:
        """Load the current document state."""
        return self.document_engine.load_document(self.book_id)

    def _save_document(self, document: DocumentRoot) -> bool:
        """Save the modified document."""
        return self.document_engine.save_document(self.book_id, document)

    def execute(self) -> CommandResult:
        """Execute with document state preservation."""
        if self._executed:
            return CommandResult(False, error_message="Command already executed")

        self._original_document = self._load_document()
        if self._original_document is None:
            return CommandResult(False, error_message="Document not found")

        result = self._execute_document_command()
        if result.success:
            self._executed = True

        return result

    def undo(self) -> CommandResult:
        """Restore original document state."""
        if not self.can_undo():
            return CommandResult(False, error_message="Cannot undo this command")

        if self._original_document and self._save_document(self._original_document):
            self._executed = False
            return CommandResult(True)
        else:
            return CommandResult(False, error_message="Failed to restore document")

    @abstractmethod
    def _execute_document_command(self) -> CommandResult:
        """Implement the specific document modification."""
        pass

    def _parse_path(self, path: str) -> List[int]:
        """Parse a document path such as root/0/2 into child indexes."""
        if path in ("", "root", "/"):
            return []

        normalized = path.replace(".", "/").strip("/")
        if normalized.startswith("root/"):
            normalized = normalized[5:]

        try:
            return [int(part) for part in normalized.split("/") if part != ""]
        except ValueError as exc:
            raise ValueError(f"Invalid document path '{path}'") from exc

    def _get_children_at_path(self, document: DocumentRoot, path: str):
        indexes = self._parse_path(path)
        node = document
        for index in indexes:
            children = getattr(node, "children", None)
            if children is None:
                raise ValueError(f"Path '{path}' points through a leaf node")
            node = children[index]

        children = getattr(node, "children", None)
        if children is None:
            raise ValueError(f"Path '{path}' does not refer to a node with children")
        return children

    def _get_node_at_path(self, document: DocumentRoot, path: str):
        indexes = self._parse_path(path)
        node = document
        for index in indexes:
            children = getattr(node, "children", None)
            if children is None:
                raise ValueError(f"Path '{path}' points through a leaf node")
            node = children[index]
        return node

    def _path_from_indexes(self, indexes: List[int]) -> str:
        if not indexes:
            return "root"
        return "root/" + "/".join(str(index) for index in indexes)


class ReplaceDocumentCommand(DocumentCommand):
    """Command to replace a book's full document with a validated document."""

    def __init__(self, document_engine: DocumentEngine, book_id: int, document_data: Dict[str, Any]):
        super().__init__(document_engine, book_id)
        self.document_data = document_data

    def _execute_document_command(self) -> CommandResult:
        try:
            new_document = self.document_engine.load_from_dict(self.document_data)
            if not self._save_document(new_document):
                return CommandResult(False, error_message="Failed to save document")
            return CommandResult(True, data=new_document)
        except Exception as e:
            return CommandResult(False, error_message=str(e))


class InsertNodeCommand(DocumentCommand):
    """Command to insert a new node into the document."""

    def __init__(
        self,
        document_engine: DocumentEngine,
        book_id: int,
        node_data: Dict[str, Any],
        parent_path: str,
        index: Optional[int] = None,
    ):
        super().__init__(document_engine, book_id)
        self.node_data = node_data
        self.parent_path = parent_path
        self.index = index

    def _execute_document_command(self) -> CommandResult:
        """Insert the node at the specified location."""
        try:
            document = self._load_document()
            if document is None:
                return CommandResult(False, error_message="Document not found")

            children = self._get_children_at_path(document, self.parent_path)
            node_type = self.node_data.get("type")
            if node_type == "chapter":
                candidate = DocumentRoot(children=[self.node_data]).children[0]
            else:
                candidate = DocumentRoot(
                    children=[
                        {
                            "type": "chapter",
                            "title": "_validation_wrapper",
                            "children": [self.node_data],
                        }
                    ]
                ).children[0].children[0]

            if self.index is None:
                children.append(candidate)
                inserted_index = len(children) - 1
            else:
                if self.index < 0 or self.index > len(children):
                    return CommandResult(False, error_message="Insert index out of range")
                children.insert(self.index, candidate)
                inserted_index = self.index
            if not self._save_document(document):
                return CommandResult(False, error_message="Failed to save document")
            return CommandResult(
                True,
                data={"inserted": True, "index": inserted_index, "node": candidate},
            )
        except Exception as e:
            return CommandResult(False, error_message=str(e))


class DeleteNodeCommand(DocumentCommand):
    """Command to delete a node from the document."""

    def __init__(self, document_engine: DocumentEngine, book_id: int, node_path: str):
        super().__init__(document_engine, book_id)
        self.node_path = node_path

    def _execute_document_command(self) -> CommandResult:
        """Delete the node at the specified path."""
        try:
            document = self._load_document()
            if document is None:
                return CommandResult(False, error_message="Document not found")

            path_indexes = self._parse_path(self.node_path)
            if not path_indexes:
                return CommandResult(False, error_message="Cannot delete the document root")

            parent_path = self._path_from_indexes(path_indexes[:-1])
            siblings = self._get_children_at_path(document, parent_path)
            deleted = siblings.pop(path_indexes[-1])
            if not self._save_document(document):
                return CommandResult(False, error_message="Failed to save document")

            return CommandResult(True, data={"deleted": True, "node": deleted})
        except Exception as e:
            return CommandResult(False, error_message=str(e))


class MoveNodeCommand(DocumentCommand):
    """Command to move a child node within the same parent."""

    def __init__(self, document_engine: DocumentEngine, book_id: int, parent_path: str, source_index: int, target_index: int):
        super().__init__(document_engine, book_id)
        self.parent_path = parent_path
        self.source_index = source_index
        self.target_index = target_index

    def _execute_document_command(self) -> CommandResult:
        try:
            document = self._load_document()
            if document is None:
                return CommandResult(False, error_message="Document not found")

            siblings = self._get_children_at_path(document, self.parent_path)
            if self.source_index < 0 or self.source_index >= len(siblings):
                return CommandResult(False, error_message="Move source index out of range")
            if self.target_index < 0 or self.target_index >= len(siblings):
                return CommandResult(False, error_message="Move target index out of range")

            node = siblings.pop(self.source_index)
            siblings.insert(self.target_index, node)
            if not self._save_document(document):
                return CommandResult(False, error_message="Failed to save document")
            return CommandResult(
                True,
                data={
                    "moved": True,
                    "source_index": self.source_index,
                    "target_index": self.target_index,
                    "node": node,
                },
            )
        except Exception as e:
            return CommandResult(False, error_message=str(e))


class ReplaceTextCommand(DocumentCommand):
    """Command to replace text across document nodes."""

    def __init__(self, document_engine: DocumentEngine, book_id: int, query: str, replacement: str, root_path: str = "root"):
        super().__init__(document_engine, book_id)
        self.query = query
        self.replacement = replacement
        self.root_path = root_path

    def _execute_document_command(self) -> CommandResult:
        try:
            if not self.query:
                return CommandResult(False, error_message="Search text cannot be empty")

            document = self._load_document()
            if document is None:
                return CommandResult(False, error_message="Document not found")

            root_node = self._get_node_at_path(document, self.root_path)
            data = root_node.model_dump()
            replacements = self._replace_in_data(data)
            if replacements == 0:
                return CommandResult(True, data={"replacements": 0})

            if self.root_path in ("", "root", "/"):
                updated_document = self.document_engine.load_from_dict(data)
                if not self._save_document(updated_document):
                    return CommandResult(False, error_message="Failed to save document")
            else:
                path_indexes = self._parse_path(self.root_path)
                parent_path = self._path_from_indexes(path_indexes[:-1])
                siblings = self._get_children_at_path(document, parent_path)
                if data.get("type") == "chapter":
                    updated_node = DocumentRoot(children=[data]).children[0]
                else:
                    updated_node = DocumentRoot(
                        children=[
                            {
                                "type": "chapter",
                                "title": "_validation_wrapper",
                                "children": [data],
                            }
                        ]
                    ).children[0].children[0]
                siblings[path_indexes[-1]] = updated_node
                if not self._save_document(document):
                    return CommandResult(False, error_message="Failed to save document")

            return CommandResult(True, data={"replacements": replacements})
        except Exception as e:
            return CommandResult(False, error_message=str(e))

    def _replace_in_data(self, value: Any) -> int:
        count = 0
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if isinstance(item, str):
                    next_item = item.replace(self.query, self.replacement)
                    if next_item != item:
                        count += item.count(self.query)
                        value[key] = next_item
                else:
                    count += self._replace_in_data(item)
        elif isinstance(value, list):
            for item in value:
                count += self._replace_in_data(item)
        return count


class UpdateNodeCommand(DocumentCommand):
    """Command to update an existing node in the document."""

    def __init__(self, document_engine: DocumentEngine, book_id: int, node_path: str, updates: Dict[str, Any]):
        super().__init__(document_engine, book_id)
        self.node_path = node_path
        self.updates = updates

    def _execute_document_command(self) -> CommandResult:
        """Update the node with new data."""
        try:
            document = self._load_document()
            if document is None:
                return CommandResult(False, error_message="Document not found")

            node = self._get_node_at_path(document, self.node_path)
            data = node.model_dump()
            data.update(self.updates)

            path_indexes = self._parse_path(self.node_path)
            if not path_indexes:
                updated_document = self.document_engine.load_from_dict(data)
                if not self._save_document(updated_document):
                    return CommandResult(False, error_message="Failed to save document")
                return CommandResult(True, data={"updated": True, "node": updated_document})

            parent_path = self._path_from_indexes(path_indexes[:-1])
            siblings = self._get_children_at_path(document, parent_path)
            if data.get("type") == "chapter":
                updated_node = DocumentRoot(children=[data]).children[0]
            else:
                updated_node = DocumentRoot(
                    children=[
                        {
                            "type": "chapter",
                            "title": "_validation_wrapper",
                            "children": [data],
                        }
                    ]
                ).children[0].children[0]
            siblings[path_indexes[-1]] = updated_node
            if not self._save_document(document):
                return CommandResult(False, error_message="Failed to save document")

            return CommandResult(True, data={"updated": True, "node": updated_node})
        except Exception as e:
            return CommandResult(False, error_message=str(e))
