from __future__ import annotations

from pathlib import Path
import os

import pytest


TEST_DB = Path(__file__).resolve().parent / 'test_federated_learning.db'

# Ensure app.db sees a dedicated SQLite database before any test module imports app.*.
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DB.as_posix()}'


@pytest.fixture(autouse=True)
def clean_test_db():
    TEST_DB.unlink(missing_ok=True)
    from backend.app.db import init_db

    init_db()
    yield
    TEST_DB.unlink(missing_ok=True)



