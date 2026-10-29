"""Request lifecycle engine (FR-006 .. FR-009).

Every transition is role- and state-controlled, recorded as a request event, and written to
the audit trail. Approval (a decision) and provisioning/delivery (fulfilment) are separate
states with separate evidence.
"""
import json
from dataclasses import dataclass
from datetime import timedelta

from . import audit, pii
from .db import get_flag, iso, jl, parse, utcnow, write_lock
from .policy import TEAM_LABELS, User

APPROVED_WAITING = "Approved – Awaiting Fulfilment"
TERMINAL = {"Closed", "Rejected", "Cancelled"}
STATUS_TONE = {
    "Submitted": "info", "Triage": "info", "Awaiting Information": "warn",
    "Awaiting Approval": "warn", APPROVED_WAITING: "accent", "In Progress": "accent",
    "Review/UAT": "accent", "Provisioned": "good", "Provision Failed": "bad",
    "Delivered": "good", "Closed": "muted", "Rejected": "bad", "Cancelled": "muted",
    "On Hold": "warn",
}

REQUEST_TYPES = {
    "A": ("Access to an existing data asset or dashboard", "key"),
    "B": ("New dataset / integration", "database"),
    "C": ("New dashboard / report", "chart"),
    "D": ("Analysis / data science / insight", "insight"),
    "E": ("Data quality issue / definition dispute", "alert"),
}


class WorkflowError(Exception):
    pass


class NotAllowed(Exception):
    pass


@dataclass(frozen=True)
class Transition:
    action: str
    label: str
    frm: tuple
    to: str
    actor: str  # requester | approver | team
    note: str = "optional"  # required | optional
    style: str = "primary"
    needs_result: bool = False
    hint: str = ""


def _cancel(*frm):
    return Transition("cancel", "Cancel request", frm, "Cancelled", "requester", "optional", "ghost")


_PROJECT_FLOW = [
    Transition("reuse", "Close — existing asset fits", ("Triage",), "Closed", "team", "required",
               "secondary", True, "Duplicate prevention: link the existing dashboard / data product."),
    Transition("accept", "Accept into backlog", ("Triage",), "Awaiting Approval", "team", "optional",
               hint="Routes KPI definitions and data-source use to the domain data owner."),
    Transition("request_info", "Request more information", ("Triage",), "Awaiting Information",
               "team", "required", "secondary"),
    Transition("reject", "Reject", ("Triage",), "Rejected", "team", "required", "danger"),
    Transition("respond", "Provide information", ("Awaiting Information",), "Triage", "requester",
               "required"),
    Transition("approve", "Approve definitions & source use", ("Awaiting Approval",),
               APPROVED_WAITING, "approver", "required"),
    Transition("reject_owner", "Reject", ("Awaiting Approval",), "Rejected", "approver", "required",
               "danger"),
    Transition("start", "Start delivery", (APPROVED_WAITING,), "In Progress", "team"),
    Transition("hold", "Put on hold", ("In Progress",), "On Hold", "team", "required", "secondary"),
    Transition("resume", "Resume", ("On Hold",), "In Progress", "team"),
    Transition("submit_uat", "Submit for review / UAT", ("In Progress",), "Review/UAT", "team",
               "optional", needs_result=True, hint="Link to the non-production output for UAT."),
    Transition("accept_delivery", "Accept delivery", ("Review/UAT",), "Delivered", "requester"),
    Transition("raise_issue", "Raise issue (reopen)", ("Review/UAT",), "In Progress", "requester",
               "required", "secondary"),
    Transition("close", "Close & register output in catalog", ("Delivered",), "Closed", "team",
               "optional", needs_result=True, hint="Published asset reference and operational owner."),
    _cancel("Submitted", "Triage", "Awaiting Information", "Awaiting Approval"),
]

FLOWS = {
    "A": [
        Transition("approve", "Approve", ("Awaiting Approval",), "@approve", "approver", "required"),
        Transition("request_info", "Request more information", ("Awaiting Approval",),
                   "Awaiting Information", "approver", "required", "secondary"),
        Transition("reject", "Reject", ("Awaiting Approval",), "Rejected", "approver", "required",
                   "danger"),
        Transition("respond", "Provide information", ("Awaiting Information",), "Awaiting Approval",
                   "requester", "required"),
        Transition("provision", "Provision access in system of record",
                   (APPROVED_WAITING, "Provision Failed"), "@provision", "team",
                   hint="Executes in the access-management system of record (simulated)."),
        Transition("confirm", "Confirm access works", ("Provisioned",), "Closed", "requester"),
        _cancel("Submitted", "Awaiting Approval", "Awaiting Information"),
    ],
    "B": _PROJECT_FLOW,
    "C": _PROJECT_FLOW,
    "D": _PROJECT_FLOW,
    "E": [
        Transition("accept", "Accept & investigate", ("Triage",), "In Progress", "team"),
        Transition("reject", "Reject (not an issue)", ("Triage",), "Rejected", "team", "required",
                   "danger"),
        Transition("resolve", "Mark resolved (root cause)", ("In Progress",), "Delivered", "team",
                   "required", hint="Record root cause and remediation evidence."),
        Transition("confirm", "Confirm resolution", ("Delivered",), "Closed", "requester"),
        Transition("raise_issue", "Not resolved (reopen)", ("Delivered",), "In Progress",
                   "requester", "required", "secondary"),
        _cancel("Submitted", "Triage"),
    ],
}

TEAM_FOR_TYPE = {"B": "platform", "C": "bi", "D": "analytics", "E": "steward"}

_F = lambda name, label, kind="text", required=True, help="", options=None: dict(  # noqa: E731
    name=name, label=label, kind=kind, required=required, help=help, options=options or [])

FORMS = {
    "A": [
        _F("target", "Asset or dashboard", "target", help="Search the catalog — you do not need table names."),
        _F("purpose", "Business purpose", "textarea", help="Why you need access, in business terms."),
        _F("task", "Task / decision supported"),
        _F("scope", "Required scope", help="e.g. period, region, product line, aggregated vs detail"),
        _F("duration_days", "Access duration", "select", options=["30", "90", "180"]),
        _F("intended_use", "Intended use", "select",
           options=["Management reporting", "Ad-hoc analysis", "Operational monitoring",
                    "Regulatory reporting", "Model development"]),
    ],
    "B": [
        _F("title", "Short title"),
        _F("purpose", "Business question", "textarea"),
        _F("expected_outcome", "Expected decision / outcome"),
        _F("domain_id", "Data domain", "domain"),
        _F("source_hint", "Source system (if known)", required=False),
        _F("frequency", "Refresh frequency", "select", options=["Daily", "Weekly", "Monthly", "One-off"]),
        _F("grain", "Grain", help="e.g. per account per day, per branch per month"),
        _F("consumers", "Expected consumers"),
        _F("sensitivity", "Sensitivity context", "select",
           options=["No personal data expected", "May contain personal data", "Unsure"]),
        _F("priority", "Priority", "select", options=["Medium", "High", "Low"]),
    ],
    "C": [
        _F("title", "Dashboard / report title"),
        _F("purpose", "Business question", "textarea"),
        _F("decision", "Decision supported"),
        _F("audience", "Audience"),
        _F("kpis", "KPIs (business terms)", help="Use glossary terms where possible, e.g. NPL, CASA."),
        _F("dimensions", "Dimensions / filters", required=False),
        _F("refresh", "Refresh need", "select", options=["Daily", "Weekly", "Monthly"]),
        _F("domain_id", "Business domain", "domain"),
        _F("confidentiality", "Confidentiality", "select", options=["Internal", "Confidential", "Restricted"]),
        _F("priority", "Priority", "select", options=["Medium", "High", "Low"]),
    ],
    "D": [
        _F("title", "Short title"),
        _F("purpose", "Question / hypothesis", "textarea"),
        _F("decision", "Business decision / intended action"),
        _F("cohort", "Cohort, period & grain"),
        _F("output", "Expected output", "select", options=["Slide summary", "Model / score", "Data extract (aggregated)", "Recommendation memo"]),
        _F("personal_data", "Use of personal / confidential data", "select", options=["None", "Aggregated only", "Record-level (needs review)"]),
        _F("domain_id", "Business domain", "domain"),
        _F("priority", "Priority", "select", options=["Medium", "High", "Low"]),
    ],
    "E": [
        _F("target", "Affected asset, dashboard or term", "target"),
        _F("title", "Short title"),
        _F("purpose", "Observed issue", "textarea", help="Describe the symptom — do not paste customer records."),
        _F("impact", "Business impact"),
        _F("period", "Affected period", required=False),
        _F("severity", "Severity", "select", options=["Medium", "High", "Low", "Critical"]),
    ],
}

FREE_TEXT = {"title", "purpose", "task", "scope", "expected_outcome", "source_hint", "grain",
             "consumers", "decision", "audience", "kpis", "dimensions", "cohort", "impact", "period"}


# ---------------------------------------------------------------- helpers

def get_request(conn, req_id):
    return conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()


def _event(conn, req_id, at, actor, action, frm, to, note="", internal=False):
    conn.execute("INSERT INTO request_events(request_id, at, actor_id, action, from_status, to_status,"
                 " note, internal) VALUES (?,?,?,?,?,?,?,?)",
                 (req_id, iso(at), actor, action, frm, to, note, int(internal)))


def notify(conn, user_ids, subject, link, at=None):
    """Notifications carry only the request ID and status — never business content (FR-017)."""
    for uid in set(user_ids):
        conn.execute("INSERT INTO notifications(user_id, at, subject, link, channel) VALUES (?,?,?,?,?)",
                     (uid, iso(at or utcnow()), subject, link, "in-app + email (simulated)"))


def team_members(conn, team):
    return [r["id"] for r in conn.execute("SELECT id, roles FROM users")
            if team in r["roles"].split(",")]


def pending_approval(conn, req) -> str | None:
    required = jl(req["required_approvals"])
    done = {r["approver_role"] for r in conn.execute(
        "SELECT approver_role FROM decisions WHERE request_id=? AND outcome='approved'", (req["id"],))}
    for role in required:
        if role not in done:
            return role
    return None


def primary_action(actions):
    """The one action a person most likely came to take (cancel is never the headline)."""
    ranked = sorted((a for a in actions if a.action != "cancel"), key=lambda a: a.style != "primary")
    return ranked[0] if ranked else None


# Plain-language "where is it now" — {who} is a name, a team, or "You".
_NOW = {
    "Submitted": "Received. The Hub is validating and routing it.",
    "Triage": "{who} {is} reviewing the scope and checking whether something that already exists answers it.",
    "Awaiting Information": "A question was asked in the request history. {who} must reply before work can continue.",
    "Awaiting Approval": "{who} must approve or reject.",
    APPROVED_WAITING: "Approved, but not usable yet. {who} must set it up in the system of record.",
    "Provisioned": "Access is set up at the source. {who} should check it works, then confirm to close the request.",
    "Provision Failed": "Setup failed at the source, so no access exists. The approval still stands; {who} must retry.",
    "In Progress": "{who} {is} working on it.",
    "On Hold": "Paused by {who}. The reason is in the request history.",
    "Review/UAT": "The output is ready for review. {who} should accept it or raise an issue.",
    "Delivered": "Delivered. {who} will register the output in the catalog and close the request.",
    "Closed": "Done. Nothing more to do.",
    "Rejected": "Rejected. The decision and its rationale are in the request history.",
    "Cancelled": "Cancelled by the requester.",
}


def now_summary(conn, user: User, req) -> dict:
    """Who holds the request right now and what that means, for the banner, workspace and home."""
    status, acts = req["status"], available_actions(conn, user, req)
    mine = primary_action(acts)
    if status in TERMINAL:
        who = None
    elif mine:
        who = "You"
    elif status == "Awaiting Approval":
        pend = pending_approval(conn, req) if req["type"] == "A" else "data_owner"
        if pend == "governance":
            who = "Security & Privacy"
        else:
            row = conn.execute("SELECT name FROM users WHERE id=?", (req["approver_id"],)).fetchone()
            who = f"{row['name']} (data owner)" if row else "The data owner"
    elif status in ("Awaiting Information", "Review/UAT", "Provisioned") or (status == "Delivered" and req["type"] == "E"):
        row = conn.execute("SELECT name FROM users WHERE id=?", (req["requester_id"],)).fetchone()
        who = row["name"] if row else "The requester"
    else:
        who = TEAM_LABELS.get(req["team"], req["team"])
    text = _NOW.get(status, status)
    if status == "Delivered" and req["type"] == "E":
        text = "Marked resolved. {who} should confirm, or reopen it if the problem is still there."
    elif status == APPROVED_WAITING and req["type"] != "A":
        text = "Approved. {who} can now start delivery."
    elif status == "Closed" and req["resolution"] == "reused-existing":
        text = "Closed: an existing asset already covers this need, so nothing new had to be built."
    if status == "Awaiting Approval" and req["type"] == "A" and pending_approval(conn, req) == "governance":
        text = "The data owner has approved. Because the asset is Confidential or Restricted, " + text
    text = text.format(who=who or "", **{"is": "are" if mine else "is"}).replace(", You ", ", you ")
    return dict(who=who, you=mine is not None, action=mine, text=text)


def resolve_target(conn, ref: str):
    """'asset:ID' | 'dashboard:ID' | 'term:ID' -> (type, row)."""
    if not ref or ":" not in ref:
        return None, None
    kind, oid = ref.split(":", 1)
    table = {"asset": "assets", "dashboard": "dashboards", "term": "terms"}.get(kind)
    if not table:
        return None, None
    return kind, conn.execute(f"SELECT * FROM {table} WHERE id=?", (oid,)).fetchone()


def target_label(row, kind):
    if row is None:
        return ""
    return row["term"] if kind == "term" else row["title"]


# ---------------------------------------------------------------- create

def create_request(conn, user: User, rtype: str, data: dict, at=None, corr=None) -> str:
    from .policy import active_entitlement, can_discover

    at = at or utcnow()
    if rtype not in FORMS:
        raise WorkflowError("Unknown request type.")
    write_lock(conn)  # request IDs are allocated from MAX(seq)
    service =conn.execute("SELECT * FROM service_definitions WHERE type=? AND active=1", (rtype,)).fetchone()
    if not service:
        raise WorkflowError("This service is currently not available.")

    missing = [f["label"] for f in FORMS[rtype] if f["required"] and not str(data.get(f["name"], "")).strip()]
    if missing:
        raise WorkflowError("Please complete: " + ", ".join(missing))
    for f in FORMS[rtype]:
        if f["kind"] == "select" and data.get(f["name"]) not in f["options"]:
            raise WorkflowError(f"Invalid value for {f['label']}.")

    findings = []
    for key in FREE_TEXT & data.keys():
        findings += pii.scan(data[key])
    if findings and not data.get("_redact"):
        raise SensitiveDataFound(findings)
    if findings:
        for key in FREE_TEXT & data.keys():
            data[key] = pii.redact(data[key])

    kind, target, domain_id = None, None, data.get("domain_id")
    if "target" in data:
        kind, target = resolve_target(conn, data["target"])
        obj_type = "dashboard" if kind == "dashboard" else "asset"
        if target is None or (kind != "term" and not can_discover(conn, user, target, obj_type)):
            raise WorkflowError("Selected item was not found.")
        domain_id = target["domain_id"]
        if rtype == "A":
            if kind == "term":
                raise WorkflowError("Business terms are open to all users — no access request needed.")
            if active_entitlement(conn, user.id, obj_type, target["id"]):
                raise WorkflowError("You already hold active access to this item.")
            dup = conn.execute(
                "SELECT id FROM requests WHERE requester_id=? AND type='A' AND target_id=? AND status NOT IN"
                " ('Closed','Rejected','Cancelled')", (user.id, target["id"])).fetchone()
            if dup:
                raise WorkflowError(f"You already have an open request for this item ({dup['id']}).")

    domain = conn.execute("SELECT * FROM domains WHERE id=?", (domain_id,)).fetchone()
    if domain is None:
        raise WorkflowError("Please select a valid domain.")

    if rtype == "A":
        title = f"Access: {target_label(target, kind)}"
        team = "bi" if kind == "dashboard" else "platform"
        required = ["data_owner"]
        if target["classification"] in ("Confidential", "Restricted"):
            required.append("governance")
    else:
        title = data["title"].strip()
        team = TEAM_FOR_TYPE[rtype]
        required = [] if rtype == "E" else ["data_owner"]
    approver, routing = domain["owner_id"], ""
    if approver == user.id:  # segregation of duties: an owner never decides on their own request
        approver = domain["delegate_id"]
        routing = " Requester is the domain owner → routed to the delegate approver."

    seq = (conn.execute("SELECT COALESCE(MAX(seq),0) m FROM requests").fetchone()["m"]) + 1
    req_id = f"REQ-{at.astimezone().year}-{seq:04d}"
    details = {f["name"]: data[f["name"]] for f in FORMS[rtype]
               if f["name"] not in ("purpose", "title", "target") and data.get(f["name"])}
    first = "Awaiting Approval" if rtype == "A" else "Triage"
    conn.execute(
        "INSERT INTO requests(id, seq, type, title, requester_id, status, priority, target_type, target_id,"
        " domain_id, approver_id, team, purpose, details_json, required_approvals, created_at, updated_at,"
        " due_at, pii_redacted, policy_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (req_id, seq, rtype, title[:140], user.id, first, data.get("priority") or data.get("severity") or "Medium",
         kind, target["id"] if target is not None else None, domain_id, approver, team, data["purpose"].strip(),
         json.dumps(details), json.dumps(required), iso(at), iso(at),
         iso(at + timedelta(days=service["sla_days"])), int(bool(findings)), service["policy_version"]))

    _event(conn, req_id, at, user.id, "submit", "Draft", "Submitted",
           "Submitted via Request Center." + (" Sensitive identifiers were redacted before storage." if findings else ""))
    checks = "Required fields complete; requester identity verified via SSO session"
    if rtype == "A":
        checks += f"; no existing entitlement; classification {target['classification']} → approvals: " + \
                  " + ".join("Data owner" if r == "data_owner" else "Security & Privacy" for r in required)
        notify(conn, [approver], f"{req_id} is awaiting your decision", f"/requests/{req_id}", at)
    else:
        notify(conn, team_members(conn, team), f"{req_id} is waiting in the {TEAM_LABELS[team]} triage queue",
               f"/requests/{req_id}", at)
    _event(conn, req_id, at, "system", "validate", "Submitted", first,
           f"{checks}. Routed per {service['policy_version']}.{routing}")
    audit.log(conn, user.id, "request.submit", "request", req_id,
              details={"type": rtype, "target": data.get("target"), "pii_redacted": bool(findings),
                       "routed_to": approver if rtype == "A" else team}, correlation_id=corr, at=at)
    return req_id


class SensitiveDataFound(WorkflowError):
    def __init__(self, findings):
        super().__init__("Possible sensitive identifiers detected.")
        self.findings = findings


# ---------------------------------------------------------------- transitions

def _actor_ok(conn, user: User, req, t: Transition) -> bool:
    if t.actor == "requester":
        return user.id == req["requester_id"]
    if user.id == req["requester_id"]:
        return False  # segregation of duties: nobody approves or fulfils their own request
    if t.actor == "team":
        return req["team"] in user.roles
    if t.actor == "approver":
        pending = pending_approval(conn, req) if req["type"] == "A" else "data_owner"
        if pending == "data_owner":
            return user.id == req["approver_id"]
        if pending == "governance":
            return "governance" in user.roles
    return False


def available_actions(conn, user: User, req) -> list[Transition]:
    return [t for t in FLOWS[req["type"]] if req["status"] in t.frm and _actor_ok(conn, user, req, t)]


def perform(conn, user: User, req_id, action, note="", result_ref="", at=None, corr=None) -> str:
    at = at or utcnow()
    write_lock(conn)  # evidence refs are allocated from COUNT(*)
    req = get_request(conn, req_id)
    if req is None:
        raise WorkflowError("Request not found.")
    t = next((t for t in FLOWS[req["type"]] if t.action == action and req["status"] in t.frm), None)
    if t is None:
        raise WorkflowError(f"'{action}' is not permitted while the request is {req['status']}.")
    if not _actor_ok(conn, user, req, t):
        audit.log(conn, user.id, f"request.{action}", "request", req_id, result="denied",
                  details={"reason": "role/segregation-of-duties"}, correlation_id=corr, at=at)
        raise NotAllowed("You are not authorised to perform this action on this request.")
    note = (note or "").strip()
    if t.note == "required" and not note:
        raise WorkflowError("A rationale / note is required for this action.")
    if t.needs_result and not result_ref.strip():
        raise WorkflowError("A result reference is required for this action.")
    if pii.scan(note) or pii.scan(result_ref):
        raise WorkflowError("The note looks like it contains customer identifiers. Remove them and retry.")

    frm, to = req["status"], t.to
    evidence = None
    role = "data_owner" if user.id == req["approver_id"] else ("governance" if "governance" in user.roles else req["team"])

    if action in ("approve", "reject", "reject_owner", "request_info") and t.actor == "approver":
        decision_role = (pending_approval(conn, req) or "data_owner") if req["type"] == "A" else "data_owner"
        outcome = {"approve": "approved", "request_info": "needs-information"}.get(action, "rejected")
        conn.execute("INSERT INTO decisions(request_id, approver_id, approver_role, outcome, rationale, at,"
                     " policy_version) VALUES (?,?,?,?,?,?,?)",
                     (req_id, user.id, decision_role, outcome, note, iso(at), req["policy_version"]))
        role = decision_role

    if to == "@approve":
        req_after = get_request(conn, req_id)
        nxt = pending_approval(conn, req_after)
        to = "Awaiting Approval" if nxt else APPROVED_WAITING
        if nxt == "governance":
            notify(conn, team_members(conn, "governance"), f"{req_id} needs Security & Privacy review",
                   f"/requests/{req_id}", at)
    elif to == "@provision":
        to, evidence = _provision(conn, user, req, at)

    closing = to in TERMINAL
    resolution = {"reuse": "reused-existing", "reject": "rejected", "reject_owner": "rejected",
                  "cancel": "cancelled"}.get(action, req["resolution"])
    if to == "Closed" and resolution is None:
        resolution = "completed"
    conn.execute("UPDATE requests SET status=?, updated_at=?, closed_at=?, result_ref=COALESCE(NULLIF(?,''), result_ref),"
                 " resolution=? WHERE id=?",
                 (to, iso(at), iso(at) if closing else None, result_ref.strip(), resolution, req_id))
    event_note = note
    if evidence:
        event_note = (note + " " if note else "") + evidence
    _event(conn, req_id, at, user.id, action, frm, to, event_note)

    watchers = {req["requester_id"]}
    if to == "Awaiting Approval" and req["type"] != "A":
        watchers.add(req["approver_id"])
    if to in (APPROVED_WAITING, "Triage"):
        watchers |= set(team_members(conn, req["team"]))
    notify(conn, watchers - {user.id}, f"{req_id} status changed to {to}", f"/requests/{req_id}", at)
    audit.log(conn, user.id, f"request.{action}", "request", req_id,
              details={"from": frm, "to": to, "as_role": role}, correlation_id=corr, at=at)
    return to


def _provision(conn, user: User, req, at):
    """Simulated call to the access-management system of record. Fails closed."""
    system = "Tableau Server (simulated)" if req["target_type"] == "dashboard" else "Enterprise IAM (simulated)"
    outage = get_flag(conn, "iam_outage") == "on" or (
        req["target_type"] == "dashboard" and get_flag(conn, "tableau_outage") == "on")
    if outage:
        conn.execute("INSERT INTO fulfilment_tasks(request_id, system, team, state, evidence_ref, actor_id, at, detail)"
                     " VALUES (?,?,?,?,?,?,?,?)", (req["id"], system, req["team"], "failed", None, user.id,
                                                   iso(at), "Target system unavailable — no access granted"))
        audit.log(conn, user.id, "entitlement.provision", req["target_type"], req["target_id"], result="failed",
                  details={"request": req["id"], "system": system}, at=at)
        return "Provision Failed", f"[{system} unavailable — nothing was granted (fail closed).]"
    days = int(jl(req["details_json"], {}).get("duration_days", 90))
    seq = conn.execute("SELECT COUNT(*) c FROM fulfilment_tasks").fetchone()["c"] + 1
    ref = ("TBL-GRP-" if req["target_type"] == "dashboard" else "IAM-CHG-") + f"{at.year}{seq:05d}"
    conn.execute("INSERT INTO entitlements(user_id, object_type, object_id, system, request_id, granted_by,"
                 " granted_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                 (req["requester_id"], req["target_type"], req["target_id"], system, req["id"], user.id,
                  iso(at), iso(at + timedelta(days=days))))
    conn.execute("INSERT INTO fulfilment_tasks(request_id, system, team, state, evidence_ref, actor_id, at, detail)"
                 " VALUES (?,?,?,?,?,?,?,?)", (req["id"], system, req["team"], "provisioned", ref, user.id,
                                               iso(at), f"Access granted for {days} days"))
    audit.log(conn, user.id, "entitlement.provision", req["target_type"], req["target_id"],
              details={"request": req["id"], "system": system, "evidence": ref, "days": days}, at=at)
    return "Provisioned", f"[Provisioned in {system}; evidence {ref}; expires in {days} days.]"


def add_comment(conn, user: User, req, body: str, internal: bool, at=None, corr=None):
    body = (body or "").strip()
    if not body:
        raise WorkflowError("Comment is empty.")
    if pii.scan(body):
        raise WorkflowError("The comment looks like it contains customer identifiers. Remove them and retry.")
    internal = internal and user.id != req["requester_id"]
    _event(conn, req["id"], at or utcnow(), user.id, "comment", None, None, body[:2000], internal)
    if not internal:
        others = {req["requester_id"], req["approver_id"]} - {user.id}
        notify(conn, others, f"New comment on {req['id']}", f"/requests/{req['id']}", at)
    audit.log(conn, user.id, "request.comment", "request", req["id"], details={"internal": internal},
              correlation_id=corr, at=at)


def sla_state(req, now=None):
    now = now or utcnow()
    due = parse(req["due_at"])
    end = parse(req["closed_at"]) or now
    if due is None:
        return "none", None
    remaining = (due - end).total_seconds() / 86400
    if req["closed_at"]:
        return ("met" if remaining >= 0 else "missed"), remaining
    if remaining < 0:
        return "breached", remaining
    return ("at-risk" if remaining < 1.5 else "on-track"), remaining
