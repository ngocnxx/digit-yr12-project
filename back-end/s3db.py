"""Keep the SQLite database file in Amazon S3 (only when S3DB_BUCKET is set).

How it works:
- Each server copy keeps its own local copy of the database file.
- Before a request uses the database, ask S3 "has it changed?" and only
  download it if it has (S3 answers 304 when nothing changed).
- If the request changed the database, upload it BEFORE replying, but only if
  nobody else saved first (S3 "If-Match"). If someone did, throw our copy away,
  download theirs and run the whole request again. So every save builds on the
  latest version and nothing is lost or saved twice.
- Photos are saved as their own S3 objects, so the database file stays small.

When S3DB_BUCKET is not set, install() does nothing and the app uses a normal
database file exactly as before.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import sqlite3
import threading
import time
import uuid

from flask import current_app

import db
from errors import ApiError

BUSY_MESSAGE = "The server is busy. Please try again."


class Busy(ApiError):
    """S3 could not be reached, or too many people saved at once."""

    def __init__(self, message: str = BUSY_MESSAGE):
        super().__init__(message, status=503)


class _Conflict(Exception):
    """Someone else saved the database first, so run the request again."""


def _status(err) -> int | None:
    """HTTP status code from an S3 (botocore) error, if it has one."""
    response = getattr(err, "response", None) or {}
    return response.get("ResponseMetadata", {}).get("HTTPStatusCode")


def _fingerprint(path: str):
    """SQLite's 'file change counter' (goes up on every commit) plus the size."""
    try:
        with open(path, "rb") as f:
            header = f.read(100)
        return header[24:28], os.path.getsize(path)
    except FileNotFoundError:
        return None


def _quick_check(path: str) -> bool:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _log(event: str, **details) -> None:
    # Only technical details, never any student data
    text = " ".join(f"{k}={v}" for k, v in details.items())
    print(f"[s3db] {event} {text}", flush=True)


class DbObject:
    """One S3 object holding the database, plus this server's local copy of it."""

    def __init__(self, s3, s3_put, bucket: str, key: str, local_path: str):
        self.s3 = s3  # normal client (with retries)
        self.s3_put = s3_put  # no automatic retries: a retried save could count twice
        self.bucket = bucket
        self.key = key
        self.local_path = local_path
        self._reset()

    def _reset(self) -> None:
        # One private copy per process
        self.pid = os.getpid()
        self.path = f"{self.local_path}.{self.pid}"
        self.etag = None  # which S3 version our local copy is
        self.base = None  # fingerprint of the file when this request started
        self.pulled = False  # has this request opened the database yet?

    def begin(self) -> None:
        """Called at the start of every API request."""
        if os.getpid() != self.pid:
            self._reset()
        if self.pulled:  # the last request stopped half way
            self.discard()

    def pull(self) -> str:
        """Make sure the local copy is the latest version. Returns its path."""
        if self.pulled:
            return self.path
        have_copy = self.etag is not None and os.path.exists(self.path)
        condition = {"IfNoneMatch": self.etag} if have_copy else {}
        fresh = created = False
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self.key, **condition)
        except Exception as err:
            code = _status(err)
            if code == 304:  # not changed since we downloaded it
                obj = None
            elif code == 404 and not self._has_history():
                obj = None  # a brand-new bucket: start a new database
                created = True
            else:
                _log("unavailable", status=code)
                raise Busy("The database is unavailable. Please try again.") from err

        if obj is not None:
            self._download(obj["Body"])
            self.etag = obj["ETag"]
            fresh = True
        if created:
            self._remove_local()
            self.etag = None

        before = None if created else _fingerprint(self.path)
        if fresh or created:
            db.init_db(self.path)  # create the tables, or add any new columns
        self.base = before
        self.pulled = True
        return self.path

    def finish(self) -> None:
        """Called after the request ran, before anything is sent back."""
        if not self.pulled:
            return
        self.pulled = False
        if _fingerprint(self.path) == self.base:
            return  # nothing changed, so there is nothing to save
        if os.path.exists(self.path + "-journal") or not _quick_check(self.path):
            self.discard()
            raise Busy("Could not save your change. Please try again.")

        token = uuid.uuid4().hex  # lets us check later whether an unclear save landed
        condition = {"IfMatch": self.etag} if self.etag else {"IfNoneMatch": "*"}
        started = time.monotonic()
        try:
            with open(self.path, "rb") as f:
                result = self.s3_put.put_object(
                    Bucket=self.bucket,
                    Key=self.key,
                    Body=f,
                    Metadata={"nrn-write": token},
                    **condition,
                )
        except Exception as err:
            code = _status(err)
            self.discard()
            if code in (409, 412):  # someone else saved first
                raise _Conflict() from err
            if self._landed(token):  # the save worked, only the reply was lost
                _log("saved-unclear-ok", status=code)
                return
            _log("save-failed", status=code)
            raise Busy("Could not save your change. Please try again.") from err
        self.etag = result["ETag"]
        _log(
            "saved",
            etag=self.etag,
            bytes=os.path.getsize(self.path),
            ms=int((time.monotonic() - started) * 1000),
        )

    def discard(self) -> None:
        """Forget the local copy, so the next request downloads a fresh one."""
        self._remove_local()
        self.etag = None
        self.pulled = False

    def _download(self, body) -> None:
        part = self.path + ".part"
        with open(part, "wb") as f:
            for chunk in iter(lambda: body.read(1024 * 1024), b""):
                f.write(chunk)
        # A leftover journal next to a new file would corrupt it, so remove it first
        self._remove(self.path + "-journal")
        os.replace(part, self.path)

    def _remove_local(self) -> None:
        for suffix in ("", "-journal", ".part"):
            self._remove(self.path + suffix)

    @staticmethod
    def _remove(path: str) -> None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass

    def _has_history(self) -> bool:
        """True if the database object existed before (then never start an empty one)."""
        try:
            listing = self.s3.list_object_versions(Bucket=self.bucket, Prefix=self.key, MaxKeys=10)
        except Exception as err:
            raise Busy("The database is unavailable. Please try again.") from err
        entries = listing.get("Versions", []) + listing.get("DeleteMarkers", [])
        return any(e.get("Key") == self.key for e in entries)

    def _landed(self, token: str) -> bool:
        try:
            head = self.s3.head_object(Bucket=self.bucket, Key=self.key)
        except Exception:
            return False
        return (head.get("Metadata") or {}).get("nrn-write") == token


class ReplayOnConflict:
    """Runs each API request, saves the database, and repeats on a clash."""

    def __init__(self, wsgi_app, store: DbObject, attempts: int, max_body: int):
        self.wsgi_app = wsgi_app
        self.store = store
        self.attempts = attempts
        self.max_body = max_body
        self.lock = threading.Lock()  # one request at a time per process

    def __call__(self, environ, start_response):
        if not environ.get("PATH_INFO", "").startswith("/api/"):
            return self.wsgi_app(environ, start_response)
        with self.lock:
            body = _read_body(environ, self.max_body + 1)  # keep it to run it again
            for attempt in range(self.attempts):
                env = dict(environ)
                env["wsgi.input"] = io.BytesIO(body)
                env["CONTENT_LENGTH"] = str(len(body))
                self.store.begin()
                try:
                    status, headers, chunks = _call(self.wsgi_app, env)
                    self.store.finish()  # upload BEFORE the reply goes out
                except _Conflict:
                    _log("conflict", attempt=attempt + 1)
                    time.sleep(random.uniform(0, 0.05 * 2**attempt))
                    continue
                except Busy as err:
                    return _json_error(start_response, err.message)
                except BaseException:
                    self.store.discard()
                    raise
                start_response(status, headers)
                return chunks
            _log("busy", attempts=self.attempts)
            return _json_error(start_response, BUSY_MESSAGE)


def _read_body(environ, limit: int) -> bytes:
    stream = environ.get("wsgi.input")
    if stream is None:
        return b""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length:
        return stream.read(min(length, limit))
    if environ.get("wsgi.input_terminated"):
        return stream.read(limit)
    return b""


def _call(wsgi_app, environ):
    """Run the Flask app and collect its whole reply without sending it yet."""
    captured = {"written": []}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = headers
        return captured["written"].append

    result = wsgi_app(environ, start_response)
    try:
        chunks = [*captured["written"], *result]
    finally:
        if hasattr(result, "close"):
            result.close()
    return captured["status"], captured["headers"], chunks


def _json_error(start_response, message: str):
    body = json.dumps({"error": message}).encode()
    start_response(
        "503 SERVICE UNAVAILABLE",
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("Retry-After", "1"),
        ],
    )
    return [body]


def save_photo(user_id: int, data_url):
    """In S3 mode, store a photo as its own object and return a pointer to it."""
    settings = current_app.config.get("S3DB_PHOTOS")
    if settings is None or not data_url:
        return data_url  # normal mode: keep the photo in the database as before
    s3, bucket, prefix = settings
    # Same photo gives the same name, so running a request again is harmless
    key = f"{prefix}{user_id}/{hashlib.sha256(data_url.encode()).hexdigest()}"
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=data_url.encode(), IfNoneMatch="*")
    except Exception as err:
        if _status(err) not in (409, 412):  # 412 means it is already saved
            raise Busy("Could not save the photo. Please try again.") from err
    return "s3:" + key


def load_photo(stored):
    """Turn a stored photo (a data URL or an S3 pointer) back into a data URL."""
    if not stored or not stored.startswith("s3:"):
        return stored
    settings = current_app.config.get("S3DB_PHOTOS")
    if settings is None:
        raise Busy("That photo is not available right now.")
    s3, bucket, _prefix = settings
    try:
        return s3.get_object(Bucket=bucket, Key=stored[3:])["Body"].read().decode()
    except Exception as err:
        raise Busy("Could not load the photo. Please try again.") from err


def _setting(app, name: str, default=None):
    return app.config.get(name) or os.environ.get(name) or default


def _boto3_clients():
    import boto3  # only needed in S3 mode, so it is imported here
    from botocore.config import Config

    endpoint = os.environ.get("S3DB_ENDPOINT_URL") or None  # only for a local test S3
    style = {"addressing_style": "path"} if endpoint else {}
    normal = boto3.client("s3", endpoint_url=endpoint, config=Config(s3=style))
    no_retry = boto3.client(
        "s3",
        endpoint_url=endpoint,
        config=Config(s3=style, retries={"total_max_attempts": 1}),
    )
    return normal, no_retry


def install(app) -> None:
    """Switch the app to the S3 database. Does nothing if S3DB_BUCKET is not set."""
    bucket = _setting(app, "S3DB_BUCKET")
    if not bucket:
        return
    s3, s3_put = app.config.get("S3DB_CLIENTS") or _boto3_clients()
    store = DbObject(
        s3,
        s3_put,
        bucket,
        _setting(app, "S3DB_KEY", "db/navigator.db"),
        app.config["DATABASE_PATH"],
    )
    app.config["DB_SYNC"] = store
    app.config["S3DB_PHOTOS"] = (s3, bucket, _setting(app, "S3DB_PHOTO_PREFIX", "photos/"))
    app.wsgi_app = ReplayOnConflict(
        app.wsgi_app,
        store,
        attempts=int(_setting(app, "S3DB_MAX_ATTEMPTS", 5)),
        max_body=app.config.get("MAX_CONTENT_LENGTH") or 3 * 1024 * 1024,
    )
