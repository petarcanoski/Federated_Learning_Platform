from __future__ import annotations

import os

import pytest


os.environ["MONGODB_USE_MOCK"] = "1"
os.environ["MONGODB_DB_NAME"] = "federated_learning_test"
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/federated_learning_test")


@pytest.fixture(autouse=True)
def clean_test_db():
    from backend.app.db import init_db, reset_database

    reset_database()
    init_db()
    yield
    reset_database()



