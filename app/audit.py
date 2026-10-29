"""Append-only, hash-chained audit trail (FR-012).

Each event stores the SHA-256 of (previous hash + canonical event payload), so any edit or
deletion breaks the chain. The table also has SQLite triggers that reject UPDATE/DELETE.
Payloads carry identifiers and outcomes only — never free-text business content.
"""
import hashlib
import json
import uuid

from .db import iso, utcnow, write_lock


def _digest(prev_hash: str, event: dict) -> str:
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


def log(conn, actor_id, action, object_type, object_id, result="success", details=None,
        correlation_id=None, at=None):
    write_lock(conn)  # read-latest-hash + insert must be atomic across concurrent requests
    prev =conn.execute("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = prev["hash"] if prev else "GENESIS"
    event = {
        "event_id": uuid.uuid4().hex[:16],
        "ts": iso(at or utcnow()),
        "actor_id": actor_id or "anonymous",
        "action": action,
        "object_type": object_type,
        "object_id": object_id or "",
        "result": result,
        "correlation_id": correlation_id or "",
        "details": json.dumps(details or {}, sort_keys=True),
    }
    conn.execute(
        "INSERT INTO audit_events(event_id, ts, actor_id, action, object_type, object_id, result,"
        " correlation_id, details, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (*event.values(), prev_hash, _digest(prev_hash, event)),
    )


def verify(conn) -> dict:
    prev_hash = "GENESIS"
    count = 0
    for row in conn.execute("SELECT * FROM audit_events ORDER BY seq"):
        event = {k: row[k] for k in ("event_id", "ts", "actor_id", "action", "object_type",
                                     "object_id", "result", "correlation_id", "details")}
        if row["prev_hash"] != prev_hash or row["hash"] != _digest(prev_hash, event):
            return {"ok": False, "count": count, "broken_at": row["seq"]}
        prev_hash = row["hash"]
        count += 1
    return {"ok": True, "count": count, "broken_at": None, "head": prev_hash}
