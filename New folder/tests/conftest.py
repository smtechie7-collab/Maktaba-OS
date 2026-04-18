import pytest
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def test_db():
    """Fixture for a temporary test database."""
    db_path = "test_maktaba_suite.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    from src.data.database import DatabaseManager
    db = DatabaseManager(db_path)
    yield db
    
    # Cleanup after tests
    if os.path.exists(db_path):
        os.remove(db_path)
