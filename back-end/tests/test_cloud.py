"""Tests for the cloud-readiness fixes (normal database file, no S3)."""

from __future__ import annotations

import sqlite3

import pytest

from app import create_app

PHOTO = "data:image/png;base64,iVBORw0KGgo="
STRONG_KEY = "k" * 64


def _topic(client, headers):
    sid = client.post("/api/subjects", json={"name": "Biology"}, headers=headers).get_json()[
        "subject"
    ]["id"]
    return client.post(
        "/api/topics", json={"subjectId": sid, "name": "Cells"}, headers=headers
    ).get_json()["topic"]["id"]


# --- Fix 1: photos are not sent in the list --------------------------------


def test_list_has_no_photo_data(client, auth_headers):
    tid = _topic(client, auth_headers)
    res = client.post(
        "/api/log-review", json={"topicId": tid, "attachment": PHOTO}, headers=auth_headers
    )
    assert res.status_code == 201
    assert b"data:image" not in res.data  # log-review does not send the photo back

    listing = client.get("/api/subjects", headers=auth_headers)
    assert b"data:image" not in listing.data
    review = listing.get_json()["subjects"][0]["topics"][0]["reviews"][0]
    assert review["id"]
    assert review["hasAttachment"] is True


def test_photo_is_only_for_its_owner(client, auth_headers):
    tid = _topic(client, auth_headers)
    client.post("/api/log-review", json={"topicId": tid, "attachment": PHOTO}, headers=auth_headers)
    review = client.get("/api/subjects", headers=auth_headers).get_json()["subjects"][0]["topics"][
        0
    ]["reviews"][0]
    url = f"/api/reviews/{review['id']}/attachment"

    own = client.get(url, headers=auth_headers)
    assert own.status_code == 200
    assert own.get_json()["attachment"] == PHOTO

    other = client.post(
        "/api/auth/signup",
        json={"name": "B", "email": "photo-b@example.com", "password": "secret-pass"},
    ).get_json()
    assert client.get(url, headers={"Authorization": f"Bearer {other['token']}"}).status_code == 404
    assert client.get(url).status_code == 401


def test_review_without_photo_has_no_attachment_route(client, auth_headers):
    tid = _topic(client, auth_headers)
    client.post("/api/log-review", json={"topicId": tid}, headers=auth_headers)
    review = client.get("/api/subjects", headers=auth_headers).get_json()["subjects"][0]["topics"][
        0
    ]["reviews"][0]
    assert review["hasAttachment"] is False
    assert client.get(f"/api/reviews/{review['id']}/attachment", headers=auth_headers).status_code == 404


# --- Fix 2: the dev secret key is refused in the cloud ---------------------


def test_production_refuses_the_dev_secret_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-insecure-change-me")
    with pytest.raises(RuntimeError):
        create_app({"DATABASE_PATH": str(tmp_path / "x.db")})
    with pytest.raises(RuntimeError):
        create_app({"DATABASE_PATH": str(tmp_path / "x.db"), "SECRET_KEY": "short"})
    app = create_app({"DATABASE_PATH": str(tmp_path / "x.db"), "SECRET_KEY": STRONG_KEY})
    assert app.config["SECRET_KEY"] == STRONG_KEY


def test_lambda_refuses_a_database_that_would_be_wiped(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "nrn-api")
    monkeypatch.delenv("S3DB_BUCKET", raising=False)
    with pytest.raises(RuntimeError):
        create_app({"DATABASE_PATH": str(tmp_path / "x.db"), "SECRET_KEY": STRONG_KEY})
    # A mounted file system is allowed (create_app does not open the file)
    create_app({"DATABASE_PATH": "/mnt/data/navigator.db", "SECRET_KEY": STRONG_KEY})


def test_local_development_still_works_with_the_dev_key(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    create_app({"DATABASE_PATH": str(tmp_path / "x.db"), "SECRET_KEY": "dev-insecure-change-me"})


# --- Fix 5a: API answers are never cached ----------------------------------


def test_api_answers_are_not_cached(client, auth_headers):
    assert client.get("/api/health").headers["Cache-Control"] == "no-store"
    assert client.get("/api/auth/me", headers=auth_headers).headers["Cache-Control"] == "no-store"


# --- health really checks the database ------------------------------------


def test_health_fails_without_a_database(tmp_path):
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()  # a file with no tables
    app = create_app({"DATABASE_PATH": str(empty), "SECRET_KEY": "test-secret", "TESTING": True})
    res = app.test_client().get("/api/health")
    assert res.status_code == 503
    assert res.get_json()["error"] == "Database unavailable."


# --- upload size limit -----------------------------------------------------


def test_too_big_upload_is_413_json(client, auth_headers):
    big = "data:image/png;base64," + "A" * (3 * 1024 * 1024)
    res = client.post("/api/log-review", json={"topicId": 1, "attachment": big}, headers=auth_headers)
    assert res.status_code == 413
    assert res.get_json()["error"] == "That upload is too big."


# --- extra: minimum password 8, no emails in logs --------------------------


def test_password_needs_eight_characters(client):
    short = client.post(
        "/api/auth/signup", json={"name": "A", "email": "short@example.com", "password": "1234567"}
    )
    assert short.status_code == 400
    assert "8 characters" in short.get_json()["error"]
    ok = client.post(
        "/api/auth/signup", json={"name": "A", "email": "eight@example.com", "password": "12345678"}
    )
    assert ok.status_code == 201


def test_logs_do_not_contain_emails(client, capsys):
    client.post(
        "/api/auth/signup",
        json={"name": "A", "email": "private@example.com", "password": "secret-pass"},
    )
    client.post("/api/auth/login", json={"email": "private@example.com", "password": "secret-pass"})
    assert "private@example.com" not in capsys.readouterr().out
