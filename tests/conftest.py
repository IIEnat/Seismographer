import os
import sys
import pytest

# Add the `main` directory (where app.py lives) to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main"))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app as flask_app  # should now work

@pytest.fixture
def app():
    flask_app.config.update(TESTING=True)
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()
