import pytest
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

TEST_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".pytest_cache", "maktaba-test-data"))
os.environ.setdefault("MAKTABA_DATA_DIR", TEST_DATA_DIR)
os.environ.setdefault("MAKTABA_LOG_DIR", os.path.join(TEST_DATA_DIR, "logs"))

@pytest.fixture
def test_db(tmp_path):
    """Fixture for a temporary test database."""
    db_path = tmp_path / "test_maktaba_suite.db"
    
    from src.data.database import DatabaseManager
    db = DatabaseManager(str(db_path))
    yield db
