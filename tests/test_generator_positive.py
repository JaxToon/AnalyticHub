"""AI Dashboard Generator — positive scenarios (PRD v0.2 §15.3, FR-023 .. FR-031)."""
import json

from app import generator
from app.policy import load_user

from .conftest import draft_id, generate, status_of


def _spec(db, gen_id):
    d = db.execute("SELECT * FROM gen_drafts WHERE id=?", (gen_id,)).fetchone()
    return d, generator.current_spec(db, d)


def test_generator_builds_schema_valid_spec_from_metadata_only(login, db, evidence):
    evidence("FR-023, §15.3-P6, §15.2", "Generator turns a business question + visible metadata into a schema-valid draft spec")
    budi = login("budi")
    gen_id = draft_id(generate(budi, "Gross NPL ratio per wilayah, bulanan", "AS-004"))
    d, spec = _spec(db, gen_id)
    package = generator.metadata_package(db, load_user(db, "budi"), ["AS-004"])
    assert generator.validate(spec, package) == []
    assert spec["spec_version"] == generator.SPEC_VERSION and spec["draft"] is True
    assert {c["type"] for c in spec["components"]} == {"kpi", "line", "bar", "table"}
    refs = json.dumps(spec["components"])
    assert "AS-004.gross_npl_ratio" in refs and "AS-004.region" in refs
    line = next(c for c in spec["components"] if c["type"] == "line")
    assert line["x"] == {"field": "AS-004.month_end", "grain": "month"}
    assert spec["provenance"]["model"] is None and spec["provenance"]["planner"] == generator.PLANNER
    page = budi.get(f"/generator/{gen_id}")
    assert page.status_code == 200 and "AS-004.gross_npl_ratio" in page.text and "Assumptions" in page.text


def test_preview_is_persistently_labelled_synthetic(login, db, evidence):
    evidence("FR-024, §15.3-N5", "Every preview, including filtered views, carries the SYNTHETIC DATA — NOT Bank ACTUALS label")
    budi = login("budi")
    gen_id = draft_id(generate(budi, "NPL amount by region", "AS-004"))
    _, spec = _spec(db, gen_id)
    for url in (f"/generator/{gen_id}", f"/generator/{gen_id}?f0=Regional office B", f"/generator/{gen_id}?f2=Last 3 periods"):
        page = budi.get(url).text
        assert generator.SYNTHETIC_LABEL in page
        charts = sum(1 for c in spec["components"] if c["type"] in ("line", "bar"))
        assert page.count(">SYNTHETIC</text>") == charts                # watermark in every chart
        assert page.count('class="syn-tag"') >= len(spec["components"]) - charts  # tag on every KPI and table
    filtered = budi.get(f"/generator/{gen_id}?f0=Regional office B").text
    assert 'fill="#c2410c"' in filtered  # the selected category is highlighted: the preview is interactive


def test_missing_metadata_becomes_questions_not_invented_logic(login, db, evidence):
    evidence("FR-026, §15.2", "Unknown terms and unapproved KPI formulas are shown as open questions, never invented")
    gen_id = draft_id(generate(login("budi"), "CASA ratio per cabang harian dan churn", "AS-001"))
    _, spec = _spec(db, gen_id)
    questions = " ".join(spec["questions"])
    assert "'churn' was not found" in questions
    assert "CASA Ratio" in questions and "must confirm" in questions
    assert "churn" not in json.dumps(spec["components"]) + json.dumps(spec["filters"])
    assert any("end-of-period" in a for a in spec["assumptions"])  # balances are not summed over time


def test_user_edit_is_validated_and_versioned(login, db, evidence):
    evidence("§15.3-P7, FR-031", "User edits a draft; each saved version and its author are traceable")
    budi = login("budi")
    gen_id = draft_id(generate(budi, "NPL amount by region", "AS-004"))
    d, spec = _spec(db, gen_id)
    edited = {"title": "NPL by region — committee view",
              "components": [c for c in spec["components"] if c["type"] != "table"], "filters": spec["filters"]}
    r = budi.post(f"/generator/{gen_id}/edit", {"spec_json": json.dumps(edited), "note": "Removed table"})
    assert r.status_code == 303
    d, spec2 = _spec(db, gen_id)
    assert d["version"] == 2 and spec2["title"] == "NPL by region — committee view"
    assert spec2["assumptions"] == spec["assumptions"] and spec2["draft"] is True  # uncertainty cannot be edited away
    versions = db.execute("SELECT version, source, author_id FROM gen_versions WHERE draft_id=? ORDER BY version",
                          (gen_id,)).fetchall()
    assert [tuple(v) for v in versions] == [(1, "generated", "budi"), (2, "user-edit", "budi")]
    assert db.execute("SELECT COUNT(*) c FROM audit_events WHERE action='generator.revise' AND object_id=?",
                      (gen_id,)).fetchone()["c"] == 1


def test_submitted_draft_goes_through_owner_review_workflow(login, db, evidence):
    evidence("FR-030, §8.3", "Submitting a draft opens a Type C request for BI triage and data-owner approval; the draft is locked")
    budi = login("budi")
    gen_id = draft_id(generate(budi, "NPL amount by region", "AS-004"))
    r = budi.post(f"/generator/{gen_id}/submit")
    assert r.status_code == 303 and "/requests/REQ-" in r.headers["location"]
    req_id = r.headers["location"].rsplit("/", 1)[-1]
    req = db.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
    assert (req["type"], req["team"], status_of(db, req_id)) == ("C", "bi", "Triage")
    assert json.loads(req["required_approvals"]) == ["data_owner"]
    assert json.loads(req["details_json"])["ai_draft"] == f"{gen_id} v1"
    assert db.execute("SELECT status FROM gen_drafts WHERE id=?", (gen_id,)).fetchone()["status"] == "Submitted for review"
    budi.post(f"/generator/{gen_id}/edit", {"spec_json": "{}"})
    assert db.execute("SELECT version FROM gen_drafts WHERE id=?", (gen_id,)).fetchone()["version"] == 1  # locked
    maya = login("maya")  # BI triage sees the draft through the request it is attached to
    assert maya.get(f"/generator/{gen_id}").status_code == 200
    assert gen_id in maya.get(f"/requests/{req_id}").text
