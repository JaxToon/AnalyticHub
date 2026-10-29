"""Authorization rules (FR-002, FR-011). Default deny.

Catalog visibility follows the classification of the metadata itself:
- Public / Internal: discoverable and fully described to any authenticated user.
- Confidential: discoverable; field-level schema and lineage only for cleared users,
  domain owner/steward, or users with an active entitlement.
- Restricted: not discoverable at all (search, listing, direct URL -> 404) unless the user
  has Restricted clearance, is the domain owner/steward, or holds an active entitlement.
Seeing metadata never grants access to data contents — that is decided by the source system.
"""
from dataclasses import dataclass, field

from .db import get_flag, iso, utcnow

LEVELS = {"Public": 0, "Internal": 1, "Confidential": 2, "Restricted": 3}

ROLE_LABELS = {
    "requester": "Business requester",
    "analyst": "Data analyst",
    "data_owner": "Data owner",
    "steward": "Data steward",
    "platform": "Data Platform Engineering",
    "bi": "BI / Analytics service owner",
    "analytics": "Analytics / Data science",
    "governance": "Security & Privacy reviewer",
    "admin": "Portal administrator",
    "auditor": "Internal audit",
}

TEAM_LABELS = {
    "platform": "Data Platform Engineering",
    "bi": "BI & Reporting",
    "analytics": "Analytics & Data Science",
    "steward": "Data Stewardship",
}


@dataclass
class User:
    id: str
    name: str
    title: str
    unit: str
    roles: set
    clearance: str
    groups: set
    owned_domains: set = field(default_factory=set)
    stewarded_domains: set = field(default_factory=set)

    def has(self, *roles) -> bool:
        return bool(self.roles & set(roles))

    @property
    def level(self) -> int:
        return LEVELS.get(self.clearance, 0)

    @property
    def primary_role(self) -> str:
        for r in ("admin", "auditor", "governance", "data_owner", "steward", "platform", "bi",
                  "analyst", "requester"):
            if r in self.roles:
                return ROLE_LABELS[r]
        return "User"


def load_user(conn, user_id) -> User | None:
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return None
    owned = {r["id"] for r in conn.execute("SELECT id FROM domains WHERE owner_id=?", (user_id,))}
    stewarded = {r["id"] for r in conn.execute("SELECT id FROM domains WHERE steward_id=?", (user_id,))}
    return User(row["id"], row["name"], row["title"], row["unit"], set(row["roles"].split(",")),
                row["clearance"], set(filter(None, row["groups_"].split(","))), owned, stewarded)


def is_custodian(user: User, domain_id: str) -> bool:
    return domain_id in user.owned_domains or domain_id in user.stewarded_domains


def active_entitlement(conn, user_id, object_type, object_id):
    return conn.execute(
        "SELECT * FROM entitlements WHERE user_id=? AND object_type=? AND object_id=?"
        " AND revoked_at IS NULL AND (expires_at IS NULL OR expires_at > ?)"
        " ORDER BY granted_at DESC LIMIT 1",
        (user_id, object_type, object_id, iso(utcnow())),
    ).fetchone()


def can_discover(conn, user: User, obj, object_type="asset") -> bool:
    if obj is None:
        return False
    if obj["classification"] != "Restricted":
        return True
    return (user.level >= 3 or is_custodian(user, obj["domain_id"])
            or active_entitlement(conn, user.id, object_type, obj["id"]) is not None)


def can_see_details(conn, user: User, obj, object_type="asset") -> bool:
    if not can_discover(conn, user, obj, object_type):
        return False
    if LEVELS[obj["classification"]] <= 1:
        return True
    return (user.level >= LEVELS[obj["classification"]] or is_custodian(user, obj["domain_id"])
            or active_entitlement(conn, user.id, object_type, obj["id"]) is not None)


def tableau_permits(conn, user: User, dashboard) -> tuple[bool, str]:
    """Simulates Tableau's own permission check. The portal never overrides this.

    Fails closed: if the identity / Tableau dependency is down, access is denied.
    """
    if get_flag(conn, "tableau_outage") == "on" or get_flag(conn, "iam_outage") == "on":
        return False, "unavailable"
    if dashboard["lifecycle"] == "retired":
        return False, "retired"
    permitted = set(filter(None, (dashboard["permitted_groups"] or "").split(",")))
    if user.groups & permitted:
        return True, "group"
    if active_entitlement(conn, user.id, "dashboard", dashboard["id"]):
        return True, "entitlement"
    return False, "denied"


def can_view_request(user: User, req) -> bool:
    if req is None:
        return False
    if user.id in (req["requester_id"], req["approver_id"]):
        return True
    if req["team"] in user.roles:
        return True
    if "governance" in user.roles and "governance" in (req["required_approvals"] or ""):
        return True
    return user.has("auditor", "admin")  # read-only oversight; no workflow actions


def can_view_internal_notes(user: User, req) -> bool:
    return can_view_request(user, req) and user.id != req["requester_id"]


def can_view_audit(user: User) -> bool:
    return user.has("auditor", "governance")


def can_view_service_metrics(user: User) -> bool:
    return user.has("admin", "bi", "platform", "auditor", "governance", "data_owner")


def can_admin(user: User) -> bool:
    return user.has("admin")
