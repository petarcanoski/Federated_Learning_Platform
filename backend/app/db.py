from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import mongomock
from mongoengine import connect, disconnect
from mongoengine.connection import get_connection, get_db as _get_db
from pymongo import ReturnDocument

DEFAULT_ALIAS = "default"
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/federated_learning")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "federated_learning")
MONGODB_USE_MOCK = os.getenv("MONGODB_USE_MOCK", "0").lower() in {"1", "true", "yes"}


def _connect_kwargs() -> dict[str, object]:
    kwargs: dict[str, object] = {"alias": DEFAULT_ALIAS, "db": MONGODB_DB_NAME}
    if MONGODB_USE_MOCK or MONGODB_URI.startswith("mongomock://"):
        kwargs["mongo_client_class"] = mongomock.MongoClient
    return kwargs


def connect_db() -> None:
    try:
        _get_db(alias=DEFAULT_ALIAS)
        return
    except Exception:
        pass
    connect(host=MONGODB_URI, **_connect_kwargs())


def reset_database() -> None:
    connect_db()
    get_connection(alias=DEFAULT_ALIAS).drop_database(MONGODB_DB_NAME)


def next_sequence(sequence_name: str) -> int:
    connect_db()
    database = _get_db(alias=DEFAULT_ALIAS)
    result = database.counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(result["value"])


def init_db() -> None:
    connect_db()
    from . import models
    from .bootstrap import ensure_demo_data

    for document in (models.User, models.Hospital, models.Experiment):
        document.ensure_indexes()
    ensure_demo_data()


@contextmanager
def session_scope() -> Generator:
    connect_db()
    database = _get_db(alias=DEFAULT_ALIAS)
    try:
        yield database
    finally:
        pass


def get_db() -> Generator:
    connect_db()
    return _get_db(alias=DEFAULT_ALIAS)


def disconnect_db() -> None:
    disconnect(alias=DEFAULT_ALIAS)

