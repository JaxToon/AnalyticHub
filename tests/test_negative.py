"""Negative / control scenarios — PRD §15.3, §9.3, §14.3 and P0 security requirements."""
import re
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from app import audit
from app.workflow import APPROVED_WAITING

from .conftest import status_of, submit_access


def test_unauthenticated_users_cannot_use_portal_services(app, evidence):
    evidence("FR-001", "Unauthenticated users are redirected to sign-in for every portal service")
    anon = TestClient(app, follow_redirects=False)
    for path in ["/", "/search?q=npl", "/catalog", "/catalog/AS-001", "/glossary", "/analytics", "/requests/new",
                 "/workspace", "/requests/REQ-2026-0001", "/mock-tableau/views/DB-001", "/audit", "/admin", "/api/suggest?q=casa"]:
        r = anon.get(path)
        assert r.status_code == 303 and r.headers["location"].startswith("/login"), path


def test_unauthorised_user_cannot_open_tableau_view_by_url(login, db, evidence):
    evidence("§15.3-N1, §9.3, FR-011", "Unauthorised user cannot open a Tableau view by pasting / guessing its URL")
    rina = login("rina")
    assert rina.get("/analytics/DB-002").status_code == 200        # listing is visible…
    assert rina.get("/mock-tableau/views/DB-002").status_code == 403  # …but grants nothing
    restricted = rina.get("/mock-tableau/views/DB-006")  # Restricted: not even its existence is confirmed
    assert restricted.status_code == 404 and "Treasury Liquidity" not in restricted.text
    denied = db.execute("SELECT COUNT(*) c FROM audit_events WHERE action='tableau.open_view' AND result='denied'"
                        " AND actor_id='rina'").fetchone()["c"]
    assert denied == 2


def test_restricted_assets_hidden_from_search_listing_suggestions_and_url(login, evidence):
    evidence("FR-002, §7.2, §14.3", "Restricted metadata is invisible in search, listing, suggestions and direct URL")
    rina = login("rina")
    assert "Treasury FX Positions" not in rina.get("/search?q=fx positions treasury").text
    assert "Customer Master" not in rina.get("/catalog").text
    assert "AS-009" not in rina.get("/api/suggest?q=customer master cif").text
    assert rina.get("/catalog/AS-008").status_code == 404
    assert rina.get("/analytics/DB-006").status_code == 404
    assert login("dewi").get("/catalog/AS-009").status_code == 200  # domain owner can discover it


def test_confidential_field_metadata_hidden_without_clearance(login, evidence):
    evidence("FR-002, FR-004", "Field-level schema of Confidential assets hidden from users without clearance")
    assert "casa_balance_idr" not in login("rina").get("/catalog/AS-001").text
    assert "casa_balance_idr" in login("budi").get("/catalog/AS-001").text


def test_user_cannot_view_another_users_request(login, evidence):
    evidence("§15.3-N2", "User cannot view another user's request or its result link")
    assert login("rina").get("/requests/REQ-2026-0001").status_code == 404
    assert login("budi").get("/requests/REQ-2026-0019").status_code == 404


def test_requester_cannot_see_internal_notes(login, evidence):
    evidence("FR-007", "Requester sees next action but not restricted internal notes")
    login("maya").post("/requests/REQ-2026-0017/comment", {"body": "Internal: check capacity with Hendra", "internal": "1"})
    assert "check capacity" not in login("rina").get("/requests/REQ-2026-0017").text
    assert "check capacity" in login("maya").get("/requests/REQ-2026-0017").text


def test_user_cannot_edit_glossary_term_without_privilege(login, db, evidence):
    evidence("§15.3-N3", "User cannot edit an approved glossary term without assigned privilege")
    r = login("rina").post("/glossary/TM-001/propose", {"definition": "Hacked", "change_note": "x"})
    assert r.status_code == 403
    assert db.execute("SELECT COUNT(*) c FROM term_revisions WHERE term_id='TM-001'").fetchone()["c"] == 1


def test_author_cannot_approve_own_definition_change(login, db, evidence):
    evidence("§4, §11.1 SoD", "Definition author cannot approve their own revision")
    rev = db.execute("SELECT id FROM term_revisions WHERE status='in_review'").fetchone()["id"]
    assert login("sari").post(f"/glossary/revisions/{rev}/decide", {"decision": "approve", "rationale": "self"}).status_code == 403


def test_requester_cannot_approve_own_request(login, db, evidence):
    evidence("§11.1 SoD, FR-008", "Owner-as-requester cannot self-approve; request routes to the delegate approver")
    dewi = login("dewi")
    req_id = submit_access(dewi, "asset:AS-012")
    dewi.act(req_id, "approve", "self approval")
    assert status_of(db, req_id) == "Awaiting Approval"
    assert db.execute("SELECT approver_id FROM requests WHERE id=?", (req_id,)).fetchone()["approver_id"] == "agus"
    login("agus").act(req_id, "approve", "Delegate approval.")
    assert db.execute("SELECT approver_id FROM decisions WHERE request_id=?", (req_id,)).fetchone()["approver_id"] == "agus"


def test_admin_cannot_approve_or_fulfil_requests(login, db, evidence):
    evidence("§15.3-N8, §7.7", "Admin attempting a prohibited approval is denied and the attempt is logged")
    tono = login("tono")
    tono.act("REQ-2026-0020", "approve", "Admin override")
    tono.act("REQ-2026-0016", "provision", "")
    assert status_of(db, "REQ-2026-0020") == "Awaiting Approval"
    assert status_of(db, "REQ-2026-0016") == "Provision Failed"
    denied = db.execute("SELECT COUNT(*) c FROM audit_events WHERE actor_id='tono' AND result='denied'").fetchone()["c"]
    assert denied == 2


def test_non_admin_cannot_change_configuration(login, db, evidence):
    evidence("FR-002, §7.7", "Non-admin users cannot open admin pages or change routing / SLA / outage settings")
    budi = login("budi")
    assert budi.get("/admin").status_code == 403
    assert budi.post("/admin/service/A", {"sla_days": "1", "active": "1"}).status_code == 403
    assert db.execute("SELECT sla_days FROM service_definitions WHERE type='A'").fetchone()["sla_days"] == 5


def test_iam_outage_fails_closed_on_provisioning(login, db, evidence):
    evidence("§15.3-N4, §11.2", "IAM outage does not fall back to allow — provisioning fails safely, nothing granted")
    login("tono").post("/admin/flags", {"key": "iam_outage", "value": "on"})
    login("hendra").act("REQ-2026-0016", "provision", "")
    assert status_of(db, "REQ-2026-0016") == "Provision Failed"
    assert db.execute("SELECT COUNT(*) c FROM entitlements WHERE request_id='REQ-2026-0016'").fetchone()["c"] == 0


def test_tableau_outage_denies_view_even_for_entitled_user(login, evidence):
    evidence("§15.3-N4, §9.3", "Tableau / identity outage blocks views instead of failing open")
    rina = login("rina")
    assert rina.get("/mock-tableau/views/DB-001").status_code == 200
    login("tono").post("/admin/flags", {"key": "tableau_outage", "value": "on"})
    r = rina.get("/mock-tableau/views/DB-001")
    assert r.status_code == 403 and "temporarily unavailable" in r.text


def test_revoked_entitlement_is_not_retained(login, db, evidence):
    evidence("§15.3-N5, §9.3", "Revoked access is effective at source and not retained by the portal")
    rina = login("rina")
    req_id = submit_access(rina, "dashboard:DB-002")
    login("agus").act(req_id, "approve")
    login("maya").act(req_id, "provision", "")
    assert rina.get("/mock-tableau/views/DB-002").status_code == 200
    ent = db.execute("SELECT id FROM entitlements WHERE request_id=?", (req_id,)).fetchone()["id"]
    assert login("dewi").post(f"/entitlements/{ent}/revoke", {"reason": "x"}).status_code == 403  # not her domain
    login("agus").post(f"/entitlements/{ent}/revoke", {"reason": "Role change"})
    assert rina.get("/mock-tableau/views/DB-002").status_code == 403


def test_customer_identifiers_in_free_text_are_blocked_or_redacted(login, db, evidence):
    evidence("§15.3-N6, FR-013", "Customer/account identifiers in free text are blocked; redaction never leaks to notifications")
    rina = login("rina")
    before = db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
    data = {"target": "dashboard:DB-002", "purpose": "Check customer NIK 3174012508900003 and account 0123456789",
            "task": "Review", "scope": "One region", "duration_days": "30", "intended_use": "Ad-hoc analysis"}
    r = rina.post("/requests/new/A", data)
    assert r.status_code == 422 and "NIK" in r.text
    assert db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"] == before
    r = rina.post("/requests/new/A", {**data, "_redact": "1"})
    assert r.status_code == 303
    row = db.execute("SELECT * FROM requests ORDER BY seq DESC LIMIT 1").fetchone()
    assert "3174012508900003" not in row["purpose"] and "0123456789" not in row["purpose"] and row["pii_redacted"] == 1
    dump = " ".join(str(tuple(x)) for t in ("notifications", "audit_events", "request_events") for x in db.execute(f"SELECT * FROM {t}"))
    assert "3174012508900003" not in dump and "0123456789" not in dump


def test_failed_metadata_sync_flags_stale_and_not_certified(login, db, evidence):
    evidence("§15.3-N7, §9.2-L3", "Failed metadata sync is flagged and does not show assets as current/certified")
    tono = login("tono")
    tono.post("/admin/flags", {"key": "tableau_outage", "value": "on"})
    tono.post("/admin/sync")
    assert db.execute("SELECT COUNT(*) c FROM dashboards WHERE sync_status='ok'").fetchone()["c"] == 0
    page = login("rina").get("/analytics")
    assert "certification unverified" in page.text and "Certified</span>" not in page.text


def test_errors_do_not_leak_internal_details(login, evidence):
    evidence("FR-014", "Error pages show no stack traces, SQL or internals — only a correlation reference")
    rina = login("rina")
    for r in (rina.get("/catalog/NOPE"), rina.get("/requests/REQ-9999-0000"), rina.post("/glossary/revisions/abc/decide")):
        assert r.status_code in (400, 404, 422)
        assert "Traceback" not in r.text and "sqlite" not in r.text.lower() and "Reference:" in r.text


def test_forged_cross_site_post_is_rejected(login, db, evidence):
    evidence("§11.1 anti-CSRF", "State-changing requests without a valid CSRF token are rejected")
    agus = login("agus")
    req_id = "REQ-2026-0020"
    r = agus.client.post(f"/requests/{req_id}/action", data={"action": "approve", "note": "forged"})
    assert r.status_code == 403 and status_of(db, req_id) == "Awaiting Approval"


def test_audit_log_is_append_only_and_tamper_evident(db, evidence):
    evidence("§14.3, FR-012", "Audit trail cannot be modified, and tampering is detectable")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE audit_events SET result='success' WHERE seq=1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM audit_events WHERE seq=1")
    db.execute("DROP TRIGGER audit_no_update")  # simulate a privileged attacker bypassing the DB control
    db.execute("UPDATE audit_events SET actor_id='someone-else' WHERE seq=2")
    assert audit.verify(db) == {"ok": False, "count": 1, "broken_at": 2}


def test_security_headers_present(login, evidence):
    evidence("§11.1", "Content-Security-Policy, anti-framing and no-sniff headers are set")
    h = login("rina").get("/").headers
    assert "default-src 'self'" in h["content-security-policy"] and h["x-frame-options"] == "DENY"
    assert h["x-content-type-options"] == "nosniff" and h["x-correlation-id"]


def test_release_gate_signoff_restricted_to_control_owner(login, db, evidence):
    evidence("FR-015", "Production gate items can only be signed by the designated control owner")
    assert login("tono").post("/release-gates/G03/sign", {"note": "pentest ok"}).status_code == 403
    assert db.execute("SELECT status FROM release_gates WHERE id='G03'").fetchone()["status"] == "open"
    login("yusuf").post("/release-gates/G03/sign", {"note": "PT-2026-07 closed"})
    assert db.execute("SELECT status FROM release_gates WHERE id='G03'").fetchone()["status"] == "signed"


def test_dropdown_values_are_validated_server_side(login, db, evidence):
    evidence("§11.1, FR-006", "Hand-crafted form values outside the allowed options are rejected")
    before = db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
    rina = login("rina")
    for bad in ({"duration_days": "36500"}, {"duration_days": "abc"}, {"intended_use": "Anything"}):
        data = {"target": "dashboard:DB-002", "purpose": "Review", "task": "Pack", "scope": "All",
                "duration_days": "90", "intended_use": "Management reporting", **bad}
        assert rina.post("/requests/new/A", data).status_code == 422
    assert db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"] == before


def test_login_never_redirects_off_site(app, evidence):
    evidence("§11.1 open redirect", "Sign-in only redirects to same-site paths")
    for target in ("//evil.example", "/\\evil.example", "https://evil.example", "/%5Cevil.example"):
        c = TestClient(app, follow_redirects=False)
        token = re.search(r'name="csrf_token" value="([^"]+)"', c.get("/login").text).group(1)
        r = c.post("/login", data={"csrf_token": token, "uid": "rina", "next": target})
        assert r.headers["location"] in ("/", target) and not r.headers["location"].startswith(("//", "/\\", "http"))


def test_signed_gate_cannot_be_overwritten(login, db, evidence):
    evidence("FR-015, §14.3", "A release-gate sign-off is evidence and cannot be re-signed or overwritten")
    yusuf = login("yusuf")
    yusuf.post("/release-gates/G03/sign", {"note": "PT-2026-07 closed"})
    yusuf.post("/release-gates/G03/sign", {"note": "overwrite attempt"})
    assert db.execute("SELECT note FROM release_gates WHERE id='G03'").fetchone()["note"] == "PT-2026-07 closed"


def test_revocation_requires_and_records_reason(login, db, evidence):
    evidence("§8.1-8, FR-012", "Revocation needs a reason, which is stored on the entitlement")
    ent = db.execute("SELECT id FROM entitlements WHERE revoked_at IS NULL AND object_id='AS-003'").fetchone()["id"]
    agus = login("agus")
    agus.post(f"/entitlements/{ent}/revoke", {"reason": ""})
    assert db.execute("SELECT revoked_at FROM entitlements WHERE id=?", (ent,)).fetchone()["revoked_at"] is None
    agus.post(f"/entitlements/{ent}/revoke", {"reason": "Moved to another unit"})
    row = db.execute("SELECT * FROM entitlements WHERE id=?", (ent,)).fetchone()
    assert row["revoked_at"] and row["revoke_reason"] == "Moved to another unit"


def test_admin_and_auditor_cannot_comment_on_requests(login, db, evidence):
    evidence("§7.7, §4 SoD", "Oversight roles (admin, audit) are read-only on requests, including comments")
    for uid in ("tono", "lina"):
        r = login(uid).post("/requests/REQ-2026-0017/comment", {"body": "note", "internal": "1"})
        assert r.status_code == 403
    assert db.execute("SELECT COUNT(*) c FROM request_events WHERE action='comment'").fetchone()["c"] == 0


def test_concurrent_submissions_get_unique_ids_and_intact_audit(app, evidence):
    evidence("§11.2 idempotency, FR-012", "Parallel submissions get unique IDs and the audit hash chain stays intact")
    from app.db import connect
    from app.policy import load_user
    from app.workflow import create_request

    def worker(uid, target):
        conn = connect(app.state.db_path)
        user = load_user(conn, uid)
        for _ in range(8):
            create_request(conn, user, "E", {"target": target, "title": "Check", "purpose": "Values look off",
                                             "impact": "Report", "severity": "Low"})
            conn.commit()
        conn.close()

    threads = [threading.Thread(target=worker, args=a) for a in (("rina", "asset:AS-005"), ("budi", "asset:AS-004"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    conn = connect(app.state.db_path)
    ids = [r["id"] for r in conn.execute("SELECT id FROM requests")]
    assert len(ids) == len(set(ids)) == 22 + 16
    assert audit.verify(conn)["ok"]
    conn.close()


def test_approval_alone_does_not_grant_access(login, db, evidence):
    evidence("§5.5, §17", "Approved-awaiting-fulfilment does not grant any access")
    req_id = submit_access(login("rina"), "dashboard:DB-002")
    login("agus").act(req_id, "approve")
    assert status_of(db, req_id) == APPROVED_WAITING
    assert db.execute("SELECT COUNT(*) c FROM entitlements WHERE request_id=?", (req_id,)).fetchone()["c"] == 0
    assert login("rina").get("/mock-tableau/views/DB-002").status_code == 403


def test_regional_potential_map_is_not_shown_without_tableau_permission(login, evidence):
    evidence("§9.3, FR-011", "Users outside the map's Tableau groups get no hexagon data")
    r = login("budi").get("/mock-tableau/views/DB-014")
    assert r.status_code == 403 and "data-h3=" not in r.text and "Request access" in r.text


def test_basemap_tile_server_is_only_allowed_on_the_map_view(login, evidence):
    evidence("NFR 11.1", "Basemap tiles load only on the H3 map view, and only from the configured tile server")
    from app import geo
    rina = login("rina")
    assert geo.tile_origin() in rina.get("/mock-tableau/views/DB-014").headers["content-security-policy"]
    assert geo.tile_origin() not in rina.get("/mock-tableau/views/DB-001").headers["content-security-policy"]
    assert geo.tile_origin() not in rina.get("/").headers["content-security-policy"]
