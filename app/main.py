"""Bank Data & Analytics Hub — PoC web application."""
import csv
import io
import json
import os
import re
import secrets
from pathlib import Path
from xml.etree import ElementTree

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from . import audit, generator, geo, metrics, pii
from .db import DEFAULT_DB_PATH, WIB, connect, get_flag, init_schema, iso, jl, parse, utcnow
from .policy import (LEVELS, ROLE_LABELS, TEAM_LABELS, active_entitlement, can_admin, can_discover,
                     can_see_details, can_view_audit, can_view_internal_notes, can_view_request,
                     can_view_service_metrics, is_custodian, load_user, tableau_permits)
from .search import record_click, search
from .security import CSP, SecurityHeaders, csrf_token, flash, pop_flashes, session_alive, verify_csrf
from .seed import seed
from .workflow import (APPROVED_WAITING, FORMS, REQUEST_TYPES, STATUS_TONE, TERMINAL, NotAllowed,
                       SensitiveDataFound, WorkflowError, add_comment, available_actions, create_request,
                       get_request, notify, now_summary, pending_approval, perform, primary_action,
                       resolve_target, sla_state)

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
EVIDENCE_XML = ROOT / "evidence" / "test-results.xml"


class LoginRequired(Exception):
    pass


# ------------------------------------------------------------------------- formatting helpers

def fmt_dt(ts, with_time=True):
    dt = parse(ts) if isinstance(ts, str) else ts
    if not dt:
        return "—"
    dt = dt.astimezone(WIB)
    return dt.strftime("%d %b %Y, %H:%M WIB") if with_time else dt.strftime("%d %b %Y")


def fmt_ago(ts):
    dt = parse(ts) if isinstance(ts, str) else ts
    if not dt:
        return "—"
    secs = (utcnow() - dt).total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return f"{int(secs // 86400)} d ago"


def safe_next(path) -> str:
    """Only allow same-site relative redirects (blocks //evil.com and /\\evil.com)."""
    path = str(path or "/")
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def status_tone(status):
    return STATUS_TONE.get(status, "muted")


def class_tone(c):
    return {"Public": "c-public", "Internal": "c-internal", "Confidential": "c-conf", "Restricted": "c-restr"}.get(c, "")


# ------------------------------------------------------------------------- app factory

def create_app(db_path: str | os.PathLike | None = None, secret_key: str | None = None) -> FastAPI:
    db_path = Path(db_path or os.environ.get("HUB_DB") or DEFAULT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    init_schema(conn)
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
        seed(conn)
    conn.close()

    app = FastAPI(title="Bank Data & Analytics Hub (PoC)", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db_path = db_path
    app.add_middleware(SecurityHeaders)
    app.add_middleware(SessionMiddleware, secret_key=secret_key or os.environ.get("HUB_SECRET") or secrets.token_hex(32),
                       session_cookie="hub_session", same_site="lax", https_only=False, max_age=8 * 3600)
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

    templates = Jinja2Templates(directory=BASE / "templates")
    env = templates.env
    env.filters.update(dt=fmt_dt, ago=fmt_ago, tone=status_tone, ctone=class_tone, jl=jl)
    env.globals.update(ROLE_LABELS=ROLE_LABELS, TEAM_LABELS=TEAM_LABELS, REQUEST_TYPES=REQUEST_TYPES,
                       LEVELS=LEVELS, APPROVED_WAITING=APPROVED_WAITING, primary_action=primary_action)

    # --------------------------------------------------------------------- dependencies

    def get_conn(request: Request):
        # Used with scope="function" (DB below): commit BEFORE the response is sent, otherwise a
        # redirect-after-POST can be followed faster than the commit and show the old state.
        c = connect(request.app.state.db_path)
        try:
            yield c
            c.commit()
        except (HTTPException, StarletteHTTPException, LoginRequired, NotAllowed):
            c.commit()  # keep audit records of denied attempts
            raise
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    DB = Depends(get_conn, scope="function")

    def current_user(request: Request, conn=DB):
        uid = request.session.get("uid")
        if not uid or not session_alive(request):
            raise LoginRequired()
        user = load_user(conn, uid)
        if user is None:
            request.session.clear()
            raise LoginRequired()
        return user

    def corr(request: Request):
        return getattr(request.state, "correlation_id", "")

    def render(request, name, conn, user=None, status_code=200, **ctx):
        names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM users")}
        names["system"] = "Hub workflow engine"
        domains = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM domains")}
        unread = todo_count = 0
        if user:
            unread = conn.execute("SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read=0",
                                  (user.id,)).fetchone()["c"]
            todo_count = len(my_queue(conn, user)) + len(requester_actions(conn, user))
        base = dict(user=user, csrf=csrf_token(request), flashes=pop_flashes(request), names=names,
                    domains=domains, unread=unread, todo_count=todo_count, path=request.url.path,
                    outage=get_flag(conn, "iam_outage") == "on" or get_flag(conn, "tableau_outage") == "on")
        return templates.TemplateResponse(request, name, {**base, **ctx}, status_code=status_code)

    def deny(conn, request, user, action, object_type, object_id, status=404):
        audit.log(conn, user.id if user else None, action, object_type, object_id, result="denied",
                  correlation_id=corr(request))
        raise HTTPException(status_code=status)

    # --------------------------------------------------------------------- error handling (FR-014)

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc):
        nxt = request.url.path if request.method == "GET" else "/"
        return RedirectResponse(f"/login?next={nxt}", status_code=303)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc):
        messages = {403: ("Not permitted", "You don't have permission to perform this action."),
                    404: ("Not found", "The page or item does not exist, or you are not authorised to see it."),
                    405: ("Not allowed", "This operation is not supported.")}
        title, msg = messages.get(exc.status_code, ("Something went wrong", "The request could not be completed."))
        if exc.detail == "csrf":
            title, msg = "Session check failed", "Your form session expired. Please go back, refresh and try again."
        return _error_page(request, exc.status_code, title, msg)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc):
        return _error_page(request, 400, "Invalid request", "Some input was missing or malformed.")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc):
        return _error_page(request, 500, "Unexpected error",
                           "The service hit an unexpected problem. No details are shown for security reasons.")

    def _error_page(request, code, title, msg):
        html = templates.get_template("error.html").render(
            code=code, title=title, message=msg, correlation_id=corr(request), user=None, csrf="",
            flashes=[], unread=0, path="", names={}, domains={}, outage=False, request=request)
        resp = HTMLResponse(html, status_code=code)
        resp.headers["X-Correlation-ID"] = corr(request)
        return resp

    # --------------------------------------------------------------------- auth (mock IdP)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, next: str = "/", conn=DB):
        personas = conn.execute("SELECT * FROM users").fetchall()
        stages = [("1", "Find & request", "Start here. Search for data, open dashboards, ask for access or new work.",
                   ("requester", "analyst")),
                  ("2", "Approve", "Decide on requests for your domain, or review Confidential / Restricted access.",
                   ("data_owner", "governance")),
                  ("3", "Deliver", "Set up approved access, build datasets & dashboards, fix data issues.",
                   ("platform", "bi", "analytics", "steward")),
                  ("4", "Oversee", "Read-only oversight: settings, audit trail, metrics and evidence.",
                   ("admin", "auditor"))]
        groups, placed = [], set()
        for stage in reversed(stages):  # most specific role wins (a data owner is also a requester)
            members = [p for p in personas if p["id"] not in placed and set(p["roles"].split(",")) & set(stage[3])]
            placed.update(p["id"] for p in members)
            groups.insert(0, (*stage[:3], members))
        return render(request, "login.html", conn, groups=groups, next=safe_next(next))

    @app.post("/login", dependencies=[Depends(verify_csrf)])
    async def login(request: Request, conn=DB):
        form = await request.form()
        uid, nxt = form.get("uid", ""), form.get("next", "/")
        user = load_user(conn, uid)
        if user is None:
            audit.log(conn, uid[:32], "auth.signin", "session", "", result="failed", correlation_id=corr(request))
            flash(request, "Sign-in failed.", "bad")
            return RedirectResponse("/login", status_code=303)
        request.session.clear()
        request.session.update(uid=user.id, last_seen=int(utcnow().timestamp()), csrf=secrets.token_urlsafe(24))
        audit.log(conn, user.id, "auth.signin", "session", "", details={"idp": "mock-sso"}, correlation_id=corr(request))
        return RedirectResponse(safe_next(nxt), status_code=303)

    @app.post("/logout", dependencies=[Depends(verify_csrf)])
    def logout(request: Request, conn=DB):
        uid = request.session.get("uid")
        if uid:
            audit.log(conn, uid, "auth.signout", "session", "", correlation_id=corr(request))
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    # --------------------------------------------------------------------- shared queries

    def visible_requests(conn, user):
        return [r for r in conn.execute("SELECT * FROM requests ORDER BY updated_at DESC") if can_view_request(user, r)]

    def my_queue(conn, user):
        out = []
        for r in conn.execute("SELECT * FROM requests WHERE status NOT IN ('Closed','Rejected','Cancelled')"
                              " ORDER BY due_at"):
            if r["requester_id"] == user.id:
                continue
            acts = available_actions(conn, user, r)
            if acts:
                out.append((r, acts))
        return out

    def requester_actions(conn, user):
        out = []
        for r in conn.execute("SELECT * FROM requests WHERE requester_id=? AND status NOT IN"
                              " ('Closed','Rejected','Cancelled') ORDER BY updated_at DESC", (user.id,)):
            acts = [a for a in available_actions(conn, user, r) if a.action != "cancel"]
            if acts:
                out.append((r, acts))
        return out

    # --------------------------------------------------------------------- home

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, conn=DB, user=Depends(current_user)):
        mine = conn.execute("SELECT * FROM requests WHERE requester_id=? ORDER BY updated_at DESC LIMIT 6",
                            (user.id,)).fetchall()
        dashboards = [d for d in conn.execute("SELECT * FROM dashboards WHERE lifecycle='published'"
                                              " ORDER BY views_30d DESC") if can_discover(conn, user, d, "dashboard")][:4]
        assets = [a for a in conn.execute("SELECT * FROM assets WHERE lifecycle='Certified' ORDER BY last_updated DESC")
                  if can_discover(conn, user, a)][:5]
        counts = dict(assets=sum(1 for a in conn.execute("SELECT * FROM assets") if can_discover(conn, user, a)),
                      terms=conn.execute("SELECT COUNT(*) c FROM terms").fetchone()["c"],
                      dashboards=sum(1 for d in conn.execute("SELECT * FROM dashboards") if can_discover(conn, user, d, "dashboard")))
        return render(request, "home.html", conn, user, mine=mine, queue=my_queue(conn, user)[:6],
                      todo=requester_actions(conn, user), dashboards=dashboards, assets=assets, counts=counts,
                      sla_state=sla_state)

    # --------------------------------------------------------------------- search & catalog

    @app.get("/search", response_class=HTMLResponse)
    def search_page(request: Request, q: str = "", kind: str = "", conn=DB, user=Depends(current_user)):
        q = q.strip()[:120]
        results, sid = search(conn, user, q, None) if q else ([], None)
        counts = {k: sum(1 for r in results if r["kind"] == k) for k in ("asset", "term", "dashboard")}
        shown = [r for r in results if not kind or r["kind"] == kind]
        if q:
            audit.log(conn, user.id, "search.query", "search", str(sid), details={"results": len(results)},
                      correlation_id=corr(request))
        return render(request, "search.html", conn, user, q=q, kind=kind, results=shown, counts=counts, sid=sid,
                      total=len(results))

    @app.get("/api/suggest")
    def suggest(q: str = "", conn=DB, user=Depends(current_user)):
        results, _ = search(conn, user, q[:200], None, limit=5, log=False) if len(q.strip()) >= 3 else ([], None)
        results = [r for r in results if r["kind"] in ("dashboard", "asset") and r["status"] not in ("deprecated", "Deprecated")]
        return JSONResponse([{k: r[k] for k in ("kind", "id", "title", "type", "domain", "url")} for r in results[:4]])

    @app.get("/catalog", response_class=HTMLResponse)
    def catalog(request: Request, domain: str = "", type: str = "", classification: str = "", lifecycle: str = "",
                conn=DB, user=Depends(current_user)):
        rows = [a for a in conn.execute("SELECT * FROM assets ORDER BY title") if can_discover(conn, user, a)]
        facets = {"type": sorted({a["type"] for a in rows}), "classification": [c for c in LEVELS if any(a["classification"] == c for a in rows)],
                  "lifecycle": sorted({a["lifecycle"] for a in rows}), "domain": sorted({a["domain_id"] for a in rows})}
        rows = [a for a in rows if (not domain or a["domain_id"] == domain) and (not type or a["type"] == type)
                and (not classification or a["classification"] == classification)
                and (not lifecycle or a["lifecycle"] == lifecycle)]
        return render(request, "catalog.html", conn, user, rows=rows, facets=facets,
                      sel=dict(domain=domain, type=type, classification=classification, lifecycle=lifecycle))

    @app.get("/catalog/{asset_id}", response_class=HTMLResponse)
    def asset_detail(asset_id: str, request: Request, sid: str = "", conn=DB, user=Depends(current_user)):
        a = conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not can_discover(conn, user, a):
            deny(conn, request, user, "catalog.view", "asset", asset_id)
        record_click(conn, sid, user.id)
        details = can_see_details(conn, user, a)

        def ref(x):
            kind = "dashboard" if x.startswith("DB-") else "asset" if x.startswith("AS-") else None
            if not kind:
                return {"label": x, "url": None}
            row = conn.execute(f"SELECT * FROM {'dashboards' if kind == 'dashboard' else 'assets'} WHERE id=?", (x,)).fetchone()
            if not can_discover(conn, user, row, kind):
                return {"label": "Restricted item", "url": None}
            return {"label": row["title"], "url": f"/{'analytics' if kind == 'dashboard' else 'catalog'}/{x}", "id": x}

        terms = [t for t in conn.execute("SELECT * FROM terms") if asset_id in (t["related_assets"] or "").split(",")]
        dashboards = [d for d in conn.execute("SELECT * FROM dashboards")
                      if asset_id in (d["related_assets"] or "").split(",") and can_discover(conn, user, d, "dashboard")]
        ent = active_entitlement(conn, user.id, "asset", asset_id)
        pending = conn.execute("SELECT * FROM requests WHERE requester_id=? AND target_id=? AND type='A' AND status NOT IN"
                               " ('Closed','Rejected','Cancelled')", (user.id, asset_id)).fetchone()
        audit.log(conn, user.id, "catalog.view", "asset", asset_id, correlation_id=corr(request))
        return render(request, "asset.html", conn, user, a=a, details=details, fields=jl(a["fields_json"]),
                      up=[ref(x) for x in jl(a["lineage_up"])], down=[ref(x) for x in jl(a["lineage_down"])],
                      rules=jl(a["quality_rules"]), terms=terms, dashboards=dashboards, ent=ent, pending=pending,
                      custodian=is_custodian(user, a["domain_id"]))

    # --------------------------------------------------------------------- glossary

    @app.get("/glossary", response_class=HTMLResponse)
    def glossary(request: Request, domain: str = "", status: str = "", q: str = "", conn=DB,
                 user=Depends(current_user)):
        rows = conn.execute("SELECT * FROM terms ORDER BY term").fetchall()
        ql = q.lower().strip()
        rows = [t for t in rows if (not domain or t["domain_id"] == domain) and (not status or t["status"] == status)
                and (not ql or ql in (t["term"] + " " + t["abbreviation"] + " " + t["synonyms"] + " " + t["definition"]).lower())]
        pending = {r["term_id"] for r in conn.execute("SELECT term_id FROM term_revisions WHERE status='in_review'")}
        return render(request, "glossary.html", conn, user, rows=rows, pending=pending,
                      sel=dict(domain=domain, status=status, q=q))

    @app.get("/glossary/{term_id}", response_class=HTMLResponse)
    def term_detail(term_id: str, request: Request, sid: str = "", conn=DB, user=Depends(current_user)):
        t = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
        if not t:
            raise HTTPException(404)
        record_click(conn, sid, user.id)
        revisions = conn.execute("SELECT * FROM term_revisions WHERE term_id=? ORDER BY id DESC", (term_id,)).fetchall()
        in_review = next((r for r in revisions if r["status"] == "in_review"), None)
        assets = [conn.execute("SELECT * FROM assets WHERE id=?", (x,)).fetchone() for x in (t["related_assets"] or "").split(",") if x]
        assets = [a for a in assets if can_discover(conn, user, a)]
        dashboards = [conn.execute("SELECT * FROM dashboards WHERE id=?", (x,)).fetchone() for x in (t["related_dashboards"] or "").split(",") if x]
        dashboards = [d for d in dashboards if can_discover(conn, user, d, "dashboard")]
        disputes = conn.execute("SELECT * FROM requests WHERE type='E' AND target_id=?", (term_id,)).fetchall()
        return render(request, "term.html", conn, user, t=t, revisions=revisions, in_review=in_review, assets=assets,
                      dashboards=dashboards, disputes=[d for d in disputes if can_view_request(user, d)],
                      can_propose=is_custodian(user, t["domain_id"]) and not in_review,
                      can_decide=bool(in_review and user.id == t["owner_id"] and in_review["author_id"] != user.id))

    @app.post("/glossary/{term_id}/propose", dependencies=[Depends(verify_csrf)])
    async def term_propose(term_id: str, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        t = conn.execute("SELECT * FROM terms WHERE id=?", (term_id,)).fetchone()
        if not t:
            raise HTTPException(404)
        if not is_custodian(user, t["domain_id"]):
            deny(conn, request, user, "glossary.propose", "term", term_id, status=403)
        if conn.execute("SELECT 1 FROM term_revisions WHERE term_id=? AND status='in_review'", (term_id,)).fetchone():
            flash(request, "A revision is already in review for this term.", "bad")
            return RedirectResponse(f"/glossary/{term_id}", status_code=303)
        definition = str(form.get("definition", "")).strip()
        note = str(form.get("change_note", "")).strip()
        if not definition or not note:
            flash(request, "Definition and change note are required.", "bad")
            return RedirectResponse(f"/glossary/{term_id}", status_code=303)
        if pii.scan(definition + " " + note):
            flash(request, "Remove customer identifiers from the text.", "bad")
            return RedirectResponse(f"/glossary/{term_id}", status_code=303)
        version = conn.execute("SELECT MAX(version) v FROM term_revisions WHERE term_id=?", (term_id,)).fetchone()["v"] + 1
        conn.execute("INSERT INTO term_revisions(term_id, version, definition, formula, change_note, status, author_id,"
                     " created_at) VALUES (?,?,?,?,?,?,?,?)",
                     (term_id, version, definition, str(form.get("formula", "")).strip(), note, "in_review", user.id, iso(utcnow())))
        notify(conn, [t["owner_id"]], f"Glossary revision v{version} of '{t['term']}' awaits your approval", f"/glossary/{term_id}")
        audit.log(conn, user.id, "glossary.propose", "term", term_id, details={"version": version}, correlation_id=corr(request))
        flash(request, f"Revision v{version} submitted to the data owner for approval.")
        return RedirectResponse(f"/glossary/{term_id}", status_code=303)

    @app.post("/glossary/revisions/{rev_id}/decide", dependencies=[Depends(verify_csrf)])
    async def term_decide(rev_id: int, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        rev = conn.execute("SELECT * FROM term_revisions WHERE id=?", (rev_id,)).fetchone()
        if not rev or rev["status"] != "in_review":
            raise HTTPException(404)
        t = conn.execute("SELECT * FROM terms WHERE id=?", (rev["term_id"],)).fetchone()
        if user.id != t["owner_id"] or user.id == rev["author_id"]:
            deny(conn, request, user, "glossary.decide", "term", t["id"], status=403)
        decision, rationale = form.get("decision"), str(form.get("rationale", "")).strip()
        if decision not in ("approve", "reject") or not rationale:
            flash(request, "Choose a decision and give a rationale.", "bad")
            return RedirectResponse(f"/glossary/{t['id']}", status_code=303)
        now = utcnow()
        conn.execute("UPDATE term_revisions SET status=?, decided_by=?, decided_at=?, rationale=? WHERE id=?",
                     ("approved" if decision == "approve" else "rejected", user.id, iso(now), rationale, rev_id))
        if decision == "approve":
            conn.execute("UPDATE terms SET definition=?, formula=?, version=?, status='Approved', effective_date=?,"
                         " updated_at=? WHERE id=?", (rev["definition"], rev["formula"], rev["version"],
                                                       now.astimezone(WIB).date().isoformat(), iso(now), t["id"]))
        done = "approved" if decision == "approve" else "rejected"
        notify(conn, [rev["author_id"]], f"Glossary revision v{rev['version']} of '{t['term']}' was {done}", f"/glossary/{t['id']}")
        audit.log(conn, user.id, f"glossary.{decision}", "term", t["id"], details={"version": rev["version"]},
                  correlation_id=corr(request))
        flash(request, f"Revision v{rev['version']} {done}." + (" Now the published definition." if decision == "approve" else ""))
        return RedirectResponse(f"/glossary/{t['id']}", status_code=303)

    # --------------------------------------------------------------------- analytics hub / Tableau

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics(request: Request, domain: str = "", certified: str = "", lifecycle: str = "", q: str = "",
                  conn=DB, user=Depends(current_user)):
        rows = [d for d in conn.execute("SELECT * FROM dashboards ORDER BY views_30d DESC")
                if can_discover(conn, user, d, "dashboard")]
        ql = q.lower().strip()
        rows = [d for d in rows if (not domain or d["domain_id"] == domain)
                and (not certified or str(d["certified"]) == certified)
                and (not lifecycle or d["lifecycle"] == lifecycle)
                and (not ql or ql in (d["title"] + d["description"] + d["tags"]).lower())]
        last_sync = conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        return render(request, "analytics.html", conn, user, rows=rows, last_sync=last_sync,
                      sel=dict(domain=domain, certified=certified, lifecycle=lifecycle, q=q))

    @app.get("/analytics/{dash_id}", response_class=HTMLResponse)
    def dashboard_detail(dash_id: str, request: Request, sid: str = "", conn=DB, user=Depends(current_user)):
        d = conn.execute("SELECT * FROM dashboards WHERE id=?", (dash_id,)).fetchone()
        if not can_discover(conn, user, d, "dashboard"):
            deny(conn, request, user, "analytics.view", "dashboard", dash_id)
        record_click(conn, sid, user.id)
        terms = [conn.execute("SELECT * FROM terms WHERE id=?", (x,)).fetchone() for x in (d["related_terms"] or "").split(",") if x]
        assets = [conn.execute("SELECT * FROM assets WHERE id=?", (x,)).fetchone() for x in (d["related_assets"] or "").split(",") if x]
        ent = active_entitlement(conn, user.id, "dashboard", dash_id)
        pending = conn.execute("SELECT * FROM requests WHERE requester_id=? AND target_id=? AND type='A' AND status NOT IN"
                               " ('Closed','Rejected','Cancelled')", (user.id, dash_id)).fetchone()
        replacement = None
        if d["lifecycle"] == "deprecated":
            replacement = conn.execute("SELECT * FROM dashboards WHERE id='DB-002'").fetchone()
            if not can_discover(conn, user, replacement, "dashboard"):
                replacement = None
        audit.log(conn, user.id, "analytics.view", "dashboard", dash_id, correlation_id=corr(request))
        return render(request, "dashboard.html", conn, user, d=d, terms=[t for t in terms if t],
                      assets=[a for a in assets if a and can_discover(conn, user, a)], ent=ent, pending=pending,
                      replacement=replacement)

    @app.get("/mock-tableau/views/{dash_id}", response_class=HTMLResponse)
    def mock_tableau(dash_id: str, request: Request, metric: str = geo.DEFAULT_METRIC, res: int = geo.DEFAULT_RESOLUTION,
                     wilayah: str = "",
                     conn=DB, user=Depends(current_user)):
        """Stands in for Tableau Server. It enforces its OWN permissions — the portal listing grants nothing."""
        d = conn.execute("SELECT * FROM dashboards WHERE id=?", (dash_id,)).fetchone()
        if not can_discover(conn, user, d, "dashboard"):
            deny(conn, request, user, "tableau.open_view", "dashboard", dash_id)  # don't confirm it exists
        ok, reason = tableau_permits(conn, user, d)
        audit.log(conn, user.id, "tableau.open_view", "dashboard", dash_id, result="success" if ok else "denied",
                  details={"basis": reason}, correlation_id=corr(request))
        hexmap = geo.hexmap(metric, res, wilayah) if ok and dash_id in geo.MAP_DASHBOARDS else None
        html = templates.get_template("mock_tableau.html").render(request=request, d=d, ok=ok, reason=reason, user=user,
                                                                   geo=hexmap)
        resp = HTMLResponse(html, status_code=200 if ok else 403)
        if hexmap and geo.tile_origin():  # only the map view may load basemap tiles, and only from that server
            resp.headers["Content-Security-Policy"] = CSP.replace("img-src 'self' data:",
                                                                  f"img-src 'self' data: {geo.tile_origin()}")
        return resp

    # --------------------------------------------------------------------- AI dashboard generator (PRD v0.2 §7.8)

    def generator_assets(conn, user):
        return [(a, can_see_details(conn, user, a)) for a in conn.execute(
            "SELECT * FROM assets WHERE lifecycle!='Deprecated' ORDER BY title") if can_discover(conn, user, a)]

    def get_draft(conn, draft_id):
        return conn.execute("SELECT * FROM gen_drafts WHERE id=?", (draft_id,)).fetchone()

    def can_view_draft(conn, user, d):
        if d is None:
            return False
        if d["owner_id"] == user.id or user.has("auditor"):
            return True
        return bool(d["request_id"]) and can_view_request(user, get_request(conn, d["request_id"]))

    def own_open_draft(conn, request, user, draft_id, action):
        d = get_draft(conn, draft_id)
        if not can_view_draft(conn, user, d):
            deny(conn, request, user, action, "generator", draft_id)
        if d["owner_id"] != user.id:
            deny(conn, request, user, action, "generator", draft_id, status=403)
        return d

    def render_generator(request, conn, user, values=None, error=None, findings=None, status_code=200):
        drafts = conn.execute("SELECT * FROM gen_drafts WHERE owner_id=? ORDER BY updated_at DESC", (user.id,)).fetchall()
        return render(request, "generator.html", conn, user, assets=generator_assets(conn, user), drafts=drafts,
                      values=values or {}, error=error, findings=findings, info=generator.planner_info(),
                      boundary=generator.PHASE1_BOUNDARY, label=generator.SYNTHETIC_LABEL,
                      max_assets=generator.MAX_ASSETS, status_code=status_code)

    def render_draft(request, conn, user, d, edit_errors=None, edit_text=None, status_code=200):
        spec = generator.current_spec(conn, d)
        try:  # re-checked for every viewer: a reviewer or a user whose access was revoked sees only what they may see
            package = generator.metadata_package(conn, user, jl(d["asset_ids"]))
            authorised = not generator.validate(spec, package)
        except generator.GeneratorError:
            package, authorised = None, False
        selected = {k: v for k, v in request.query_params.items() if re.fullmatch(r"f\d", k)}
        ctx = {}
        if authorised:
            ctx = dict(spec=spec, fields=package["fields"], filters=generator.filter_options(spec, package),
                       components=generator.preview(spec, package, selected, f"{d['id']}:{d['version']}"),
                       profile=generator.quality_profile(package), assets_meta=package["assets"])
        existing = []
        if authorised and d["status"] == "Draft":  # §8.3 step 2: reuse before building
            hits, _ = search(conn, user, d["question"], None, limit=10, log=False)
            existing = [h for h in hits if h["kind"] in ("dashboard", "asset") and h["score"] >= 6
                        and h["status"] not in ("deprecated", "Deprecated")][:3]
        if not selected:
            audit.log(conn, user.id, "generator.view", "generator", d["id"], result="success" if authorised else "restricted",
                      correlation_id=corr(request))
        return render(request, "generator_draft.html", conn, user, d=d, authorised=authorised, selected=selected,
                      versions=conn.execute("SELECT * FROM gen_versions WHERE draft_id=? ORDER BY version DESC",
                                            (d["id"],)).fetchall(),
                      req=get_request(conn, d["request_id"]) if d["request_id"] else None, existing=existing,
                      label=generator.SYNTHETIC_LABEL, info=generator.planner_info(), edit_errors=edit_errors,
                      edit_text=edit_text if edit_text is not None else (generator.editable_view(spec) if authorised else ""),
                      can_edit=authorised and d["owner_id"] == user.id and d["status"] == "Draft",
                      status_code=status_code, **ctx)

    @app.get("/generator", response_class=HTMLResponse)
    def generator_home(request: Request, asset: str = "", conn=DB, user=Depends(current_user)):
        return render_generator(request, conn, user, {"assets": [asset] if asset else []})

    @app.post("/generator", dependencies=[Depends(verify_csrf)])
    async def generator_create(request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        values = {"question": str(form.get("question", "")).strip()[:500], "audience": str(form.get("audience", "")).strip()[:120],
                  "decision": str(form.get("decision", "")).strip()[:200], "assets": [str(a) for a in form.getlist("assets")][:6]}
        if not (values["question"] and values["audience"] and values["decision"]):
            return render_generator(request, conn, user, values, error="Describe the business question, audience and decision.",
                                    status_code=422)
        try:
            generator.screen(values["question"], values["audience"], values["decision"])
        except generator.Blocked as e:
            audit.log(conn, user.id, "generator.blocked", "generator", "", result="denied",
                      details={"reason": str(e), "findings": [f["type"] for f in e.findings]}, correlation_id=corr(request))
            if e.findings:
                return render_generator(request, conn, user, values, findings=e.findings, status_code=422)
            return render_generator(request, conn, user, values, status_code=422,
                                    error="The text contains instructions the generator does not accept (for example asking it "
                                          "to ignore rules, reveal hidden tables or run code). Describe only the business "
                                          "question. The attempt was recorded.")
        try:
            draft_id, out = generator.new_draft(conn, user, values["question"], values["audience"], values["decision"],
                                                values["assets"])
        except generator.GeneratorError as e:
            return render_generator(request, conn, user, values, error=str(e), status_code=422)
        spec = out["spec"]
        if out["package"]["flagged"]:
            audit.log(conn, user.id, "generator.metadata_flagged", "generator", draft_id,
                      details={"fields": out["package"]["flagged"]}, correlation_id=corr(request))
        audit.log(conn, user.id, "generator.create", "generator", draft_id,
                  details={"assets": spec["provenance"]["assets"], "version": 1, "planner": generator.PLANNER, "model": None,
                           "valid": True, "components": len(spec["components"]), "confidence": out["stats"]["confidence"]},
                  correlation_id=corr(request))
        flash(request, f"Draft {draft_id} generated from metadata only. All preview values are synthetic.")
        return RedirectResponse(f"/generator/{draft_id}", status_code=303)

    @app.get("/generator/{draft_id}", response_class=HTMLResponse)
    def generator_draft(draft_id: str, request: Request, conn=DB, user=Depends(current_user)):
        d = get_draft(conn, draft_id)
        if not can_view_draft(conn, user, d):
            deny(conn, request, user, "generator.view", "generator", draft_id)
        return render_draft(request, conn, user, d)

    @app.post("/generator/{draft_id}/edit", dependencies=[Depends(verify_csrf)])
    async def generator_edit(draft_id: str, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        d = own_open_draft(conn, request, user, draft_id, "generator.revise")
        if d["status"] != "Draft":
            flash(request, "This draft is locked because it was submitted or discarded.", "bad")
            return RedirectResponse(f"/generator/{draft_id}", status_code=303)
        text, note = str(form.get("spec_json", ""))[:20000], str(form.get("note", "")).strip()[:300]
        try:
            package = generator.metadata_package(conn, user, jl(d["asset_ids"]))
            spec = generator.merge_edit(generator.current_spec(conn, d), json.loads(text))
            errors = generator.validate(spec, package)
        except json.JSONDecodeError:
            errors = ["Not valid JSON — check commas, quotes and brackets."]
        except generator.GeneratorError as e:
            errors = [str(e)]
        if not errors and pii.scan(text + " " + note):
            errors = ["Remove customer identifiers from the specification or change note."]
        if errors:
            audit.log(conn, user.id, "generator.validation_failed", "generator", draft_id, result="rejected",
                      details={"errors": len(errors), "version": d["version"]}, correlation_id=corr(request))
            return render_draft(request, conn, user, d, edit_errors=errors, edit_text=text, status_code=422)
        version = generator.save_edit(conn, d, user, spec, note)
        audit.log(conn, user.id, "generator.revise", "generator", draft_id,
                  details={"version": version, "components": len(spec["components"]), "valid": True},
                  correlation_id=corr(request))
        flash(request, f"Saved as version {version}. It passed validation and is still a draft.")
        return RedirectResponse(f"/generator/{draft_id}", status_code=303)

    @app.post("/generator/{draft_id}/submit", dependencies=[Depends(verify_csrf)])
    def generator_submit(draft_id: str, request: Request, conn=DB, user=Depends(current_user)):
        d = own_open_draft(conn, request, user, draft_id, "generator.submit")
        if d["status"] != "Draft":
            flash(request, "This draft was already submitted or discarded.", "bad")
            return RedirectResponse(f"/generator/{draft_id}", status_code=303)
        spec = generator.current_spec(conn, d)
        try:
            package = generator.metadata_package(conn, user, jl(d["asset_ids"]))
            errors = generator.validate(spec, package)
        except generator.GeneratorError as e:
            errors = [str(e)]
        if errors:
            flash(request, "The draft no longer passes validation against the metadata you can see. Regenerate it.", "bad")
            return RedirectResponse(f"/generator/{draft_id}", status_code=303)
        conf = max((a["classification"] for a in package["assets"]), key=LEVELS.get)
        grain = next((c["x"]["grain"] for c in spec["components"] if c["type"] == "line"), "month")
        data = {"title": spec["title"], "purpose": d["question"], "decision": d["decision"], "audience": d["audience"],
                "kpis": ", ".join(dict.fromkeys(c["title"] for c in spec["components"] if c["type"] == "kpi"))[:300],
                "dimensions": ", ".join(dict.fromkeys(package["fields"][f["field"]]["name"] for f in spec["filters"]))[:300],
                "refresh": {"day": "Daily", "week": "Weekly"}.get(grain, "Monthly"), "domain_id": d["domain_id"],
                "confidentiality": "Internal" if conf == "Public" else conf, "priority": "Medium"}
        try:
            req_id = create_request(conn, user, "C", data, corr=corr(request))
        except WorkflowError as e:
            flash(request, str(e), "bad")
            return RedirectResponse(f"/generator/{draft_id}", status_code=303)
        ref = f"{d['id']} v{d['version']}"
        req = get_request(conn, req_id)
        conn.execute("UPDATE requests SET details_json=? WHERE id=?",
                     (json.dumps({**jl(req["details_json"], {}), "ai_draft": ref}), req_id))
        conn.execute("INSERT INTO request_events(request_id, at, actor_id, action, from_status, to_status, note)"
                     " VALUES (?,?,?,?,?,?,?)", (req_id, iso(utcnow()), "system", "attach", req["status"], req["status"],
                                                 f"AI-generated draft specification {ref} attached (metadata-only, synthetic "
                                                 "preview). It is a design input, not an approved definition."))
        conn.execute("UPDATE gen_drafts SET status='Submitted for review', request_id=?, updated_at=? WHERE id=?",
                     (req_id, iso(utcnow()), draft_id))
        audit.log(conn, user.id, "generator.submit", "generator", draft_id,
                  details={"version": d["version"], "request": req_id}, correlation_id=corr(request))
        flash(request, f"{ref} submitted as dashboard request {req_id}. BI triage and the data owner review it next.")
        return RedirectResponse(f"/requests/{req_id}", status_code=303)

    @app.post("/generator/{draft_id}/discard", dependencies=[Depends(verify_csrf)])
    def generator_discard(draft_id: str, request: Request, conn=DB, user=Depends(current_user)):
        d = own_open_draft(conn, request, user, draft_id, "generator.discard")
        if d["status"] == "Draft":
            conn.execute("UPDATE gen_drafts SET status='Discarded', updated_at=? WHERE id=?", (iso(utcnow()), draft_id))
            audit.log(conn, user.id, "generator.discard", "generator", draft_id, details={"version": d["version"]},
                      correlation_id=corr(request))
            flash(request, f"Draft {draft_id} discarded. Its versions stay in the history.")
        return RedirectResponse("/generator", status_code=303)

    # --------------------------------------------------------------------- request center

    def target_options(conn, user, include_terms=False):
        opts = {"Datasets & data products": [], "Tableau dashboards": [], "Business terms": []}
        for a in conn.execute("SELECT * FROM assets WHERE lifecycle!='Deprecated' ORDER BY title"):
            if can_discover(conn, user, a):
                opts["Datasets & data products"].append((f"asset:{a['id']}", f"{a['title']} · {a['classification']}"))
        for d in conn.execute("SELECT * FROM dashboards WHERE lifecycle NOT IN ('retired') ORDER BY title"):
            if can_discover(conn, user, d, "dashboard"):
                opts["Tableau dashboards"].append((f"dashboard:{d['id']}", f"{d['title']} · {d['classification']}"))
        if include_terms:
            for t in conn.execute("SELECT * FROM terms ORDER BY term"):
                opts["Business terms"].append((f"term:{t['id']}", t["term"]))
        return {k: v for k, v in opts.items() if v}

    def render_form(request, conn, user, rtype, values, error=None, findings=None, suggestions=None, status_code=200):
        svc = conn.execute("SELECT * FROM service_definitions WHERE type=?", (rtype,)).fetchone()
        domain_rows = conn.execute("SELECT * FROM domains ORDER BY name").fetchall()
        return render(request, "request_form.html", conn, user, rtype=rtype, svc=svc, fields=FORMS[rtype],
                      values=values, error=error, findings=findings, suggestions=suggestions,
                      targets=target_options(conn, user, include_terms=rtype == "E"), domain_rows=domain_rows,
                      status_code=status_code)

    @app.get("/requests/new", response_class=HTMLResponse)
    def request_center(request: Request, conn=DB, user=Depends(current_user)):
        services = conn.execute("SELECT * FROM service_definitions ORDER BY type").fetchall()
        return render(request, "request_center.html", conn, user, services=services)

    @app.get("/requests/new/{rtype}", response_class=HTMLResponse)
    def request_form(rtype: str, request: Request, target: str = "", conn=DB, user=Depends(current_user)):
        if rtype not in FORMS:
            raise HTTPException(404)
        return render_form(request, conn, user, rtype, {"target": target})

    @app.post("/requests/new/{rtype}", dependencies=[Depends(verify_csrf)])
    async def request_submit(rtype: str, request: Request, conn=DB, user=Depends(current_user)):
        if rtype not in FORMS:
            raise HTTPException(404)
        form = await request.form()
        data = {k: str(v)[:4000] for k, v in form.items()}
        if data.get("_redact") != "1":
            data.pop("_redact", None)
        if rtype in ("B", "C", "D") and data.get("_dup_ack") != "1":
            text = " ".join(data.get(k, "") for k in ("title", "kpis", "purpose"))
            hits, _ = search(conn, user, text, None, limit=12, log=False)
            hits = [h for h in hits if h["kind"] in ("dashboard", "asset") and h["status"] not in ("deprecated", "Deprecated")]
            hits = [h for h in hits if h["score"] >= 6][:4]
            if hits:
                return render_form(request, conn, user, rtype, data, suggestions=hits)
        try:
            req_id = create_request(conn, user, rtype, {k: v for k, v in data.items() if k not in ("csrf_token", "_dup_ack")},
                                    corr=corr(request))
        except SensitiveDataFound as e:
            return render_form(request, conn, user, rtype, data, findings=e.findings, status_code=422)
        except WorkflowError as e:
            return render_form(request, conn, user, rtype, data, error=str(e), status_code=422)
        flash(request, f"Request {req_id} submitted. You can track every status change here.")
        return RedirectResponse(f"/requests/{req_id}", status_code=303)

    @app.get("/requests/{req_id}", response_class=HTMLResponse)
    def request_detail(req_id: str, request: Request, conn=DB, user=Depends(current_user)):
        r = get_request(conn, req_id)
        if not can_view_request(user, r):
            deny(conn, request, user, "request.view", "request", req_id)
        internal_ok = can_view_internal_notes(user, r)
        events = [e for e in conn.execute("SELECT * FROM request_events WHERE request_id=? ORDER BY at, id", (req_id,))
                  if internal_ok or not e["internal"]]
        decisions = conn.execute("SELECT * FROM decisions WHERE request_id=? ORDER BY at", (req_id,)).fetchall()
        tasks = conn.execute("SELECT * FROM fulfilment_tasks WHERE request_id=? ORDER BY at", (req_id,)).fetchall()
        kind, target = resolve_target(conn, f"{r['target_type']}:{r['target_id']}") if r["target_id"] else (None, None)
        svc = conn.execute("SELECT * FROM service_definitions WHERE type=?", (r["type"],)).fetchone()
        result = None
        if r["result_ref"] and ":" in r["result_ref"]:
            rk, rrow = resolve_target(conn, r["result_ref"])
            if rrow is not None and can_discover(conn, user, rrow, "dashboard" if rk == "dashboard" else "asset"):
                result = {"label": rrow["title"], "url": f"/{'analytics' if rk == 'dashboard' else 'catalog'}/{rrow['id']}"}
        actions = [] if user.has("admin", "auditor") and user.id != r["requester_id"] else available_actions(conn, user, r)
        return render(request, "request_detail.html", conn, user, r=r, events=events, decisions=decisions, tasks=tasks,
                      kind=kind, target=target, svc=svc, details=jl(r["details_json"], {}), actions=actions,
                      required=jl(r["required_approvals"]), pending_role=pending_approval(conn, r) if r["type"] == "A" else None,
                      sla=sla_state(r), internal_ok=internal_ok, result=result, fields=FORMS[r["type"]],
                      now=now_summary(conn, user, r),
                      readonly=user.has("admin", "auditor") and user.id != r["requester_id"])

    @app.post("/requests/{req_id}/action", dependencies=[Depends(verify_csrf)])
    async def request_action(req_id: str, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        r = get_request(conn, req_id)
        if not can_view_request(user, r):
            deny(conn, request, user, "request.action", "request", req_id)
        try:
            new = perform(conn, user, req_id, str(form.get("action", "")), str(form.get("note", "")),
                          str(form.get("result_ref", "")), corr=corr(request))
            flash(request, f"{req_id} is now: {new}", "bad" if new == "Provision Failed" else "good")
        except NotAllowed as e:
            conn.commit()
            flash(request, str(e), "bad")
            return RedirectResponse(f"/requests/{req_id}", status_code=303)
        except WorkflowError as e:
            flash(request, str(e), "bad")
        return RedirectResponse(f"/requests/{req_id}", status_code=303)

    @app.post("/requests/{req_id}/comment", dependencies=[Depends(verify_csrf)])
    async def request_comment(req_id: str, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        r = get_request(conn, req_id)
        oversight_only = user.has("auditor", "admin") and r is not None and user.id != r["requester_id"]
        if not can_view_request(user, r) or oversight_only:
            deny(conn, request, user, "request.comment", "request", req_id, status=403 if r else 404)
        try:
            add_comment(conn, user, r, str(form.get("body", "")), form.get("internal") == "1", corr=corr(request))
            flash(request, "Comment added.")
        except WorkflowError as e:
            flash(request, str(e), "bad")
        return RedirectResponse(f"/requests/{req_id}#timeline", status_code=303)

    # --------------------------------------------------------------------- workspace

    @app.get("/workspace", response_class=HTMLResponse)
    def workspace(request: Request, tab: str = "requests", conn=DB, user=Depends(current_user)):
        mine = conn.execute("SELECT * FROM requests WHERE requester_id=? ORDER BY updated_at DESC", (user.id,)).fetchall()
        # Group by who holds the ball: things only I can move, things others are working on, finished.
        groups = {"you": [], "others": [], "done": []}
        for r in mine:
            n = now_summary(conn, user, r)
            groups["done" if r["status"] in TERMINAL else "you" if n["you"] else "others"].append((r, n))
        ents = conn.execute("SELECT * FROM entitlements WHERE user_id=? ORDER BY granted_at DESC", (user.id,)).fetchall()
        governed = []
        if user.owned_domains or user.has("platform", "bi"):
            for e in conn.execute("SELECT * FROM entitlements WHERE revoked_at IS NULL ORDER BY granted_at DESC"):
                _, obj = resolve_target(conn, f"{e['object_type']}:{e['object_id']}")
                if obj is not None and (obj["domain_id"] in user.owned_domains):
                    governed.append((e, obj))
        objs = {}
        for e in list(ents) + [g[0] for g in governed]:
            _, obj = resolve_target(conn, f"{e['object_type']}:{e['object_id']}")
            objs[e["id"]] = obj
        return render(request, "workspace.html", conn, user, tab=tab, mine=mine, queue=my_queue(conn, user),
                      ents=ents, governed=governed, objs=objs, groups=groups, sla_state=sla_state,
                      now=iso(utcnow()))

    @app.post("/entitlements/{ent_id}/revoke", dependencies=[Depends(verify_csrf)])
    async def revoke(ent_id: int, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        e = conn.execute("SELECT * FROM entitlements WHERE id=? AND revoked_at IS NULL", (ent_id,)).fetchone()
        if not e:
            raise HTTPException(404)
        _, obj = resolve_target(conn, f"{e['object_type']}:{e['object_id']}")
        if obj is None or obj["domain_id"] not in user.owned_domains:
            deny(conn, request, user, "entitlement.revoke", e["object_type"], e["object_id"], status=403)
        reason = str(form.get("reason", "")).strip()[:300]
        if not reason or pii.scan(reason):
            flash(request, "Give a revocation reason without customer identifiers.", "bad")
            return RedirectResponse("/workspace?tab=access", status_code=303)
        conn.execute("UPDATE entitlements SET revoked_at=?, revoked_by=?, revoke_reason=? WHERE id=?",
                     (iso(utcnow()), user.id, reason, ent_id))
        notify(conn, [e["user_id"]], f"Your access to {obj['title']} was revoked", "/workspace?tab=access")
        audit.log(conn, user.id, "entitlement.revoke", e["object_type"], e["object_id"],
                  details={"entitlement": ent_id, "holder": e["user_id"], "request": e["request_id"],
                           "reason_recorded": True},
                  correlation_id=corr(request))
        flash(request, f"Access revoked at source ({e['system']}). Reason recorded on the entitlement.")
        return RedirectResponse("/workspace?tab=access", status_code=303)

    @app.get("/notifications", response_class=HTMLResponse)
    def notifications(request: Request, conn=DB, user=Depends(current_user)):
        rows = conn.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY at DESC LIMIT 60", (user.id,)).fetchall()
        resp = render(request, "notifications.html", conn, user, rows=rows)
        conn.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user.id,))
        return resp

    # --------------------------------------------------------------------- service management

    @app.get("/service/metrics", response_class=HTMLResponse)
    def service_metrics(request: Request, conn=DB, user=Depends(current_user)):
        if not can_view_service_metrics(user):
            deny(conn, request, user, "metrics.view", "page", "metrics", status=403)
        m = metrics.compute(conn)
        return render(request, "metrics.html", conn, user, m=m, chain=audit.verify(conn), tests=_load_tests(),
                      gen=generator.telemetry(conn))

    @app.get("/admin", response_class=HTMLResponse)
    def admin(request: Request, conn=DB, user=Depends(current_user)):
        if not can_admin(user):
            deny(conn, request, user, "admin.view", "page", "admin", status=403)
        return render(request, "admin.html", conn, user,
                      services=conn.execute("SELECT * FROM service_definitions ORDER BY type").fetchall(),
                      flags={r["key"]: r for r in conn.execute("SELECT * FROM system_flags")},
                      syncs=conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 8").fetchall(),
                      domain_rows=conn.execute("SELECT * FROM domains ORDER BY name").fetchall(),
                      outbox=conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 12").fetchall(),
                      stale=conn.execute("SELECT COUNT(*) c FROM dashboards WHERE sync_status!='ok'").fetchone()["c"],
                      boundary=generator.PHASE1_BOUNDARY, info=generator.planner_info())

    @app.post("/admin/service/{rtype}", dependencies=[Depends(verify_csrf)])
    async def admin_service(rtype: str, request: Request, conn=DB, user=Depends(current_user)):
        if not can_admin(user):
            deny(conn, request, user, "admin.service_update", "service", rtype, status=403)
        form = await request.form()
        svc = conn.execute("SELECT * FROM service_definitions WHERE type=?", (rtype,)).fetchone()
        if not svc:
            raise HTTPException(404)
        try:
            sla = max(1, min(int(form.get("sla_days", svc["sla_days"])), 180))
        except ValueError:
            sla = svc["sla_days"]
        active = 1 if form.get("active") == "1" else 0
        if (sla, active) != (svc["sla_days"], svc["active"]):
            new_version, bumped = re.subn(r"v(\d+)\.(\d+)", lambda m: f"v{m[1]}.{int(m[2]) + 1}",
                                          svc["policy_version"], count=1)
            if not bumped:
                new_version += " (rev)"
            conn.execute("UPDATE service_definitions SET sla_days=?, active=?, policy_version=?, updated_at=?, updated_by=?"
                         " WHERE type=?", (sla, active, new_version, iso(utcnow()), user.id, rtype))
            audit.log(conn, user.id, "admin.service_update", "service", rtype,
                      details={"before": {"sla_days": svc["sla_days"], "active": svc["active"], "version": svc["policy_version"]},
                               "after": {"sla_days": sla, "active": active, "version": new_version}},
                      correlation_id=corr(request))
            flash(request, f"Service {rtype} updated → {new_version}. Change recorded in audit trail.")
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/flags", dependencies=[Depends(verify_csrf)])
    async def admin_flags(request: Request, conn=DB, user=Depends(current_user)):
        if not can_admin(user):
            deny(conn, request, user, "admin.flag", "flag", "", status=403)
        form = await request.form()
        key, value = form.get("key"), "on" if form.get("value") == "on" else "off"
        if key not in ("iam_outage", "tableau_outage"):
            raise HTTPException(404)
        conn.execute("UPDATE system_flags SET value=?, updated_at=?, updated_by=? WHERE key=?", (value, iso(utcnow()), user.id, key))
        audit.log(conn, user.id, "admin.simulate_outage", "flag", key, details={"value": value}, correlation_id=corr(request))
        flash(request, f"Simulation: {key.replace('_', ' ')} is now {value.upper()}.", "bad" if value == "on" else "good")
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/sync", dependencies=[Depends(verify_csrf)])
    def admin_sync(request: Request, conn=DB, user=Depends(current_user)):
        if not can_admin(user):
            deny(conn, request, user, "admin.sync", "sync", "tableau", status=403)
        now = utcnow()
        n = conn.execute("SELECT COUNT(*) c FROM dashboards").fetchone()["c"]
        if get_flag(conn, "tableau_outage") == "on":
            conn.execute("UPDATE dashboards SET sync_status='stale'")
            conn.execute("INSERT INTO sync_runs(at, source, status, items, detail, actor_id) VALUES (?,?,?,?,?,?)",
                         (iso(now), "Tableau metadata (simulated)", "failed", 0,
                          "Tableau REST API unreachable — all items flagged stale; certification shown as unverified", user.id))
            audit.log(conn, user.id, "metadata.sync", "sync", "tableau", result="failed", correlation_id=corr(request))
            flash(request, "Sync failed: Tableau API unavailable. Dashboards marked stale — certification no longer shown as verified.", "bad")
        else:
            conn.execute("UPDATE dashboards SET sync_status='ok', sync_ts=?", (iso(now),))
            conn.execute("INSERT INTO sync_runs(at, source, status, items, detail, actor_id) VALUES (?,?,?,?,?,?)",
                         (iso(now), "Tableau metadata (simulated)", "success", n,
                          "Synchronised title, owner, project, tags, certification, lifecycle", user.id))
            audit.log(conn, user.id, "metadata.sync", "sync", "tableau", details={"items": n}, correlation_id=corr(request))
            flash(request, f"Tableau metadata synchronised ({n} views).")
        return RedirectResponse("/admin", status_code=303)

    # --------------------------------------------------------------------- audit & evidence

    def _audit_rows(conn, actor, action, result, limit=400):
        sql, args = "SELECT * FROM audit_events WHERE 1=1", []
        if actor:
            sql += " AND actor_id=?"
            args.append(actor)
        if action:
            sql += " AND action LIKE ?"
            args.append(action + "%")
        if result:
            sql += " AND result=?"
            args.append(result)
        return conn.execute(sql + " ORDER BY seq DESC LIMIT ?", (*args, limit)).fetchall()

    @app.get("/audit", response_class=HTMLResponse)
    def audit_page(request: Request, actor: str = "", action: str = "", result: str = "", conn=DB,
                   user=Depends(current_user)):
        if not can_view_audit(user):
            deny(conn, request, user, "audit.view", "page", "audit", status=403)
        audit.log(conn, user.id, "audit.view", "page", "audit", correlation_id=corr(request))
        actions = sorted({r["action"].split(".")[0] for r in conn.execute("SELECT DISTINCT action FROM audit_events")})
        return render(request, "audit.html", conn, user, rows=_audit_rows(conn, actor, action, result), chain=audit.verify(conn),
                      sel=dict(actor=actor, action=action, result=result), actions=actions,
                      total=conn.execute("SELECT COUNT(*) c FROM audit_events").fetchone()["c"])

    @app.get("/audit/export.csv")
    def audit_export(request: Request, conn=DB, user=Depends(current_user)):
        if not can_view_audit(user):
            deny(conn, request, user, "audit.export", "page", "audit", status=403)
        audit.log(conn, user.id, "audit.export", "page", "audit", correlation_id=corr(request))
        buf = io.StringIO()
        w = csv.writer(buf)
        cols = ["seq", "event_id", "ts", "actor_id", "action", "object_type", "object_id", "result", "correlation_id",
                "details", "prev_hash", "hash"]
        w.writerow(cols)
        for r in conn.execute("SELECT * FROM audit_events ORDER BY seq"):
            w.writerow([r[c] for c in cols])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=hub-audit-evidence.csv"})

    def _load_tests():
        if not EVIDENCE_XML.exists():
            return None
        root = ElementTree.parse(EVIDENCE_XML).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        cases = []
        for tc in suite.iter("testcase"):
            failed = tc.find("failure") is not None or tc.find("error") is not None
            props = {p.get("name"): p.get("value") for p in tc.iter("property")}
            name = tc.get("name")
            cases.append({"name": name, "classname": tc.get("classname", "").split(".")[-1], "ok": not failed,
                          "ref": props.get("prd_ref", ""), "title": props.get("title") or name.replace("test_", "").replace("_", " "),
                          "kind": "Negative" if "negative" in tc.get("classname", "") else "Positive"})
        cases.sort(key=lambda c: c["kind"] != "Positive")
        return {"cases": cases, "passed": sum(c["ok"] for c in cases), "total": len(cases),
                "timestamp": suite.get("timestamp", ""), "time": suite.get("time", "")}

    @app.get("/evidence", response_class=HTMLResponse)
    def evidence(request: Request, conn=DB, user=Depends(current_user)):
        if not user.has("auditor", "governance", "admin", "data_owner", "bi", "platform"):
            deny(conn, request, user, "evidence.view", "page", "evidence", status=403)
        gates = conn.execute("SELECT * FROM release_gates ORDER BY ord").fetchall()
        tests = _load_tests()
        chain = audit.verify(conn)
        m = metrics.compute(conn)
        return render(request, "evidence.html", conn, user, gates=gates, tests=tests, chain=chain, m=m,
                      signed=sum(1 for g in gates if g["status"] == "signed"))

    @app.post("/release-gates/{gate_id}/sign", dependencies=[Depends(verify_csrf)])
    async def sign_gate(gate_id: str, request: Request, conn=DB, user=Depends(current_user)):
        form = await request.form()
        g = conn.execute("SELECT * FROM release_gates WHERE id=?", (gate_id,)).fetchone()
        if not g:
            raise HTTPException(404)
        if g["owner_role"] not in user.roles:
            deny(conn, request, user, "gate.sign", "gate", gate_id, status=403)
        note = str(form.get("note", "")).strip()
        if not note:
            flash(request, "A reference / note is required to sign off.", "bad")
            return RedirectResponse("/evidence#gates", status_code=303)
        signed = conn.execute("UPDATE release_gates SET status='signed', signed_by=?, signed_at=?, note=?"
                              " WHERE id=? AND status!='signed'", (user.id, iso(utcnow()), note[:300], gate_id))
        if not signed.rowcount:  # a sign-off is evidence; it is never overwritten
            flash(request, f"Gate {gate_id} is already signed by {g['signed_by']}.", "bad")
            return RedirectResponse("/evidence#gates", status_code=303)
        audit.log(conn, user.id, "gate.sign", "gate", gate_id, correlation_id=corr(request))
        flash(request, f"Gate {gate_id} signed off.")
        return RedirectResponse("/evidence#gates", status_code=303)

    return app
