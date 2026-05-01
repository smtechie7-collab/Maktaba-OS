import pytest
from pathlib import Path

from infrastructure.database.manager import DatabaseManager

@pytest.fixture
def temp_db(tmp_path):
    """
    Provides an isolated, temporary SQLite database instance for each test.
    Ensures tests don't corrupt the user's real library.
    """
    db_path = tmp_path / "test_maktaba.db"
    return DatabaseManager(db_path)
