"""Pytest fixtures — a Flask test client backed by a fresh temp SQLite file."""

from __future__ import annotations

import pytest

import db as db_module
from app import create_app


@pytest.fixture
def app(tmp_path):
    database_path = str(tmp_path / "test.db")
    db_module.init_db(database_path)
    application = create_app(
        {"DATABASE_PATH": database_path, "SECRET_KEY": "test-secret", "TESTING": True}
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(client):
    """Sign up a user and return Authorization headers for them."""
    res = client.post(
        "/api/auth/signup",
        json={
            "name": "Aroha Smith",
            "email": "aroha@example.com",
            "password": "secret",
            "yearLevel": 12,
        },
    )
    token = res.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}
