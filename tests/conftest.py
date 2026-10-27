"""Shared pytest fixtures for isolated SmartChunk API and storage tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.storage import SmartChunkStore


@pytest.fixture

def store(tmp_path, monkeypatch) -> SmartChunkStore:
    """Give each test a temporary SQLite store and patch the API's store binding."""
    from backend import main

    isolated_store = SmartChunkStore(tmp_path / "smartchunk-test-data")
    monkeypatch.setattr(main, "STORE", isolated_store)
    return isolated_store


@pytest.fixture

def client(store) -> TestClient:
    """Return a FastAPI TestClient using the isolated temporary store."""
    from backend.main import app

    with TestClient(app) as test_client:
        yield test_client
