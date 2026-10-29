"""Global search across catalog assets, glossary terms and the Tableau inventory (FR-003).

Results are filtered by the caller's authorization before scoring, so restricted items never
appear in counts, snippets or suggestions. Snippets come from approved description fields only.
"""
import re
import time

from .db import iso, utcnow
from .policy import can_discover

# Curated bilingual synonyms (business vocabulary <-> catalog vocabulary).
SYNONYMS = [
    {"npl", "non performing loan", "non-performing loan", "kredit bermasalah", "kredit macet", "kolektibilitas"},
    {"casa", "current account saving account", "giro tabungan", "dana murah"},
    {"dpk", "dana pihak ketiga", "third party funds", "deposits", "simpanan", "funding"},
    {"customer", "nasabah", "cif", "client"},
    {"loan", "kredit", "pinjaman", "lending", "credit"},
    {"branch", "cabang", "kantor cabang", "outlet"},
    {"ldr", "loan to deposit ratio"},
    {"nim", "net interest margin"},
    {"dpd", "days past due", "delinquency", "tunggakan"},
    {"sme", "umkm", "ukm", "msme"},
    {"complaint", "keluhan", "pengaduan"},
    {"fx", "valas", "foreign exchange", "kurs"},
    {"atm", "mesin atm", "e-channel"},
    {"digital", "mobile banking", "internet banking", "e-channel"},
    {"pl", "p&l", "profit and loss", "laba rugi", "income statement"},
    {"headcount", "pegawai", "employee", "karyawan"},
]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9& ]+", " ", (text or "").lower()).strip()


def expand(query: str) -> list[str]:
    q = _norm(query)
    terms = {q} | set(q.split())
    for group in SYNONYMS:
        if any(s == q or s in q.split() or (len(s) > 4 and s in q) for s in group):
            terms |= group
    return [t for t in terms if len(t) >= 2]


def _score(fields: dict, terms: list[str]) -> float:
    weights = {"title": 5, "name": 4, "abbr": 6, "synonyms": 3, "tags": 2, "domain": 1.5,
               "description": 1, "owner": 1}
    score = 0.0
    for key, text in fields.items():
        t = _norm(text)
        for term in terms:
            if term and term in t:
                score += weights.get(key, 1) * (2 if t == term else 1)
    return score


def search(conn, user, query: str, kind: str | None = None, limit: int = 50, log: bool = True):
    started = time.perf_counter()
    terms = expand(query)
    results = []
    if not terms:
        return [], None
    domains = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM domains")}
    owners = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM users")}

    if kind in (None, "", "asset"):
        for a in conn.execute("SELECT * FROM assets"):
            if not can_discover(conn, user, a, "asset"):
                continue
            s = _score({"title": a["title"], "name": a["name"], "tags": a["tags"], "description": a["description"],
                        "domain": domains.get(a["domain_id"]), "owner": owners.get(a["owner_id"])}, terms)
            if s:
                results.append(dict(kind="asset", id=a["id"], title=a["title"], subtitle=a["name"],
                                    type=a["type"], snippet=a["description"], domain=domains.get(a["domain_id"]),
                                    classification=a["classification"], status=a["lifecycle"],
                                    url=f"/catalog/{a['id']}", score=s))
    if kind in (None, "", "term"):
        for t in conn.execute("SELECT * FROM terms"):
            s = _score({"title": t["term"], "abbr": t["abbreviation"], "synonyms": t["synonyms"],
                        "description": t["definition"], "domain": domains.get(t["domain_id"])}, terms)
            if s:
                results.append(dict(kind="term", id=t["id"], title=t["term"], subtitle=t["abbreviation"],
                                    type="Business term", snippet=t["definition"], domain=domains.get(t["domain_id"]),
                                    classification=None, status=t["status"], url=f"/glossary/{t['id']}", score=s))
    if kind in (None, "", "dashboard"):
        for d in conn.execute("SELECT * FROM dashboards"):
            if not can_discover(conn, user, d, "dashboard"):
                continue
            s = _score({"title": d["title"], "tags": d["tags"], "description": d["description"],
                        "name": d["workbook"], "domain": domains.get(d["domain_id"])}, terms)
            if d["lifecycle"] in ("deprecated", "retired"):
                s *= 0.4
            if s:
                results.append(dict(kind="dashboard", id=d["id"], title=d["title"], subtitle=d["workbook"],
                                    type="Tableau dashboard", snippet=d["description"],
                                    domain=domains.get(d["domain_id"]), classification=d["classification"],
                                    status=d["lifecycle"], url=f"/analytics/{d['id']}", score=s,
                                    certified=bool(d["certified"])))
    results.sort(key=lambda r: -r["score"])
    results = results[:limit]
    latency = (time.perf_counter() - started) * 1000
    search_id = None
    if log:
        cur = conn.execute("INSERT INTO search_log(at, user_id, query, result_count, latency_ms) VALUES (?,?,?,?,?)",
                           (iso(utcnow()), user.id, query[:120], len(results), latency))
        search_id = cur.lastrowid
    return results, search_id


def record_click(conn, search_id, user_id):
    if search_id and str(search_id).isdigit():
        conn.execute("UPDATE search_log SET clicked=1 WHERE id=? AND user_id=?", (int(search_id), user_id))
