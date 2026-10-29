import re

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.main import create_app

CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')


class Session:
    """A signed-in browser session for one persona."""

    def __init__(self, app, uid):
        self.client = TestClient(app, follow_redirects=False)
        token = CSRF.search(self.client.get("/login").text).group(1)
        r = self.client.post("/login", data={"csrf_token": token, "uid": uid, "next": "/"})
        assert r.status_code == 303
        self.csrf = CSRF.search(self.client.get("/").text).group(1)

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, data=None, **kw):
        return self.client.post(url, data={"csrf_token": self.csrf, **(data or {})}, **kw)

    def act(self, req_id, action, note="Recorded for test.", result_ref=""):
        return self.post(f"/requests/{req_id}/action", {"action": action, "note": note, "result_ref": result_ref})


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "hub.db", secret_key="test-secret")


@pytest.fixture
def db(app):
    conn = connect(app.state.db_path)
    yield conn
    conn.close()


@pytest.fixture
def login(app):
    return lambda uid: Session(app, uid)


@pytest.fixture
def evidence(record_property):
    def _tag(prd_ref, title):
        record_property("prd_ref", prd_ref)
        record_property("title", title)
    return _tag


def status_of(db, req_id):
    return db.execute("SELECT status FROM requests WHERE id=?", (req_id,)).fetchone()["status"]


def generate(session, question, assets, audience="Risk committee", decision="Regional collection focus"):
    """Ask the AI dashboard generator for a draft; returns the response (303 to the draft on success)."""
    return session.post("/generator", {"question": question, "audience": audience, "decision": decision,
                                       "assets": assets if isinstance(assets, list) else [assets]})


def draft_id(response):
    assert response.status_code == 303, response.text[:400]
    return response.headers["location"].rsplit("/", 1)[-1]


def submit_access(session, target, **extra):
    data = {"target": target, "purpose": "Monthly regional performance review.", "task": "Committee pack",
            "scope": "All regions, 12 months", "duration_days": "90", "intended_use": "Management reporting", **extra}
    r = session.post(f"/requests/new/A", data)
    assert r.status_code == 303, r.text[:400]
    return r.headers["location"].rsplit("/", 1)[-1]
