"""API tests for feature F1 — auth, onboarding, subjects, topics (happy + failure)."""

from __future__ import annotations

# --- auth --------------------------------------------------------------------


def test_signup_returns_token_and_user(client):
    res = client.post(
        "/api/auth/signup",
        json={"name": "Aroha", "email": "a@example.com", "password": "secret", "yearLevel": 12},
    )
    assert res.status_code == 201
    body = res.get_json()
    assert body["token"]
    assert body["user"]["email"] == "a@example.com"
    assert body["user"]["yearLevel"] == 12
    assert body["user"]["onboarding_done"] == 0
    assert "password" not in body["user"] and "password_hash" not in body["user"]


def test_signup_duplicate_email_is_400(client):
    payload = {"name": "A", "email": "dup@example.com", "password": "secret"}
    client.post("/api/auth/signup", json=payload)
    res = client.post("/api/auth/signup", json=payload)
    assert res.status_code == 400
    assert "already exists" in res.get_json()["error"]


def test_signup_short_password_is_400(client):
    res = client.post(
        "/api/auth/signup",
        json={"name": "A", "email": "b@example.com", "password": "x"},
    )
    assert res.status_code == 400


def test_login_then_me(client):
    client.post(
        "/api/auth/signup",
        json={"name": "A", "email": "c@example.com", "password": "secret"},
    )
    res = client.post("/api/auth/login", json={"email": "c@example.com", "password": "secret"})
    assert res.status_code == 200
    token = res.get_json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "c@example.com"


def test_login_wrong_password_is_401(client):
    client.post(
        "/api/auth/signup",
        json={"name": "A", "email": "d@example.com", "password": "secret"},
    )
    res = client.post("/api/auth/login", json={"email": "d@example.com", "password": "nope"})
    assert res.status_code == 401


def test_me_without_token_is_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_bad_token_is_401(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401


# --- onboarding --------------------------------------------------------------


def test_complete_onboarding_sets_flag(client, auth_headers):
    res = client.put("/api/user/onboarding", headers=auth_headers)
    assert res.status_code == 200
    me = client.get("/api/auth/me", headers=auth_headers)
    assert me.get_json()["user"]["onboarding_done"] == 1


# --- subjects & topics -------------------------------------------------------


def test_create_subject(client, auth_headers):
    res = client.post(
        "/api/subjects",
        json={"name": "Biology", "emoji": "🧬", "colour": "#10B981"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    subject = res.get_json()["subject"]
    assert subject["name"] == "Biology"
    assert subject["id"]


def test_create_subject_requires_auth(client):
    res = client.post("/api/subjects", json={"name": "Biology"})
    assert res.status_code == 401


def test_duplicate_subject_name_is_400(client, auth_headers):
    client.post("/api/subjects", json={"name": "Biology"}, headers=auth_headers)
    res = client.post("/api/subjects", json={"name": "Biology"}, headers=auth_headers)
    assert res.status_code == 400


def test_empty_subject_name_is_400(client, auth_headers):
    res = client.post("/api/subjects", json={"name": "   "}, headers=auth_headers)
    assert res.status_code == 400


def test_add_topic_and_list_subjects(client, auth_headers):
    sid = client.post(
        "/api/subjects", json={"name": "Biology", "emoji": "🧬"}, headers=auth_headers
    ).get_json()["subject"]["id"]

    res = client.post(
        "/api/topics",
        json={"subjectId": sid, "name": "Photosynthesis", "standardNumber": "AS 91156"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    assert res.get_json()["topic"]["name"] == "Photosynthesis"

    listing = client.get("/api/subjects", headers=auth_headers).get_json()["subjects"]
    assert len(listing) == 1
    assert listing[0]["topics"][0]["standardNumber"] == "AS 91156"


def test_add_topic_to_foreign_subject_is_404(client, auth_headers):
    # A second user's subject must not be writable by the first user.
    other = client.post(
        "/api/auth/signup",
        json={"name": "B", "email": "other@example.com", "password": "secret"},
    ).get_json()
    other_sid = client.post(
        "/api/subjects",
        json={"name": "Physics"},
        headers={"Authorization": f"Bearer {other['token']}"},
    ).get_json()["subject"]["id"]

    res = client.post(
        "/api/topics",
        json={"subjectId": other_sid, "name": "Mechanics"},
        headers=auth_headers,
    )
    assert res.status_code == 404


def test_subjects_are_scoped_per_user(client, auth_headers):
    client.post("/api/subjects", json={"name": "Biology"}, headers=auth_headers)
    other = client.post(
        "/api/auth/signup",
        json={"name": "B", "email": "scoped@example.com", "password": "secret"},
    ).get_json()
    listing = client.get(
        "/api/subjects", headers={"Authorization": f"Bearer {other['token']}"}
    ).get_json()["subjects"]
    assert listing == []
