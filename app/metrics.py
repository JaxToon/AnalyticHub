"""Operational metrics for service owners (FR-018, PRD section 16)."""
from collections import Counter
from datetime import timedelta
from statistics import median, quantiles

from .db import iso, parse, utcnow
from .workflow import REQUEST_TYPES, TERMINAL, sla_state


def _pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def compute(conn):
    now = utcnow()
    reqs = conn.execute("SELECT * FROM requests").fetchall()
    events = conn.execute("SELECT * FROM request_events ORDER BY at").fetchall()
    by_req = {}
    for e in events:
        by_req.setdefault(e["request_id"], []).append(e)

    open_reqs = [r for r in reqs if r["status"] not in TERMINAL]
    closed = [r for r in reqs if r["closed_at"]]

    triage_h, decision_d, fulfil_d, lead_d = [], [], [], []
    for r in reqs:
        evs = by_req.get(r["id"], [])
        created = parse(r["created_at"])
        first_human = next((e for e in evs if e["actor_id"] not in ("system", r["requester_id"])
                            and e["action"] != "comment"), None)
        if first_human:
            triage_h.append((parse(first_human["at"]) - created).total_seconds() / 3600)
        approved = next((e for e in evs if e["to_status"] == "Approved – Awaiting Fulfilment"), None)
        if approved:
            decision_d.append((parse(approved["at"]) - created).total_seconds() / 86400)
            done = next((e for e in evs if e["to_status"] in ("Provisioned", "Delivered", "Review/UAT")
                         and e["at"] > approved["at"]), None)
            if done:
                fulfil_d.append((parse(done["at"]) - parse(approved["at"])).total_seconds() / 86400)
        if r["closed_at"] and r["resolution"] in ("completed", "reused-existing"):
            lead_d.append((parse(r["closed_at"]) - created).total_seconds() / 86400)

    sla_closed = [sla_state(r, now)[0] for r in closed if r["resolution"] != "cancelled"]
    sla_open = Counter(sla_state(r, now)[0] for r in open_reqs)

    aging = Counter()
    for r in open_reqs:
        age = (now - parse(r["created_at"])).days
        bucket = "0–3 d" if age <= 3 else "4–7 d" if age <= 7 else "8–14 d" if age <= 14 else "15+ d"
        aging[bucket] += 1

    weeks = []
    for i in range(7, -1, -1):
        start = now - timedelta(days=7 * (i + 1))
        end = now - timedelta(days=7 * i)
        weeks.append({"label": end.strftime("%d %b"),
                      "count": sum(1 for r in reqs if start < parse(r["created_at"]) <= end)})

    assets = conn.execute("SELECT * FROM assets").fetchall()
    mandatory = ("owner_id", "steward_id", "description", "classification", "refresh", "quality_status", "allowed_use")
    complete = sum(1 for a in assets if all(a[f] for f in mandatory))
    dashboards = conn.execute("SELECT * FROM dashboards").fetchall()
    active_dash = [d for d in dashboards if d["lifecycle"] in ("published", "under review")]
    dash_ok = sum(1 for d in active_dash if d["owner_id"] and d["description"] and d["domain_id"] and d["sync_status"] == "ok")
    terms = conn.execute("SELECT status FROM terms").fetchall()

    searches = conn.execute("SELECT * FROM search_log").fetchall()
    lat = [s["latency_ms"] for s in searches]
    pct = quantiles(lat, n=100, method="inclusive") if len(lat) > 1 else [lat[0] if lat else 0.0] * 99

    dup_c = [r for r in reqs if r["type"] in ("B", "C", "D")]
    reopened = sum(1 for e in events if e["action"] == "raise_issue")
    ent = conn.execute("SELECT COUNT(*) c FROM entitlements WHERE revoked_at IS NULL AND expires_at > ?",
                       (iso(now),)).fetchone()["c"]
    expiring = conn.execute("SELECT COUNT(*) c FROM entitlements WHERE revoked_at IS NULL AND expires_at > ?"
                            " AND expires_at <= ?", (iso(now), iso(now + timedelta(days=14)))).fetchone()["c"]
    prov_fail = conn.execute("SELECT COUNT(*) c FROM fulfilment_tasks WHERE state='failed'").fetchone()["c"]
    denied = conn.execute("SELECT COUNT(*) c FROM audit_events WHERE result='denied'").fetchone()["c"]

    return {
        "total_requests": len(reqs),
        "open": len(open_reqs),
        "by_status": Counter(r["status"] for r in open_reqs).most_common(),
        "by_type": [(REQUEST_TYPES[t][0], c) for t, c in sorted(Counter(r["type"] for r in reqs).items())],
        "by_team": Counter(r["team"] for r in open_reqs).most_common(),
        "median_triage_h": round(median(triage_h), 1) if triage_h else 0,
        "median_decision_d": round(median(decision_d), 1) if decision_d else 0,
        "median_fulfil_d": round(median(fulfil_d), 1) if fulfil_d else 0,
        "median_lead_d": round(median(lead_d), 1) if lead_d else 0,
        "sla_attainment": _pct(sla_closed.count("met"), len(sla_closed)),
        "sla_open": dict(sla_open),
        "aging": [(b, aging.get(b, 0)) for b in ("0–3 d", "4–7 d", "8–14 d", "15+ d")],
        "weeks": weeks,
        "rejected_rate": _pct(sum(1 for r in reqs if r["status"] == "Rejected"), len(closed)),
        "reopened": reopened,
        "duplicates_prevented": sum(1 for r in reqs if r["resolution"] == "reused-existing"),
        "duplicate_rate": _pct(sum(1 for r in dup_c if r["resolution"] == "reused-existing"), len(dup_c)),
        "catalog_coverage": _pct(complete, len(assets)),
        "catalog_assets": len(assets),
        "dashboard_discoverability": _pct(dash_ok, len(active_dash)),
        "dashboards_active": len(active_dash),
        "terms_approved": sum(1 for t in terms if t["status"] == "Approved"),
        "terms_total": len(terms),
        "searches": len(searches),
        "search_success": _pct(sum(1 for s in searches if s["clicked"]), len(searches)),
        "zero_result": _pct(sum(1 for s in searches if s["result_count"] == 0), len(searches)),
        "p50_ms": round(pct[49], 1),
        "p95_ms": round(pct[94], 1),
        "active_entitlements": ent,
        "expiring_14d": expiring,
        "provision_failures": prov_fail,
        "denied_attempts": denied,
    }
