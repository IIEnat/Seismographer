# tests/conftest.py
import os
import sys
import pytest

# Ensure the parent directory (the one containing app.py) is on sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app as flask_app  # now works

@pytest.fixture
def app():
    flask_app.config.update(TESTING=True)
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()
