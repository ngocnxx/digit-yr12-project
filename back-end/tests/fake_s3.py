"""An in-memory stand-in for Amazon S3, for testing s3db.py without AWS.

It copies the S3 rules that matter here:
- GET with IfNoneMatch=<etag> raises 304 when the object has not changed.
- PUT with IfNoneMatch="*" raises 412 if the object already exists.
- PUT with IfMatch=<etag> raises 412 if someone saved a newer version
  (and 404 if the object is gone).
Errors look like botocore errors (they have a .response dict).
"""

from __future__ import annotations

import hashlib
import io


class FakeClientError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(f"{status} {code}")
        self.response = {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}


class _Body:
    def __init__(self, data: bytes):
        self._buf = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


class FakeS3:
    def __init__(self):
        self.objects: dict[str, dict] = {}  # key -> {"body", "etag", "metadata"}
        self.history: list[tuple[str, str]] = []  # ("version" | "delete", key)
        self.calls: list[tuple[str, str, int]] = []  # (operation, key, status)
        self.before_put = None  # hook(key): runs before a PUT checks its condition
        self.fail_put = None  # hook(key) -> None or (status, landed)
        self.fail_get = None  # hook(key) -> None or status
        self._counter = 0

    # --- helpers for tests -------------------------------------------------

    def seed(self, key: str, data: bytes) -> None:
        """Put an object in place without counting it as a call."""
        self._store(key, data, {})

    def rewrite(self, key: str) -> None:
        """Save the same bytes again, which gives a new ETag (like another save)."""
        obj = self.objects[key]
        self._store(key, obj["body"], obj["metadata"])

    def count(self, operation: str, status: int | None = None, prefix: str = "") -> int:
        return sum(
            1
            for op, key, st in self.calls
            if op == operation and key.startswith(prefix) and (status is None or st == status)
        )

    def versions(self, key: str) -> int:
        return sum(1 for kind, k in self.history if kind == "version" and k == key)

    # --- the S3 API used by s3db.py ---------------------------------------

    def get_object(self, Bucket, Key, IfNoneMatch=None):
        failure = self.fail_get(Key) if self.fail_get else None
        if failure:
            self.calls.append(("get", Key, failure))
            raise FakeClientError(failure, "InternalError")
        obj = self.objects.get(Key)
        if obj is None:
            self.calls.append(("get", Key, 404))
            raise FakeClientError(404, "NoSuchKey")
        if IfNoneMatch is not None and IfNoneMatch == obj["etag"]:
            self.calls.append(("get", Key, 304))
            raise FakeClientError(304, "304")
        self.calls.append(("get", Key, 200))
        return {"Body": _Body(obj["body"]), "ETag": obj["etag"]}

    def put_object(self, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None, Metadata=None, **_):
        data = Body.read() if hasattr(Body, "read") else Body
        if self.before_put is not None:
            self.before_put(Key)
        current = self.objects.get(Key)
        if IfNoneMatch == "*" and current is not None:
            self.calls.append(("put", Key, 412))
            raise FakeClientError(412, "PreconditionFailed")
        if IfMatch is not None:
            if current is None:
                self.calls.append(("put", Key, 404))
                raise FakeClientError(404, "NoSuchKey")
            if current["etag"] != IfMatch:
                self.calls.append(("put", Key, 412))
                raise FakeClientError(412, "PreconditionFailed")
        failure = self.fail_put(Key) if self.fail_put else None
        if failure:
            status, landed = failure
            if landed:
                self._store(Key, data, Metadata or {})
            self.calls.append(("put", Key, status))
            raise FakeClientError(status, "InternalError")
        etag = self._store(Key, data, Metadata or {})
        self.calls.append(("put", Key, 200))
        return {"ETag": etag}

    def head_object(self, Bucket, Key):
        obj = self.objects.get(Key)
        if obj is None:
            raise FakeClientError(404, "NotFound")
        return {"ETag": obj["etag"], "Metadata": dict(obj["metadata"])}

    def list_object_versions(self, Bucket, Prefix="", MaxKeys=1000):
        versions = [{"Key": k} for kind, k in self.history if kind == "version" and k.startswith(Prefix)]
        markers = [{"Key": k} for kind, k in self.history if kind == "delete" and k.startswith(Prefix)]
        return {"Versions": versions[:MaxKeys], "DeleteMarkers": markers[:MaxKeys]}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)
        self.history.append(("delete", Key))

    def _store(self, key: str, data: bytes, metadata: dict) -> str:
        self._counter += 1
        # Real S3 uses the MD5 of the content; the counter makes every save unique
        etag = f'"{hashlib.md5(data).hexdigest()}-{self._counter}"'
        self.objects[key] = {"body": data, "etag": etag, "metadata": dict(metadata)}
        self.history.append(("version", key))
        return etag
