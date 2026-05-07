import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication, QListWidgetItem

from apps.desktop.ui.sync_mode import SyncModeWidget

@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication instance exists for PyQt6 UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

@pytest.fixture
def sync_widget(qapp, tmp_path):
    """Initialize SyncModeWidget with mocked database, engine, and audio dependencies."""
    with (
        patch('apps.desktop.ui.sync_mode.load_config') as mock_load_config,
        patch('apps.desktop.ui.sync_mode.DatabaseManager') as mock_db_manager,
        patch('apps.desktop.ui.sync_mode.DocumentEngine') as mock_document_engine,
        patch('apps.desktop.ui.sync_mode.AudioProcessor') as mock_audio_processor,
        patch('apps.desktop.ui.sync_mode.WEBENGINE_AVAILABLE', False),
    ):
        # Isolate from actual database writes and audio backends during tests
        mock_config = MagicMock()
        mock_config.db_path = tmp_path / "test_maktaba.db"
        mock_load_config.return_value = mock_config
        mock_db_manager.return_value = MagicMock()
        mock_document_engine.return_value = MagicMock()
        mock_audio_processor.return_value = MagicMock()

        mock_bus = MagicMock()
        widget = SyncModeWidget(mock_bus)
        return widget

def test_sync_populate_word_list_enforces_schema(sync_widget):
    """Ensures that the UI correctly parses the strict Document Schema (Law 2)."""
    class MockBundle:
        def __init__(self, id, ar, en):
            self.id = id
            self.ar = ar
            self.en = en
            self.ur = ""
            
    class MockBlock:
        def __init__(self, bundles):
            self.content = bundles  # Adheres to interlinear_block -> content -> word_bundle

    class MockChapter:
        def __init__(self, title, blocks):
            self.title = title
            self.children = blocks

    bundles = [
        MockBundle("word_1", "بِسْمِ", "In the name"),
        MockBundle("word_2", "ٱللَّهِ", "of Allah"),
    ]
    chapter = MockChapter("Test Chapter", [MockBlock(bundles)])
    
    sync_widget._populate_word_list(chapter)
    
    assert len(sync_widget.word_nodes) == 2
    assert sync_widget.word_nodes[0] == "word_1"
    assert sync_widget.word_nodes[1] == "word_2"
    assert sync_widget.word_list.count() == 2

def test_sync_mark_current_word_accuracy(sync_widget):
    """Tests the spacebar timestamp mapping logic against audio timeline progression."""
    sync_widget.word_nodes = ["word_1", "word_2"]
    sync_widget.word_list.addItem(QListWidgetItem("word 1"))
    sync_widget.word_list.addItem(QListWidgetItem("word 2"))
    
    sync_widget.current_word_index = 0
    sync_widget.current_position = 1.25  # Simulate audio playing at 1.25s
    
    # Simulate first spacebar press
    sync_widget.mark_current_word()
    assert "word_1" in sync_widget.timestamps
    assert sync_widget.timestamps["word_1"] == 1.25
    assert sync_widget.current_word_index == 1
    
    # Simulate audio progression and second spacebar press
    sync_widget.current_position = 2.40
    sync_widget.mark_current_word()
    
    assert "word_2" in sync_widget.timestamps
    assert sync_widget.timestamps["word_2"] == 2.40
    assert sync_widget.current_word_index == 2