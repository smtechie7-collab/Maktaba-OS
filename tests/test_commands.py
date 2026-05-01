"""
Tests for the command system.
"""

import pytest
from unittest.mock import Mock

from core.commands.commands import (
    CommandResult, DocumentCommand, InsertNodeCommand,
    DeleteNodeCommand, MoveNodeCommand, ReplaceDocumentCommand,
    ReplaceTextCommand, UpdateNodeCommand
)
from core.commands.command_history import CommandHistory
from core.commands.command_bus import CommandBus
from core.schema.document import DocumentRoot
from infrastructure.database.manager import DatabaseManager


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_success_result(self):
        result = CommandResult(True, data="test")
        assert result.success is True
        assert result.data == "test"
        assert result.error_message is None

    def test_error_result(self):
        result = CommandResult(False, error_message="Error occurred")
        assert result.success is False
        assert result.data is None
        assert result.error_message == "Error occurred"


class TestDocumentCommand:
    """Test DocumentCommand base class."""

    def test_execute_stores_original(self):
        # Mock document engine
        mock_engine = Mock()
        mock_document = DocumentRoot(type="document", children=[])
        mock_engine.load_document.return_value = mock_document

        command = InsertNodeCommand(mock_engine, 1, {"type": "paragraph", "text": "test"}, "root")
        command._execute_document_command = Mock(return_value=CommandResult(True))

        result = command.execute()

        assert result.success is True
        assert command._original_document == mock_document
        assert command._executed is True

    def test_execute_fails_if_already_executed(self):
        mock_engine = Mock()
        command = InsertNodeCommand(mock_engine, 1, {"type": "paragraph", "text": "test"}, "root")
        command._executed = True

        result = command.execute()

        assert result.success is False
        assert "already executed" in result.error_message

    def test_undo_restores_original(self):
        mock_engine = Mock()
        mock_document = DocumentRoot(type="document", children=[])
        mock_engine.load_document.return_value = mock_document
        mock_engine.save_document.return_value = True

        command = InsertNodeCommand(mock_engine, 1, {"type": "paragraph", "text": "test"}, "root")
        command._original_document = mock_document
        command._executed = True

        result = command.undo()

        assert result.success is True
        mock_engine.save_document.assert_called_with(1, mock_document)

    def test_insert_update_delete_mutate_persisted_document(self, tmp_path):
        db = DatabaseManager(tmp_path / "commands.db")
        book_id = db.create_book("Command Book")
        engine = db_engine(db)

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [{"type": "chapter", "title": "Chapter 1", "children": []}],
            },
        )
        assert replace.execute().success is True

        insert = InsertNodeCommand(
            engine,
            book_id,
            {"type": "paragraph", "text": "Original text"},
            "root/0",
        )
        assert insert.execute().success is True
        assert db.load_document(book_id).children[0].children[0].text == "Original text"

        update = UpdateNodeCommand(engine, book_id, "root/0/0", {"text": "Updated text"})
        assert update.execute().success is True
        assert db.load_document(book_id).children[0].children[0].text == "Updated text"

        delete = DeleteNodeCommand(engine, book_id, "root/0/0")
        assert delete.execute().success is True
        assert db.load_document(book_id).children[0].children == []

    def test_insert_node_supports_explicit_position(self, tmp_path):
        db = DatabaseManager(tmp_path / "ordered_commands.db")
        book_id = db.create_book("Ordered Command Book")
        engine = db_engine(db)

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [
                    {
                        "type": "chapter",
                        "title": "Chapter 1",
                        "children": [{"type": "paragraph", "text": "Second"}],
                    }
                ],
            },
        )
        assert replace.execute().success is True

        insert = InsertNodeCommand(
            engine,
            book_id,
            {"type": "paragraph", "text": "First"},
            "root/0",
            index=0,
        )
        result = insert.execute()

        assert result.success is True
        assert result.data["index"] == 0
        children = db.load_document(book_id).children[0].children
        assert [child.text for child in children] == ["First", "Second"]

    def test_insert_node_rejects_out_of_range_position(self, tmp_path):
        db = DatabaseManager(tmp_path / "bad_position_commands.db")
        book_id = db.create_book("Bad Position Command Book")
        engine = db_engine(db)

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [{"type": "chapter", "title": "Chapter 1", "children": []}],
            },
        )
        assert replace.execute().success is True

        insert = InsertNodeCommand(
            engine,
            book_id,
            {"type": "paragraph", "text": "Too far"},
            "root/0",
            index=2,
        )
        result = insert.execute()

        assert result.success is False
        assert "out of range" in result.error_message
        assert db.load_document(book_id).children[0].children == []

    def test_move_node_reorders_children(self, tmp_path):
        db = DatabaseManager(tmp_path / "move_commands.db")
        book_id = db.create_book("Move Command Book")
        engine = db_engine(db)

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [
                    {
                        "type": "chapter",
                        "title": "Chapter 1",
                        "children": [
                            {"type": "paragraph", "text": "First"},
                            {"type": "paragraph", "text": "Second"},
                        ],
                    }
                ],
            },
        )
        assert replace.execute().success is True

        move = MoveNodeCommand(engine, book_id, "root/0", 1, 0)
        result = move.execute()

        assert result.success is True
        children = db.load_document(book_id).children[0].children
        assert [child.text for child in children] == ["Second", "First"]

    def test_replace_text_command_updates_multilingual_blocks(self, tmp_path):
        db = DatabaseManager(tmp_path / "replace_text_commands.db")
        book_id = db.create_book("Replace Text Command Book")
        engine = db_engine(db)

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [
                    {
                        "type": "chapter",
                        "title": "Chapter 1",
                        "children": [
                            {
                                "type": "multilingual_block",
                                "block_type": "paragraph",
                                "ar": "",
                                "ur": "",
                                "gu": "",
                                "en": "old text and old note",
                            }
                        ],
                    }
                ],
            },
        )
        assert replace.execute().success is True

        command = ReplaceTextCommand(engine, book_id, "old", "new", "root/0")
        result = command.execute()

        assert result.success is True
        assert result.data["replacements"] == 2
        block = db.load_document(book_id).children[0].children[0]
        assert block.en == "new text and new note"

    def test_interlinear_block_persists_through_node_commands(self, tmp_path):
        db = DatabaseManager(tmp_path / "interlinear_commands.db")
        book_id = db.create_book("Interlinear Command Book")
        engine = db_engine(db)

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [{"type": "chapter", "title": "Chapter 1", "children": []}],
            },
        )
        assert replace.execute().success is True

        insert = InsertNodeCommand(
            engine,
            book_id,
            {
                "type": "interlinear_block",
                "tokens": [
                    {
                        "source_l1": "بسم",
                        "transliteration_l2": "bsm",
                        "translation_l3": "In",
                    }
                ],
            },
            "root/0",
        )
        assert insert.execute().success is True

        update = UpdateNodeCommand(
            engine,
            book_id,
            "root/0/0",
            {
                "tokens": [
                    {
                        "source_l1": "الله",
                        "transliteration_l2": "allah",
                        "translation_l3": "Allah",
                    }
                ]
            },
        )
        assert update.execute().success is True

        block = db.load_document(book_id).children[0].children[0]
        assert block.type == "interlinear_block"
        assert block.tokens[0].source_l1 == "الله"
        assert block.tokens[0].translation_l3 == "Allah"

    def test_move_and_replace_are_undoable_through_history(self, tmp_path):
        db = DatabaseManager(tmp_path / "history_real_commands.db")
        book_id = db.create_book("History Real Command Book")
        engine = db_engine(db)
        history = CommandHistory()

        replace = ReplaceDocumentCommand(
            engine,
            book_id,
            {
                "type": "document",
                "children": [
                    {
                        "type": "chapter",
                        "title": "Chapter 1",
                        "children": [
                            {"type": "paragraph", "text": "First"},
                            {"type": "paragraph", "text": "Second"},
                        ],
                    }
                ],
            },
        )
        assert replace.execute().success is True

        move = MoveNodeCommand(engine, book_id, "root/0", 1, 0)
        assert history.execute_and_add(move).success is True
        assert [child.text for child in db.load_document(book_id).children[0].children] == ["Second", "First"]

        assert history.undo().success is True
        assert [child.text for child in db.load_document(book_id).children[0].children] == ["First", "Second"]

        assert history.redo().success is True
        assert [child.text for child in db.load_document(book_id).children[0].children] == ["Second", "First"]


class TestCommandHistory:
    """Test CommandHistory functionality."""

    def test_execute_and_add(self):
        history = CommandHistory()

        mock_command = Mock()
        mock_command.execute.return_value = CommandResult(True)
        mock_command.can_undo.return_value = True

        result = history.execute_and_add(mock_command)

        assert result.success is True
        assert history.can_undo() is True
        assert history.can_redo() is False

    def test_undo_redo(self):
        history = CommandHistory()

        mock_command = Mock()
        mock_command.execute.return_value = CommandResult(True)
        mock_command.undo.return_value = CommandResult(True)
        mock_command.can_undo.return_value = True

        # Execute command
        history.execute_and_add(mock_command)
        assert history.can_undo() is True

        # Undo
        result = history.undo()
        assert result.success is True
        assert history.can_undo() is False
        assert history.can_redo() is True

        # Redo
        result = history.redo()
        assert result.success is True
        assert history.can_undo() is True
        assert history.can_redo() is False


class TestCommandBus:
    """Test CommandBus functionality."""

    def test_execute_command_sync(self):
        mock_engine = Mock()
        bus = CommandBus(mock_engine)

        mock_command = Mock()
        mock_command.execute.return_value = CommandResult(True)

        result = bus.execute_command_sync(mock_command)

        assert result.success is True

    def test_async_execution(self):
        mock_engine = Mock()
        bus = CommandBus(mock_engine)
        bus.start()

        mock_command = Mock()
        mock_command.execute.return_value = CommandResult(True)

        callback_called = False
        def callback(result):
            nonlocal callback_called
            callback_called = True
            assert result.success is True

        command_id = bus.execute_command(mock_command, callback)

        # Wait a bit for async processing
        import time
        time.sleep(0.1)

        assert callback_called is True

        bus.stop()


def db_engine(db):
    from core.engine.document_engine import DocumentEngine

    return DocumentEngine(db)
