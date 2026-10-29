"""SQLite persistence for the PoC. Holds portal-owned state only (metadata, workflow, audit).

No customer or transaction data is stored here — all records are synthetic.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hub.db"
WIB = timezone(timedelta(hours=7))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, name TEXT, title TEXT, unit TEXT, roles TEXT, clearance TEXT,
  groups_ TEXT, email TEXT, persona_note TEXT);
CREATE TABLE IF NOT EXISTS domains(
  id TEXT PRIMARY KEY, name TEXT, owner_id TEXT, steward_id TEXT, description TEXT, delegate_id TEXT);
CREATE TABLE IF NOT EXISTS assets(
  id TEXT PRIMARY KEY, type TEXT, name TEXT, title TEXT, description TEXT, domain_id TEXT,
  source_system TEXT, owner_id TEXT, steward_id TEXT, classification TEXT, lifecycle TEXT,
  grain TEXT, refresh TEXT, last_updated TEXT, quality_status TEXT, quality_score REAL,
  sla TEXT, allowed_use TEXT, retention_class TEXT, tags TEXT, fields_json TEXT,
  lineage_up TEXT, lineage_down TEXT, quality_rules TEXT, canonical_uri TEXT);
CREATE TABLE IF NOT EXISTS terms(
  id TEXT PRIMARY KEY, term TEXT, abbreviation TEXT, definition TEXT, formula TEXT,
  synonyms TEXT, domain_id TEXT, owner_id TEXT, steward_id TEXT, status TEXT,
  version INTEGER, effective_date TEXT, related_assets TEXT, related_dashboards TEXT,
  updated_at TEXT);
CREATE TABLE IF NOT EXISTS term_revisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, term_id TEXT, version INTEGER, definition TEXT,
  formula TEXT, change_note TEXT, status TEXT, author_id TEXT, created_at TEXT,
  decided_by TEXT, decided_at TEXT, rationale TEXT);
CREATE TABLE IF NOT EXISTS dashboards(
  id TEXT PRIMARY KEY, title TEXT, description TEXT, site TEXT, project TEXT, workbook TEXT,
  view_name TEXT, owner_id TEXT, domain_id TEXT, tags TEXT, certified INTEGER,
  lifecycle TEXT, audience TEXT, classification TEXT, permitted_groups TEXT,
  source_updated TEXT, sync_ts TEXT, sync_status TEXT, related_terms TEXT,
  related_assets TEXT, views_30d INTEGER);
CREATE TABLE IF NOT EXISTS service_definitions(
  type TEXT PRIMARY KEY, name TEXT, description TEXT, team TEXT, sla_days INTEGER,
  approval_policy TEXT, policy_version TEXT, active INTEGER, updated_at TEXT, updated_by TEXT);
CREATE TABLE IF NOT EXISTS requests(
  id TEXT PRIMARY KEY, seq INTEGER, type TEXT, title TEXT, requester_id TEXT, status TEXT,
  priority TEXT, target_type TEXT, target_id TEXT, domain_id TEXT, approver_id TEXT,
  team TEXT, purpose TEXT, details_json TEXT, required_approvals TEXT, created_at TEXT,
  updated_at TEXT, due_at TEXT, closed_at TEXT, result_ref TEXT, resolution TEXT,
  pii_redacted INTEGER DEFAULT 0, policy_version TEXT);
CREATE TABLE IF NOT EXISTS request_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, at TEXT, actor_id TEXT,
  action TEXT, from_status TEXT, to_status TEXT, note TEXT, internal INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, approver_id TEXT,
  approver_role TEXT, outcome TEXT, rationale TEXT, at TEXT, policy_version TEXT);
CREATE TABLE IF NOT EXISTS fulfilment_tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, system TEXT, team TEXT,
  state TEXT, evidence_ref TEXT, actor_id TEXT, at TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS entitlements(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, object_type TEXT, object_id TEXT,
  system TEXT, request_id TEXT, granted_by TEXT, granted_at TEXT, expires_at TEXT,
  revoked_at TEXT, revoked_by TEXT, revoke_reason TEXT);
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, at TEXT, subject TEXT, link TEXT,
  read INTEGER DEFAULT 0, channel TEXT);
CREATE TABLE IF NOT EXISTS search_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, user_id TEXT, query TEXT,
  result_count INTEGER, latency_ms REAL, clicked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS system_flags(
  key TEXT PRIMARY KEY, value TEXT, updated_at TEXT, updated_by TEXT);
CREATE TABLE IF NOT EXISTS sync_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, source TEXT, status TEXT, items INTEGER,
  detail TEXT, actor_id TEXT);
CREATE TABLE IF NOT EXISTS release_gates(
  id TEXT PRIMARY KEY, ord INTEGER, area TEXT, item TEXT, owner_role TEXT, status TEXT,
  signed_by TEXT, signed_at TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS gen_drafts(
  id TEXT PRIMARY KEY, seq INTEGER, owner_id TEXT, title TEXT, question TEXT, audience TEXT,
  decision TEXT, asset_ids TEXT, domain_id TEXT, status TEXT, version INTEGER, request_id TEXT,
  created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS gen_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, draft_id TEXT, version INTEGER, spec_json TEXT,
  source TEXT, note TEXT, author_id TEXT, created_at TEXT, latency_ms REAL, unsupported INTEGER,
  confidence TEXT);
CREATE TABLE IF NOT EXISTS audit_events(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, ts TEXT, actor_id TEXT,
  action TEXT, object_type TEXT, object_id TEXT, result TEXT, correlation_id TEXT,
  details TEXT, prev_hash TEXT, hash TEXT);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events
  BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
  BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;
"""


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse(ts: str | None) -> datetime | None:
    return datetime.fromisoformat(ts) if ts else None


def jl(value, default=None):
    """json-load helper tolerant of NULL."""
    if value in (None, ""):
        return default if default is not None else []
    return json.loads(value)


def write_lock(conn):
    """Take SQLite's write lock before read-then-write sequences (ID allocation, audit hash chain).

    A connection that has already written in this transaction holds the lock already.
    """
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")


def get_flag(conn, key, default="off") -> str:
    row = conn.execute("SELECT value FROM system_flags WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default
