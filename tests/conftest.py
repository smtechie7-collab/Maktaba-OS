import pytest
import os
import sys
from pathlib import Path

# Ensure the src module is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data.database import DatabaseManager

@pytest.fixture
def temp_db(tmp_path):
    """
    Provides an isolated, temporary SQLite database instance for each test.
    Ensures tests don't corrupt the user's real library.
    """
    db_path = tmp_path / "test_maktaba.db"
    return DatabaseManager(str(db_path))