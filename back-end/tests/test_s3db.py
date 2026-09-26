"""Tests for s3db.py: the SQLite database kept as one object in S3.

Two apps sharing one FakeS3 behave like two Lambda copies of the server.
No AWS account and no boto3 are needed.
"""

from __future__ import annotations

import io
import sqlite3
import sys

import pytest
from fake_s3 import FakeS3

import s3db
from app import create_app
from db import SCHEMA_PATH

KEY = "db/navigator.db"
PHOTO = "data:image/png;base64,iVBORw0KGgo="
PASSWORD = "secret-pass"


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    # Retries wait a little between tries; tests do not need to
    monkeypatch.setattr(s3db.time, "sleep", lambda _s: None)


def make_app(tmp_path, fake, name):
    folder = tmp_path / name
    folder.mkdir()
    return create_app(
        {
            "DATABASE_PATH": str(folder / "navigator.db"),
            "SECRET_KEY": "test-secret",
            "TESTING": True,
            "S3DB_BUCKET": "bucket",
            "S3DB_CLIENTS": (fake, fake),
        }
    )


def signup(client, email):
    res = client.post(
        "/api/auth/signup", json={"name": "Student", "email": email, "password": PASSWORD}
    )
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def seed_topic(client, headers, subject="Biology"):
    sid = client.post("/api/subjects", json={"name": subject}, headers=headers).get_json()[
        "subject"
    ]["id"]
    tid = client.post(
        "/api/topics", json={"subjectId": sid, "name": "Photosynthesis"}, headers=headers
    ).get_json()["topic"]["id"]
    return sid, tid


def s3_db(fake, tmp_path, key=KEY):
    """Open a copy of the database object stored in the fake S3."""
    path = tmp_path / "inspect.db"
    path.write_bytes(fake.objects[key]["body"])
    conn = sqlite3.connect(path)
    return conn


def once(fake, action):
    """A before_put hook that runs one time only (like one other save)."""

    def hook(_key):
        fake.before_put = None
        action()

    return hook


# --- off by default ---------------------------------------------------------


def test_plain_mode_is_unchanged(tmp_path):
    app = create_app(
        {"DATABASE_PATH": str(tmp_path / "plain.db"), "SECRET_KEY": "test-secret", "TESTING": True}
    )
    assert not isinstance(app.wsgi_app, s3db.ReplayOnConflict)
    assert "DB_SYNC" not in app.config
    assert "boto3" not in sys.modules


# --- creating, reading and refreshing --------------------------------------


def test_fresh_bucket_is_created(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    assert a.get("/api/health").status_code == 200
    assert fake.versions(KEY) == 1
    tables = {r[0] for r in s3_db(fake, tmp_path).execute("SELECT name FROM sqlite_master")}
    assert {"users", "subjects", "topics", "reviews"} <= tables


def test_two_cold_starts_make_one_database(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    b = make_app(tmp_path, fake, "b").test_client()
    # While A is creating the database, B creates it first
    fake.before_put = once(fake, lambda: b.get("/api/health"))
    assert a.get("/api/health").status_code == 200
    assert fake.versions(KEY) == 1
    assert fake.count("put", 412) == 1  # A lost the race, then used B's copy


def test_reads_never_upload(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    headers, _uid = signup(a, "alice@example.com")
    seed_topic(a, headers)
    puts = fake.count("put")

    a.get("/api/subjects", headers=headers)
    a.get("/api/priorities", headers=headers)
    a.get("/api/auth/me", headers=headers)
    a.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    dup = a.post(
        "/api/auth/signup", json={"name": "A", "email": "alice@example.com", "password": PASSWORD}
    )
    assert dup.status_code == 400
    assert fake.count("put") == puts  # nothing changed, so nothing was saved
    assert fake.count("get", 304) >= 5  # and nothing was downloaded again


def test_copy_refreshes_after_another_copy_saves(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    b = make_app(tmp_path, fake, "b").test_client()
    assert b.get("/api/health").status_code == 200  # B now holds a copy
    headers, _uid = signup(a, "alice@example.com")  # A saves a new version
    downloads = fake.count("get", 200)
    puts = fake.count("put")
    me = b.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "alice@example.com"
    assert fake.count("get", 200) == downloads + 1  # B downloaded the new version
    assert fake.count("put") == puts  # and reading it did not save anything


# --- clashes between copies -------------------------------------------------


def test_clash_runs_the_request_again_and_saves_once(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    b = make_app(tmp_path, fake, "b").test_client()
    headers, _uid = signup(a, "alice@example.com")
    _sid, tid = seed_topic(a, headers)
    assert b.get("/api/health").status_code == 200

    # Just before A saves its review, B saves a new student
    bob = {"name": "Bob", "email": "bob@example.com", "password": PASSWORD}
    fake.before_put = once(fake, lambda: b.post("/api/auth/signup", json=bob))
    res = a.post("/api/log-review", json={"topicId": tid}, headers=headers)

    assert res.status_code == 201
    assert res.get_json()["topic"]["reviewCount"] == 1
    assert fake.count("put", 412) == 1  # A's first save was refused, then it ran again
    conn = s3_db(fake, tmp_path)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2  # Bob kept
    assert conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1  # saved once
    assert conn.execute("SELECT review_count FROM topics").fetchone()[0] == 1


def test_too_many_clashes_gives_busy_and_saves_nothing(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    headers, _uid = signup(a, "alice@example.com")
    _sid, tid = seed_topic(a, headers)

    fake.before_put = lambda key: fake.rewrite(key)  # someone always saves first
    res = a.post("/api/log-review", json={"topicId": tid}, headers=headers)
    fake.before_put = None

    assert res.status_code == 503
    assert res.headers["Cache-Control"] == "no-store"
    assert "busy" in res.get_json()["error"]
    assert fake.count("put", 412) == 5
    assert s3_db(fake, tmp_path).execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0
    # The next request downloads a fresh copy and works normally
    assert a.get("/api/subjects", headers=headers).status_code == 200


def test_unclear_save_that_landed_counts_as_saved(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    headers, _uid = signup(a, "alice@example.com")
    _sid, tid = seed_topic(a, headers)

    fake.fail_put = lambda key: (500, True) if key == KEY else None  # saved, reply lost
    res = a.post("/api/log-review", json={"topicId": tid}, headers=headers)
    fake.fail_put = None
    assert res.status_code == 201
    assert s3_db(fake, tmp_path).execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1


def test_failed_save_gives_busy_and_is_not_repeated(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    headers, _uid = signup(a, "alice@example.com")
    _sid, tid = seed_topic(a, headers)
    puts = fake.count("put")

    fake.fail_put = lambda key: (500, False) if key == KEY else None  # not saved
    res = a.post("/api/log-review", json={"topicId": tid}, headers=headers)
    fake.fail_put = None
    assert res.status_code == 503
    assert fake.count("put") == puts + 1  # tried once, not repeated
    assert s3_db(fake, tmp_path).execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0


def test_s3_down_gives_busy(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    fake.fail_get = lambda _key: 500
    res = a.get("/api/health")
    assert res.status_code == 503
    assert fake.count("put") == 0


# --- safety -----------------------------------------------------------------


def test_old_database_is_upgraded_and_saved_once(tmp_path):
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("ALTER TABLE users DROP COLUMN daily_cap")  # like a database from before
    conn.commit()
    conn.close()
    fake = FakeS3()
    fake.seed(KEY, old.read_bytes())

    a = make_app(tmp_path, fake, "a").test_client()
    assert a.get("/api/health").status_code == 200
    assert fake.count("put") == 1  # the new column was saved
    assert a.get("/api/health").status_code == 200
    assert fake.count("put") == 1  # and only once
    columns = {r[1] for r in s3_db(fake, tmp_path).execute("PRAGMA table_info(users)")}
    assert "daily_cap" in columns


def test_deleted_database_is_never_replaced_with_an_empty_one(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    signup(a, "alice@example.com")
    fake.delete_object(Bucket="bucket", Key=KEY)
    puts = fake.count("put")

    b = make_app(tmp_path, fake, "b").test_client()
    res = b.get("/api/health")
    assert res.status_code == 503
    assert fake.count("put") == puts  # the class's data is not wiped


def test_journal_mode_stays_delete(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    signup(a, "alice@example.com")
    mode = s3_db(fake, tmp_path).execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "delete"


# --- photos -----------------------------------------------------------------


def test_photos_are_their_own_s3_objects(tmp_path):
    fake = FakeS3()
    a = make_app(tmp_path, fake, "a").test_client()
    headers, uid = signup(a, "alice@example.com")
    _sid, tid = seed_topic(a, headers)

    res = a.post(
        "/api/log-review",
        json={"topicId": tid, "attachment": PHOTO, "attachmentName": "notes.png"},
        headers=headers,
    )
    assert res.status_code == 201
    assert b"data:image" not in res.data  # the photo is not sent back
    assert fake.count("put", 200, prefix=f"photos/{uid}/") == 1
    assert b"data:image" not in fake.objects[KEY]["body"]  # not inside the database

    listing = a.get("/api/subjects", headers=headers)
    assert b"data:image" not in listing.data
    review = listing.get_json()["subjects"][0]["topics"][0]["reviews"][0]
    assert review["hasAttachment"] is True

    url = f"/api/reviews/{review['id']}/attachment"
    own = a.get(url, headers=headers)
    assert own.status_code == 200
    assert own.get_json()["attachment"] == PHOTO
    other_headers, _ = signup(a, "bob@example.com")
    assert a.get(url, headers=other_headers).status_code == 404
    assert a.get(url).status_code == 401


# --- the reply only goes out after the save --------------------------------


def test_reply_waits_for_the_save(monkeypatch):
    events = []

    class StubStore:
        clashes = 1

        def begin(self):
            events.append("begin")

        def finish(self):
            events.append("finish")
            if self.clashes:
                self.clashes -= 1
                raise s3db._Conflict()

        def discard(self):
            events.append("discard")

    def stub_app(environ, start_response):
        events.append("app:" + environ["wsgi.input"].read().decode())
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"ok"]

    middleware = s3db.ReplayOnConflict(stub_app, StubStore(), attempts=3, max_body=100)
    environ = {"PATH_INFO": "/api/x", "wsgi.input": io.BytesIO(b"hello"), "CONTENT_LENGTH": "5"}
    body = middleware(environ, lambda status, headers: events.append("reply:" + status))

    assert body == [b"ok"]
    assert events == [
        "begin",
        "app:hello",
        "finish",  # clash: run again with the same body
        "begin",
        "app:hello",
        "finish",
        "reply:200 OK",  # sent once, only after the save
    ]
