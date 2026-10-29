"""Positive scenarios — PRD §15.3 and P0 functional requirements."""
from app import audit
from app.workflow import APPROVED_WAITING

from .conftest import status_of, submit_access


def test_entitled_user_finds_and_opens_authorised_tableau_view(login, evidence):
    evidence("§15.3-P1, FR-003, FR-010", "Entitled user searches metadata and opens an authorised Tableau view")
    rina = login("rina")
    page = rina.get("/search?q=funding performance")
    assert "Retail Funding Performance" in page.text
    assert rina.get("/mock-tableau/views/DB-001").status_code == 200


def test_search_understands_bilingual_business_synonyms(login, evidence):
    evidence("FR-003, §7.2", "Search matches Bahasa Indonesia synonyms (kredit macet → NPL)")
    page = login("budi").get("/search?q=kredit macet")
    assert "Non-Performing Loan" in page.text and "NPL Monitoring by Region" in page.text


def test_requester_submits_access_request_and_receives_id(login, db, evidence):
    evidence("§15.3-P2, FR-006", "Requester submits a complete access request and receives a request ID")
    req_id = submit_access(login("rina"), "dashboard:DB-002")
    assert req_id.startswith("REQ-")
    row = db.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
    assert row["status"] == "Awaiting Approval" and row["approver_id"] == "agus"


def test_owner_decision_records_approver_rationale_and_policy(login, db, evidence):
    evidence("§15.3-P3, FR-007, FR-008", "Data owner approves with rationale; decision evidence and history recorded")
    req_id = submit_access(login("rina"), "dashboard:DB-002")
    login("agus").act(req_id, "approve", "Fits management-reporting purpose.")
    assert status_of(db, req_id) == APPROVED_WAITING
    d = db.execute("SELECT * FROM decisions WHERE request_id=?", (req_id,)).fetchone()
    assert (d["approver_id"], d["outcome"], d["rationale"]) == ("agus", "approved", "Fits management-reporting purpose.")
    assert d["at"] and d["policy_version"].startswith("ACCESS-POL")
    events = [e["to_status"] for e in db.execute("SELECT to_status FROM request_events WHERE request_id=?", (req_id,))]
    assert events == ["Submitted", "Awaiting Approval", APPROVED_WAITING]


def test_confidential_asset_requires_conditional_security_review(login, db, evidence):
    evidence("§5.6, §8.1-4", "Confidential asset adds a conditional Security & Privacy review after the owner")
    req_id = submit_access(login("budi"), "asset:AS-007")
    login("dewi").act(req_id, "approve")
    assert status_of(db, req_id) == "Awaiting Approval"  # owner alone is not enough
    login("yusuf").act(req_id, "approve", "Pseudonymised; aggregated outputs only.")
    assert status_of(db, req_id) == APPROVED_WAITING


def test_fulfilment_is_recorded_separately_and_closes_loop(login, db, evidence):
    evidence("§15.3-P4, §8.1-6/7", "Provisioning recorded separately from approval; access then works at source")
    rina = login("rina")
    req_id = submit_access(rina, "dashboard:DB-002")
    login("agus").act(req_id, "approve")
    assert rina.get("/mock-tableau/views/DB-002").status_code == 403  # approved ≠ provisioned
    login("maya").act(req_id, "provision", "")
    assert status_of(db, req_id) == "Provisioned"
    task = db.execute("SELECT * FROM fulfilment_tasks WHERE request_id=?", (req_id,)).fetchone()
    assert task["state"] == "provisioned" and task["evidence_ref"].startswith("TBL-GRP-")
    assert rina.get("/mock-tableau/views/DB-002").status_code == 200
    rina.act(req_id, "confirm", "")
    assert status_of(db, req_id) == "Closed"


def test_steward_updates_definition_through_review_workflow(login, db, evidence):
    evidence("§15.3-P5, FR-005", "Steward changes a definition via draft → owner review → publish")
    login("sari").post("/glossary/TM-005/propose", {"definition": "Customer funds in giro, tabungan and deposito.",
                                                    "change_note": "Clarify product scope"})
    term = db.execute("SELECT * FROM terms WHERE id='TM-005'").fetchone()
    assert term["version"] == 1  # unchanged until approved
    rev = db.execute("SELECT id FROM term_revisions WHERE term_id='TM-005' AND status='in_review'").fetchone()
    login("dewi").post(f"/glossary/revisions/{rev['id']}/decide", {"decision": "approve", "rationale": "Agreed."})
    term = db.execute("SELECT * FROM terms WHERE id='TM-005'").fetchone()
    assert term["version"] == 2 and term["definition"].startswith("Customer funds in giro")


def test_request_form_recommends_existing_dashboards_before_submission(login, db, evidence):
    evidence("FR-019, §5.1", "New-dashboard form recommends existing views before a duplicate is created")
    before = db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
    data = {"title": "CASA funding performance by branch", "purpose": "Track CASA by branch.", "decision": "Funding review",
            "audience": "Regional heads", "kpis": "CASA", "refresh": "Daily", "domain_id": "RET",
            "confidentiality": "Internal", "priority": "Medium"}
    r = login("rina").post("/requests/new/C", data)
    assert r.status_code == 200 and "Retail Funding Performance" in r.text
    assert db.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"] == before


def test_triage_can_close_request_by_reusing_existing_asset(login, db, evidence):
    evidence("§8.3-3, §16", "BI triage closes a request by linking an existing dashboard (duplicate prevented)")
    login("maya").act("REQ-2026-0017", "reuse", "Already in Retail Funding Performance.", "dashboard:DB-001")
    r = db.execute("SELECT * FROM requests WHERE id='REQ-2026-0017'").fetchone()
    assert (r["status"], r["resolution"], r["result_ref"]) == ("Closed", "reused-existing", "dashboard:DB-001")


def test_audit_trail_records_transitions_and_verifies(login, db, evidence):
    evidence("FR-012, §15.2", "Every request change is audited and the hash chain verifies")
    req_id = submit_access(login("rina"), "dashboard:DB-002")
    login("agus").act(req_id, "approve")
    actions = [r["action"] for r in db.execute("SELECT action FROM audit_events WHERE object_id=?", (req_id,))]
    assert actions == ["request.submit", "request.approve"]
    assert audit.verify(db)["ok"]


def test_notifications_carry_only_minimum_details(login, db, evidence):
    evidence("FR-017", "Notifications contain only request ID/status — never the business purpose")
    secret_purpose = "Confidential board restructuring scenario Omega"
    submit_access(login("rina"), "dashboard:DB-002", purpose=secret_purpose)
    subjects = " ".join(r["subject"] for r in db.execute("SELECT subject FROM notifications"))
    assert "Omega" not in subjects


def test_unapproved_terms_are_visibly_marked(login, evidence):
    evidence("FR-005, §15.2", "Draft / under-review definitions are visibly marked as not official")
    page = login("rina").get("/glossary/TM-009")
    assert "Draft — not official" in page.text


def test_service_owner_sees_sla_metrics(login, evidence):
    evidence("FR-018", "Service owner can view lead time, SLA attainment, backlog and reuse metrics")
    page = login("maya").get("/service/metrics")
    assert page.status_code == 200 and "SLA attainment" in page.text and "Duplicate requests prevented" in page.text


def test_regional_potential_map_aggregates_locations_into_h3_cells(login, evidence):
    evidence("§7.4, FR-010", "Regional potential map: H3 index per location matches the h3 reference and totals are kept")
    import h3
    from app import geo
    for res in geo.RESOLUTIONS:
        m = geo.hexmap("dpk", res)
        assert {c["h3"] for c in m["cells"]} == {h3.latlng_to_cell(l["lat"], l["lon"], res) for l in geo.LOCATIONS}
        assert abs(sum(c["dpk"] for c in m["cells"]) - sum(l["dpk"] for l in geo.LOCATIONS)) < 1
    bekasi = geo.hexmap("potential", 8, "Bekasi")
    assert bekasi["cells"] and all(c["wilayah"] == "Bekasi" for c in bekasi["cells"])
    page = login("rina").get("/mock-tableau/views/DB-014?wilayah=Bekasi")
    assert page.status_code == 200 and "Priority hexagons" in page.text and "Wilayah Bekasi" in page.text
