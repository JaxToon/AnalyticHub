"""AI Dashboard Generator — Phase 1, metadata-only (PRD v0.2 §7.8, §13.3, FR-023 .. FR-035).

Business question + metadata the user is allowed to see → versioned JSON dashboard specification
→ deterministic server-side validation → preview drawn by trusted templates from synthetic values.

Phase 1 boundary (FR-032): there is no database connector, query executor, data export, Tableau
publication or model provider in this code. Nothing here reads data values; the preview numbers
come from a seeded random generator and are labelled as synthetic everywhere they are shown.

No Bank-approved model gateway exists yet, so planning uses the deterministic rules fallback
(FR-027). A configured but unapproved provider is ignored — prompts are never routed to it.
"""
import hashlib
import json
import os
import random
import re
import time

from . import pii
from .db import iso, jl, utcnow, write_lock
from .policy import LEVELS, active_entitlement, can_discover, can_see_details, is_custodian
from .search import SYNONYMS, _norm

SPEC_VERSION = "dash-spec/1.0"
PLANNER = "rules-v1"
SYNTHETIC_LABEL = "SYNTHETIC DATA — NOT Bank ACTUALS"
MAX_ASSETS = 3

# Locked in code, not configuration: no flag, env var or admin setting can switch these on.
PHASE1_BOUNDARY = [
    ("Database / query connector", "Not present in Phase 1 code"),
    ("SQL or generated-code execution", "Not present; specs are data, rendered by trusted templates"),
    ("Data export (CSV / extract)", "Not present"),
    ("Direct Tableau publication", "Not present; delivery goes through a Type C request"),
    ("External / hosted LLM", "Blocked until an approved gateway is cleared (FR-027)"),
]
APPROVED_PROVIDERS: dict = {}  # filled only after provider, contract, location and retention approvals

COMPONENTS = {
    "kpi": {"id", "type", "title", "metric"},
    "line": {"id", "type", "title", "x", "y"},
    "bar": {"id", "type", "title", "x", "y", "limit"},
    "table": {"id", "type", "title", "rows", "columns"},
}
TOP_KEYS = {"spec_version", "title", "draft", "components", "filters", "assumptions", "questions", "provenance"}
EDITABLE_KEYS = ("title", "components", "filters")
PROVENANCE_KEYS = {"assets", "metadata_source", "generated_at", "planner", "model", "spec_version"}
GRAINS = ("day", "week", "month", "quarter")
AGG_LABELS = {"sum": "Sum", "avg": "Average", "min": "Minimum", "max": "Maximum", "last": "End-of-period",
              "count": "Count", "count_distinct": "Distinct count"}
# Which aggregation intents are meaningful for which field kind. Anything else is rejected (§15.3).
ALLOWED_AGG = {
    "flow": {"sum", "avg", "min", "max"},
    "stock": {"last", "avg", "min", "max"},   # balances / positions: summing over time double counts
    "ratio": {"avg", "min", "max", "last"},   # a ratio cannot be summed
    "identifier": {"count_distinct"},
    "dimension": {"count", "count_distinct"},
    "status": {"count", "count_distinct"},
}

INSTRUCTION_LIKE = re.compile(
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)|disregard\s+(the\s+|all\s+|any\s+)?"
    r"(rules|instructions|policy|policies)|system\s+prompt|you\s+are\s+now|jailbreak|bypass\s+(the\s+)?"
    r"(policy|rules|authori[sz]ation|permissions?)|(show|list|reveal|dump)\s+(me\s+)?(all\s+)?(the\s+)?hidden"
    r"|hidden\s+(tables|fields|columns|schema)|\b(run|execute)\s+(this\s+|the\s+)?(sql|code|query|script)"
    r"|drop\s+table|delete\s+from|insert\s+into|select\s+\*|<\s*script|javascript:"
    r"|abaikan\s+(semua\s+)?(instruksi|aturan|perintah)|tabel\s+(tersembunyi|rahasia)", re.I)
CODE_LIKE = re.compile(r"<\s*/?\s*[a-z]+[^>]*>|javascript:|\bon\w+\s*=|\bdrop\s+table\b|\beval\s*\(|\bfunction\s*\(", re.I)

# Business vocabulary (Bahasa Indonesia) → catalog vocabulary used in field names.
WORDS = {"cabang": "branch", "wilayah": "region", "regional": "region", "kanwil": "region", "produk": "product",
         "segmen": "segment", "saldo": "balance", "jumlah": "count", "rekening": "account", "kanal": "channel",
         "kategori": "category", "sektor": "sector", "valas": "ccy", "mata": "ccy", "currency": "ccy",
         "tanggal": "date", "unit": "unit", "pengaduan": "complaint", "keluhan": "complaint",
         "fitur": "feature", "transaksi": "txn", "transactions": "txn", "transaction": "txn", "tarik": "cash",
         "tunai": "cash", "rasio": "ratio", "deposito": "td", "giro": "casa", "tabungan": "casa",
         "kolektibilitas": "collectibility", "tunggakan": "dpd", "restrukturisasi": "restructured",
         "pegawai": "headcount", "karyawan": "headcount", "outlet": "branch", "terminal": "terminal",
         "posisi": "position", "baki": "outstanding", "debet": "outstanding"}
GRAIN_WORDS = {"harian": "day", "daily": "day", "hari": "day", "day": "day", "mingguan": "week", "weekly": "week",
               "minggu": "week", "week": "week", "bulanan": "month", "monthly": "month", "bulan": "month",
               "month": "month", "kuartal": "quarter", "quarterly": "quarter", "triwulan": "quarter",
               "quarter": "quarter"}
STOP = set("""a an the of for and or to in on by per with vs versus show me display give what which how
many much is are was were be please dashboard report chart charts view trend trends over time across
compare comparison overview summary breakdown top bottom latest current total all each every from at as
that this those these we our my i need want see track monitor last next between
dan atau untuk dengan yang di ke dari pada oleh per tampilkan lihat berapa bagaimana apa mana semua setiap
total tren perbandingan bandingkan ringkasan saya kami kita ingin butuh perlu data nilai angka""".split())

TEXT_LIMIT, LIST_LIMIT = 160, 30


class GeneratorError(Exception):
    pass


class Blocked(GeneratorError):
    """Input refused before planning (sensitive identifiers or instruction-like text)."""

    def __init__(self, reason, findings=None):
        super().__init__(reason)
        self.findings = findings or []


# ------------------------------------------------------------------------- provider gate (FR-027)

def planner_info() -> dict:
    configured = os.environ.get("HUB_MODEL_PROVIDER", "").strip()
    info = {"planner": PLANNER, "model": None, "configured": configured or None, "routed": False}
    if configured and configured not in APPROVED_PROVIDERS:
        info["notice"] = (f"A model provider ('{configured[:40]}') is configured but not approved. "
                          "It was ignored — no prompt or metadata was sent to it.")
    return info


# ------------------------------------------------------------------------- authorised metadata (FR-028)

def _field_visible(conn, user, asset, f) -> bool:
    return (LEVELS.get(f.get("sensitivity", "Internal"), 3) <= user.level or is_custodian(user, asset["domain_id"])
            or active_entitlement(conn, user.id, "asset", asset["id"]) is not None)


def _kind(name, typ, desc) -> tuple[str, str]:
    """Candidate role from name + type only. A hypothesis, never an official business meaning."""
    t, n, d = typ.upper(), name.lower(), (desc or "").lower()
    if t.startswith(("DATE", "TIMESTAMP")):
        return "time", "time"
    if n.endswith(("_key", "_id")) or n in ("id", "session_id", "case_id"):
        return "identifier", "identifier"
    if t.startswith("BOOLEAN") or n.endswith("_flag"):
        return "status", "status"
    if t.startswith("TINYINT"):  # small codes such as collectibility 1–5 are categories, not quantities
        return "status", "status"
    if t.startswith(("DECIMAL", "INTEGER", "BIGINT", "DOUBLE", "FLOAT", "NUMERIC")):
        if re.search(r"ratio|rate|pct|percent|share", n):
            return "measure", "ratio"
        if re.search(r"balance|outstanding|position|npl_amount|headcount|account_count", n) or "end-of-day" in d:
            return "measure", "stock"
        return "measure", "flow"
    if t.startswith(("STRING", "VARCHAR", "CHAR")):
        return "dimension", "dimension"
    return "unsupported", "unsupported"


def metadata_package(conn, user, asset_ids) -> dict:
    """Metadata the generator may use: only assets and fields visible to this user, nothing else."""
    ids = list(dict.fromkeys(a for a in asset_ids if a))
    if not ids:
        raise GeneratorError("Choose at least one dataset or data product.")
    if len(ids) > MAX_ASSETS:
        raise GeneratorError(f"Choose at most {MAX_ASSETS} assets for one draft.")
    assets, fields, flagged = [], {}, []
    for aid in ids:
        a = conn.execute("SELECT * FROM assets WHERE id=?", (aid,)).fetchone()
        if not can_discover(conn, user, a):
            raise GeneratorError("A selected item was not found.")  # same message as "does not exist"
        if a["lifecycle"] == "Deprecated":
            raise GeneratorError(f"{a['title']} is deprecated — choose its certified replacement.")
        if not can_see_details(conn, user, a):
            raise GeneratorError(f"Field-level metadata of {a['title']} is not visible to you. "
                                 "Request access to the asset first.")
        terms = [t for t in conn.execute("SELECT * FROM terms") if aid in (t["related_assets"] or "").split(",")]
        hidden = 0
        for f in jl(a["fields_json"]):
            if not _field_visible(conn, user, a, f):
                hidden += 1
                continue
            desc = f.get("description") or ""
            if INSTRUCTION_LIKE.search(desc):  # metadata text is untrusted input (FR-029)
                flagged.append(f"{aid}.{f['name']}")
                desc = None
            role, kind = _kind(f["name"], f["type"], desc)
            fid = f"{aid}.{f['name']}"
            fields[fid] = {"id": fid, "asset_id": aid, "name": f["name"], "type": f["type"], "role": role,
                           "kind": kind, "description": desc, "label": (desc or f["name"].replace("_", " ")).split(" (")[0][:60],
                           "sensitivity": f.get("sensitivity", "Internal")}
        assets.append({"id": aid, "name": a["name"], "title": a["title"], "domain_id": a["domain_id"],
                       "classification": a["classification"], "grain": a["grain"] or "", "refresh": a["refresh"] or "",
                       "owner_id": a["owner_id"], "lineage": bool(jl(a["lineage_up"]) or jl(a["lineage_down"])),
                       "hidden_fields": hidden, "terms": [dict(t) for t in terms],
                       "description_flagged": bool(INSTRUCTION_LIKE.search(a["description"] or ""))})
    return {"assets": assets, "fields": fields, "flagged": flagged}


def quality_profile(package) -> list[dict]:
    """FR-033: what the metadata does and does not tell us. Missing items lower confidence."""
    out = []
    for a in package["assets"]:
        fs = [f for f in package["fields"].values() if f["asset_id"] == a["id"]]
        described = sum(1 for f in fs if f["description"])
        approved = sum(1 for t in a["terms"] if t["status"] == "Approved")
        checks = [("Column descriptions", f"{described}/{len(fs)}", described == len(fs) and fs),
                  ("Grain", a["grain"] or "unknown", bool(a["grain"])),
                  ("Table relationships", "unknown — not in metadata", False),
                  ("Owner", "named" if a["owner_id"] else "missing", bool(a["owner_id"])),
                  ("Classification", a["classification"], bool(a["classification"])),
                  ("Lineage reference", "present" if a["lineage"] else "missing", a["lineage"]),
                  ("Approved KPI definitions", f"{approved} of {len(a['terms'])} linked terms", approved > 0)]
        out.append({"asset": a, "checks": [{"label": c[0], "value": c[1], "ok": bool(c[2])} for c in checks],
                    "score": sum(1 for c in checks if c[2]) / len(checks)})
    return out


# ------------------------------------------------------------------------- planner (rules fallback)

def _tokens(text) -> list[str]:
    words = _norm(text).split()
    return [WORDS.get(w, w) for w in words]


def _field_tokens(f) -> tuple[set, set]:
    name = set(f["name"].lower().split("_"))
    desc = set(_tokens(f["description"] or "")) - STOP
    return name, desc


def _match_terms(question, package):
    q = " " + _norm(question) + " "
    found, seen = [], set()
    for a in package["assets"]:
        for t in a["terms"]:
            names = [t["term"], t["abbreviation"]] + (t["synonyms"] or "").split(",")
            if t["id"] not in seen and any(n.strip() and f" {_norm(n)} " in q for n in names):
                seen.add(t["id"])
                found.append(t)
    return found


def _grain_rank(g):
    return GRAINS.index(g) if g in GRAINS else 2


def _source_grain(asset) -> str:
    text = (asset["grain"] + " " + asset["refresh"]).lower()
    if re.search(r"\bday\b|daily|hour|min|session|case", text):
        return "day"
    if "month" in text:
        return "month"
    return "month"


def plan(question, package, now=None) -> tuple[dict, dict]:
    """Deterministic planner. Returns (spec, stats). Never invents fields: everything it references
    comes from the authorised package, and every guess is written down as an assumption."""
    now = now or utcnow()
    fields = package["fields"]
    assumptions, questions = [], []
    q_tokens = [t for t in _tokens(question) if t not in STOP]
    grain_req = next((GRAIN_WORDS[t] for t in _norm(question).split() if t in GRAIN_WORDS), None)
    terms = _match_terms(question, package)

    wanted = set(q_tokens)
    for t in terms:
        wanted |= set(_tokens(t["abbreviation"] or "")) | set(_tokens(t["term"])) - STOP
    for group in SYNONYMS:  # bilingual synonyms, e.g. kredit macet → npl
        if any(" " + s + " " in " " + _norm(question) + " " for s in group):
            wanted |= {w for s in group for w in s.split() if len(w) > 2} - STOP

    def score(f):
        name, desc = _field_tokens(f)
        return 2 * len(wanted & name) + len(wanted & desc)

    used = set()
    for f in fields.values():
        name, desc = _field_tokens(f)
        if score(f):
            used |= wanted & (name | desc)
    for t in terms:
        used |= set(_tokens(t["term"])) | set(_tokens(t["abbreviation"] or ""))
        for s in (t["synonyms"] or "").split(","):
            used |= set(_tokens(s))
    unsupported = [t for t in dict.fromkeys(q_tokens)
                   if len(t) > 2 and t not in used and t not in GRAIN_WORDS and not t.isdigit()][:5]

    measures = sorted((f for f in fields.values() if f["role"] == "measure"), key=lambda f: -score(f))
    matched = [m for m in measures if score(m)]
    if matched:
        measures = matched[:3]
    else:
        measures = measures[:2]
        if measures:
            assumptions.append("The question did not name a measure found in the metadata — candidate measures "
                               "are shown for you to confirm or remove.")
    if not measures:  # e.g. case-level tables: count distinct records as a placeholder KPI
        ident = next((f for f in fields.values() if f["role"] == "identifier"), None)
        if ident:
            measures = [ident]
            assumptions.append(f"No numeric measure exists; '{ident['name']}' is counted (distinct) as a "
                               "placeholder volume metric. Confirm the intended KPI with the data owner.")
    if not measures:
        raise GeneratorError("The selected metadata has no measure or identifier to build a dashboard from.")

    def agg_for(f):
        if f["role"] == "identifier":
            return "count_distinct"
        if f["kind"] == "ratio":
            assumptions.append(f"'{f['name']}' looks like a ratio: a simple average is shown as a placeholder. "
                               "The official (weighted) formula must come from an approved definition.")
            return "avg"
        if f["kind"] == "stock":
            assumptions.append(f"'{f['name']}' looks like a point-in-time stock (balance, position or count): "
                               "end-of-period value assumed — summing it over time would double count.")
            return "last"
        assumptions.append(f"'{f['name']}' is summed — inferred from its data type ({f['type']}) only.")
        return "sum"

    def metric(f):
        return {"field": f["id"], "agg": agg_for(f)}

    components, n = [], 0
    for f in measures:
        n += 1
        components.append({"id": f"kpi{n}", "type": "kpi", "title": f["label"][:60], "metric": metric(f)})

    dims_by_asset, filters = {}, []
    for f in fields.values():
        if f["role"] in ("dimension", "status"):
            dims_by_asset.setdefault(f["asset_id"], []).append(f)
    primary_assets = list(dict.fromkeys(m["asset_id"] for m in measures))[:2]
    grain_used = None
    for aid in primary_assets:
        asset = next(a for a in package["assets"] if a["id"] == aid)
        m = next(f for f in measures if f["asset_id"] == aid)
        time_f = next((f for f in fields.values() if f["asset_id"] == aid and f["role"] == "time"), None)
        dims = sorted(dims_by_asset.get(aid, []), key=lambda f: -score(f))
        if time_f:
            src = _source_grain(asset)
            grain = grain_req or src
            if _grain_rank(grain) < _grain_rank(src):
                questions.append(f"You asked for a {grain} view but {asset['title']} is {src}ly at the finest — "
                                 f"the draft uses {src}.")
                grain = src
            if not grain_req and grain_used is None:
                assumptions.append(f"Time grain not stated — {grain} assumed from the source refresh/grain.")
            grain_used = grain_used or grain
            components.append({"id": f"line{aid[-3:]}", "type": "line", "title": f"{m['label'][:50]} by {grain}",
                               "x": {"field": time_f["id"], "grain": grain}, "y": metric(m)})
        else:
            questions.append(f"{asset['title']} has no date/time field — a trend chart is not possible.")
        if dims:
            d = dims[0]
            if not score(d):
                assumptions.append(f"No breakdown was named — '{d['name']}' chosen as the first available dimension.")
            components.append({"id": f"bar{aid[-3:]}", "type": "bar", "title": f"{m['label'][:50]} by {d['label'][:30]}",
                               "x": {"field": d["id"]}, "y": metric(m), "limit": 8})
            cols = [metric(f) for f in measures if f["asset_id"] == aid]
            components.append({"id": f"tbl{aid[-3:]}", "type": "table", "title": f"Breakdown by {d['label'][:40]}",
                               "rows": {"field": d["id"]}, "columns": cols})
            filters += [{"field": x["id"]} for x in dims[:2]]
        if time_f:
            filters.append({"field": time_f["id"]})

    for f in fields.values():
        if f["role"] == "identifier" and score(f) and f not in measures:
            questions.append(f"'{f['name']}' is an identifier. Breakdowns by identifiers are record-level and are not "
                             "proposed — ask the owner for an approved grouping.")
    for a in package["assets"]:
        if a["id"] not in primary_assets and not any(m["asset_id"] == a["id"] for m in measures):
            questions.append(f"{a['title']} has no measure for this question and cannot be joined in Phase 1, "
                             "so it was not used.")
    for t in terms:
        if t["status"] != "Approved":
            questions.append(f"'{t['term']}' is {t['status']} in the glossary — not an official definition yet.")
        elif t["formula"]:
            questions.append(f"'{t['term']}' has an approved formula ({t['formula']}). Mapping it to the fields above "
                             "is a hypothesis — the data owner must confirm numerator/denominator before use.")
        else:
            assumptions.append(f"'{t['term']}' matched the approved glossary term (v{t['version']}); field mapping "
                               "is by name only.")
    for word in unsupported:
        questions.append(f"'{word}' was not found in the metadata you can see, so nothing was added for it.")
    for fid in package["flagged"]:
        questions.append(f"The description of '{fid}' contains instruction-like text. It was ignored and the "
                         "field is described by name only. Report it to the steward.")
    hidden = sum(a["hidden_fields"] for a in package["assets"])
    if hidden:
        assumptions.append(f"{hidden} field(s) above your clearance were not used and are not listed.")
    assumptions.append("Table relationships are not available in the metadata; nothing is joined across assets.")

    # dedupe while keeping order
    assumptions = list(dict.fromkeys(assumptions))[:LIST_LIMIT]
    questions = list(dict.fromkeys(questions))[:LIST_LIMIT]
    title = re.sub(r"\s+", " ", question).strip().rstrip("?.")[:90] or "Draft dashboard"
    spec = {
        "spec_version": SPEC_VERSION,
        "title": title[0].upper() + title[1:],
        "draft": True,
        "components": components[:12],
        "filters": list({f["field"]: f for f in filters}.values())[:6],
        "assumptions": assumptions,
        "questions": questions,
        "provenance": provenance(package, now),
    }
    profile = quality_profile(package)
    meta_score = sum(p["score"] for p in profile) / len(profile)
    confidence = "High" if matched and not unsupported and meta_score >= .7 else "Medium" if matched else "Low"
    return spec, {"unsupported": len(unsupported), "confidence": confidence, "matched_terms": [t["id"] for t in terms]}


def provenance(package, now=None) -> dict:
    return {"assets": [a["id"] for a in package["assets"]], "metadata_source": "Hub catalog (synthetic seed metadata)",
            "generated_at": iso(now or utcnow()), "planner": PLANNER, "model": None, "spec_version": SPEC_VERSION}


# ------------------------------------------------------------------------- validator (FR-025)

def validate(spec, package) -> list[str]:
    """Deterministic checks before anything is stored or rendered. Unknown and unauthorised fields
    get the same message, so the error itself does not confirm that a hidden field exists."""
    errors = []
    fields = package["fields"]
    if not isinstance(spec, dict):
        return ["Specification must be a JSON object."]
    extra = set(spec) - TOP_KEYS
    if extra:
        errors.append(f"Unsupported top-level key(s): {', '.join(sorted(extra))[:120]}.")
    if spec.get("spec_version") != SPEC_VERSION:
        errors.append(f"spec_version must be '{SPEC_VERSION}'.")
    if spec.get("draft") is not True:
        errors.append("An AI-generated specification must stay a draft (draft: true). "
                      "Certification happens only through the owner review workflow.")
    _text(spec.get("title"), "title", errors, required=True)
    for key in ("assumptions", "questions"):
        items = spec.get(key, [])
        if not isinstance(items, list) or len(items) > LIST_LIMIT or not all(isinstance(i, str) and len(i) <= 400 for i in items):
            errors.append(f"{key} must be a list of short texts.")
    prov = spec.get("provenance")
    if not isinstance(prov, dict) or set(prov) != PROVENANCE_KEYS:
        errors.append("provenance is missing or malformed.")
    elif prov.get("model") is not None or prov.get("planner") != PLANNER:
        errors.append("provenance names a planner/model that is not approved.")

    comps = spec.get("components")
    if not isinstance(comps, list) or not 1 <= len(comps) <= 12:
        errors.append("components must be a list of 1–12 items.")
        comps = []
    ids = set()

    def field_ref(ref, where, roles):
        if not isinstance(ref, dict) or not isinstance(ref.get("field"), str):
            errors.append(f"{where}: field reference missing.")
            return None
        f = fields.get(ref["field"])
        if f is None:
            errors.append(f"{where}: unknown or unauthorised field '{str(ref['field'])[:60]}'.")
            return None
        if f["role"] not in roles:
            errors.append(f"{where}: '{f['name']}' is a {f['role']} and cannot be used here.")
        return f

    def metric_ref(ref, where):
        if isinstance(ref, dict) and set(ref) - {"field", "agg"}:
            errors.append(f"{where}: unsupported metric key(s).")
        f = field_ref(ref, where, {"measure", "identifier", "dimension", "status"})
        if f is None:
            return None
        agg = ref.get("agg")
        if agg not in AGG_LABELS:
            errors.append(f"{where}: aggregation '{str(agg)[:20]}' is not supported.")
        elif agg not in ALLOWED_AGG.get(f["kind"], set()):
            errors.append(f"{where}: '{AGG_LABELS[agg].lower()}' of '{f['name']}' ({f['kind']}) is not a valid "
                          "aggregation intent.")
        return f

    for i, c in enumerate(comps):
        where = f"component {i + 1}"
        if not isinstance(c, dict) or c.get("type") not in COMPONENTS:
            errors.append(f"{where}: unsupported component type '{str(c.get('type') if isinstance(c, dict) else c)[:20]}'."
                          f" Allowed: {', '.join(COMPONENTS)}.")
            continue
        extra = set(c) - COMPONENTS[c["type"]]
        if extra:
            errors.append(f"{where}: unsupported key(s) {', '.join(sorted(map(str, extra)))[:80]}.")
        cid = c.get("id")
        if not isinstance(cid, str) or not re.fullmatch(r"[a-z0-9_-]{1,16}", cid) or cid in ids:
            errors.append(f"{where}: id must be unique, lowercase, max 16 characters.")
        ids.add(cid)
        _text(c.get("title"), f"{where} title", errors, required=True)
        used = []
        if c["type"] == "kpi":
            used.append(metric_ref(c.get("metric"), where))
        elif c["type"] in ("line", "bar"):
            x = c.get("x")
            if c["type"] == "line":
                used.append(field_ref(x, f"{where} x", {"time"}))
                if isinstance(x, dict) and (x.get("grain") not in GRAINS or set(x) - {"field", "grain"}):
                    errors.append(f"{where}: time grain must be one of {', '.join(GRAINS)}.")
            else:
                used.append(field_ref(x, f"{where} x", {"dimension", "status"}))
                if isinstance(x, dict) and set(x) - {"field"}:
                    errors.append(f"{where}: unsupported x key(s).")
                if "limit" in c and (not isinstance(c["limit"], int) or isinstance(c["limit"], bool) or not 1 <= c["limit"] <= 12):
                    errors.append(f"{where}: limit must be a whole number from 1 to 12.")
            used.append(metric_ref(c.get("y"), f"{where} y"))
        else:
            used.append(field_ref(c.get("rows"), f"{where} rows", {"dimension", "status"}))
            if isinstance(c.get("rows"), dict) and set(c["rows"]) - {"field"}:
                errors.append(f"{where}: unsupported rows key(s).")
            cols = c.get("columns")
            if not isinstance(cols, list) or not 1 <= len(cols) <= 6:
                errors.append(f"{where}: columns must list 1–6 metrics.")
                cols = []
            used += [metric_ref(col, f"{where} column {j + 1}") for j, col in enumerate(cols)]
        assets = {f["asset_id"] for f in used if f}
        if len(assets) > 1:
            errors.append(f"{where}: combines fields from different assets. Cross-asset joins are out of scope.")

    filters = spec.get("filters", [])
    if not isinstance(filters, list) or len(filters) > 6:
        errors.append("filters must be a list of at most 6 items.")
        filters = []
    for i, flt in enumerate(filters):
        if isinstance(flt, dict) and set(flt) - {"field"}:
            errors.append(f"filter {i + 1}: unsupported key(s).")
        field_ref(flt, f"filter {i + 1}", {"dimension", "status", "time"})
    return errors


def _text(value, where, errors, required=False):
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > TEXT_LIMIT:
        errors.append(f"{where} must be text of 1–{TEXT_LIMIT} characters.")
    elif CODE_LIKE.search(value):
        errors.append(f"{where} contains markup or code. Specifications are data only and are never executed.")


def merge_edit(previous: dict, edited) -> dict:
    """Users edit title, components and filters. Draft status, assumptions, open questions and
    provenance stay server-controlled so uncertainty cannot be edited away."""
    if not isinstance(edited, dict):
        raise GeneratorError("The edited specification must be a JSON object.")
    merged = {k: v for k, v in previous.items()}
    for k, v in edited.items():
        merged[k] = v  # non-editable keys are validated (e.g. draft must stay true) rather than silently dropped
    for k in ("assumptions", "questions", "provenance"):
        merged[k] = previous[k]
    return merged


def editable_view(spec) -> str:
    return json.dumps({k: spec[k] for k in EDITABLE_KEYS if k in spec}, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------------- input screening

def screen(question, *extra):
    text = " ".join([question or "", *extra])
    findings = pii.scan(text)
    if findings:
        raise Blocked("pii", findings)
    if INSTRUCTION_LIKE.search(text):
        raise Blocked("instruction")


# ------------------------------------------------------------------------- synthetic preview (FR-024)

def _cats(field, n=6):
    base = field["label"].split(" (")[0][:18] if field else "Item"
    return [f"{base} {chr(65 + i)}" for i in range(n)]


def _fmt(v, kind):
    if kind == "ratio":
        return f"{v:.2f}%"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.0f}"


def _series(rng, n, kind):
    if kind == "ratio":
        start = rng.uniform(1.5, 6)
        return [max(.1, start + rng.uniform(-.4, .4) + i * rng.uniform(-.05, .08)) for i in range(n)]
    start = rng.uniform(800, 9000)
    return [max(10, start * (1 + i * rng.uniform(-.01, .03)) + rng.uniform(-start * .06, start * .06)) for i in range(n)]


def filter_options(spec, package) -> list[dict]:
    out = []
    for i, flt in enumerate(spec.get("filters", [])):
        f = package["fields"].get(flt["field"])
        if not f:
            continue
        opts = [f"Last {k}" for k in ("3 periods", "6 periods", "12 periods")] if f["role"] == "time" else _cats(f)
        out.append({"key": f"f{i}", "label": f["label"], "field": f["id"], "options": opts})
    return out


def preview(spec, package, selected: dict, seed_key: str) -> list[dict]:
    """View-models for the trusted templates. Values are random numbers seeded per draft version and
    filter choice; the only metadata used are labels. No real value ever reaches this function."""
    fields = package["fields"]
    sel = "|".join(f"{k}={v}" for k, v in sorted(selected.items()))
    rng = random.Random(hashlib.sha256(f"{seed_key}|{sel}".encode()).hexdigest())
    chosen = {}
    for opt in filter_options(spec, package):
        if selected.get(opt["key"]) in opt["options"]:
            chosen[opt["field"]] = selected[opt["key"]]
    periods = 12
    for k, v in chosen.items():
        if fields[k]["role"] == "time":
            periods = int(re.search(r"\d+", v).group())
    out = []
    for c in spec["components"]:
        if c["type"] == "kpi":
            f = fields[c["metric"]["field"]]
            v, prev = _series(rng, 2, f["kind"])
            out.append({"type": "kpi", "title": c["title"], "agg": AGG_LABELS[c["metric"]["agg"]],
                        "value": _fmt(v, f["kind"]), "delta": f"{(v - prev) / prev * 100:+.1f}%",
                        "up": v >= prev, "field": f["name"]})
        elif c["type"] == "line":
            f = fields[c["y"]["field"]]
            vals = _series(rng, periods, f["kind"])
            g = c["x"]["grain"][0].upper()
            out.append({"type": "line", "title": c["title"], **_line_geom(vals, [f"{g}{i + 1}" for i in range(periods)], f["kind"]),
                        "y_label": f"{AGG_LABELS[c['y']['agg']]} of {f['name']}", "x_label": fields[c["x"]["field"]]["name"]})
        elif c["type"] == "bar":
            f, d = fields[c["y"]["field"]], fields[c["x"]["field"]]
            cats = _cats(d)[:c.get("limit", 8)]
            vals = [_series(rng, 1, f["kind"])[0] for _ in cats]
            out.append({"type": "bar", "title": c["title"], **_bar_geom(vals, cats, f["kind"], chosen.get(d["id"])),
                        "y_label": f"{AGG_LABELS[c['y']['agg']]} of {f['name']}", "x_label": d["name"]})
        else:
            d = fields[c["rows"]["field"]]
            cols = [fields[col["field"]] for col in c["columns"]]
            rows = [[cat] + [_fmt(_series(rng, 1, f["kind"])[0], f["kind"]) for f in cols] for cat in _cats(d)]
            if d["id"] in chosen:
                rows = [r for r in rows if r[0] == chosen[d["id"]]]
            out.append({"type": "table", "title": c["title"],
                        "columns": [d["name"]] + [f"{AGG_LABELS[col['agg']]} {fields[col['field']]['name']}" for col in c["columns"]],
                        "rows": rows})
    return out


W, H, PAD_L, PAD_B, PAD_T = 640, 220, 60, 30, 14


def _ticks(lo, hi, kind):
    return [(PAD_T + (H - PAD_T - PAD_B) * (1 - i / 3), _fmt(lo + (hi - lo) * i / 3, kind)) for i in range(4)]


def _line_geom(vals, labels, kind):
    lo, hi = min(vals) * .95, max(vals) * 1.05
    span = (hi - lo) or 1
    step = (W - PAD_L - 12) / max(len(vals) - 1, 1)
    pts = [(PAD_L + i * step, PAD_T + (H - PAD_T - PAD_B) * (1 - (v - lo) / span)) for i, v in enumerate(vals)]
    return {"w": W, "h": H, "pad_l": PAD_L, "base": H - PAD_B, "points": " ".join(f"{x:.1f},{y:.1f}" for x, y in pts),
            "dots": [(round(x, 1), round(y, 1), labels[i], _fmt(vals[i], kind)) for i, (x, y) in enumerate(pts)],
            "ticks": _ticks(lo, hi, kind), "labels": [(round(x, 1), labels[i]) for i, (x, _) in enumerate(pts)]}


def _bar_geom(vals, cats, kind, selected):
    hi = max(vals) * 1.08
    slot = (W - PAD_L - 12) / len(vals)
    bars = []
    for i, v in enumerate(vals):
        h = (H - PAD_T - PAD_B) * v / hi
        bars.append({"x": round(PAD_L + i * slot + slot * .18, 1), "y": round(H - PAD_B - h, 1), "w": round(slot * .64, 1),
                     "h": round(h, 1), "label": cats[i], "value": _fmt(v, kind), "sel": cats[i] == selected,
                     "cx": round(PAD_L + i * slot + slot / 2, 1)})
    return {"w": W, "h": H, "pad_l": PAD_L, "base": H - PAD_B, "bars": bars, "ticks": _ticks(0, hi, kind),
            "dim": bool(selected)}


# ------------------------------------------------------------------------- persistence

def new_draft(conn, user, question, audience, decision, asset_ids, at=None) -> tuple[str, dict]:
    started = time.perf_counter()
    at = at or utcnow()
    package = metadata_package(conn, user, asset_ids)
    spec, stats = plan(question, package, at)
    errors = validate(spec, package)
    if errors:  # the planner must satisfy the same validator as a human edit; fail closed if it does not
        raise GeneratorError("The generated draft did not pass validation and was not saved.")
    write_lock(conn)
    seq = conn.execute("SELECT COALESCE(MAX(seq),0) m FROM gen_drafts").fetchone()["m"] + 1
    draft_id = f"GEN-{at.astimezone().year}-{seq:04d}"
    domain = package["assets"][0]["domain_id"]
    conn.execute("INSERT INTO gen_drafts(id, seq, owner_id, title, question, audience, decision, asset_ids, domain_id,"
                 " status, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (draft_id, seq, user.id, spec["title"], question.strip(), audience.strip(), decision.strip(),
                  json.dumps([a["id"] for a in package["assets"]]), domain, "Draft", 1, iso(at), iso(at)))
    _save_version(conn, draft_id, 1, spec, user.id, "generated", "", at, (time.perf_counter() - started) * 1000, stats)
    return draft_id, {"package": package, "spec": spec, "stats": stats}


def save_edit(conn, draft, user, spec, note, at=None):
    at = at or utcnow()
    version = draft["version"] + 1
    conn.execute("UPDATE gen_drafts SET version=?, title=?, updated_at=? WHERE id=?",
                 (version, spec["title"], iso(at), draft["id"]))
    _save_version(conn, draft["id"], version, spec, user.id, "user-edit", note, at, None, None)
    return version


def _save_version(conn, draft_id, version, spec, author, source, note, at, latency_ms, stats):
    conn.execute("INSERT INTO gen_versions(draft_id, version, spec_json, source, note, author_id, created_at, latency_ms,"
                 " unsupported, confidence) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 (draft_id, version, json.dumps(spec, ensure_ascii=False), source, note[:300], author, iso(at), latency_ms,
                  (stats or {}).get("unsupported"), (stats or {}).get("confidence")))


def current_spec(conn, draft) -> dict:
    row = conn.execute("SELECT spec_json FROM gen_versions WHERE draft_id=? AND version=?",
                       (draft["id"], draft["version"])).fetchone()
    return json.loads(row["spec_json"])


def telemetry(conn) -> dict:
    """FR-034: generator quality signals without storing prompt content."""
    drafts = conn.execute("SELECT * FROM gen_drafts").fetchall()
    versions = conn.execute("SELECT * FROM gen_versions").fetchall()
    failed = conn.execute("SELECT COUNT(*) c FROM audit_events WHERE action='generator.validation_failed'").fetchone()["c"]
    blocked = conn.execute("SELECT COUNT(*) c FROM audit_events WHERE action='generator.blocked'").fetchone()["c"]
    generated = [v for v in versions if v["source"] == "generated"]
    lat = sorted(v["latency_ms"] for v in generated if v["latency_ms"] is not None)
    attempts = len(versions) + failed
    return {"drafts": len(drafts), "versions": len(versions),
            "validity": round(100 * len(versions) / attempts) if attempts else None,
            "edited": sum(1 for d in drafts if d["version"] > 1), "submitted": sum(1 for d in drafts if d["request_id"]),
            "discarded": sum(1 for d in drafts if d["status"] == "Discarded"), "blocked": blocked, "failed": failed,
            "unsupported_rate": round(100 * sum(1 for v in generated if v["unsupported"]) / len(generated)) if generated else None,
            "p50_ms": round(lat[len(lat) // 2], 1) if lat else None}
