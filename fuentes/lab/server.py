#!/usr/bin/env python3
"""A read-only, synthetic carrier portal for the take-home. Not an extractor."""

from __future__ import annotations

import argparse
import copy
import html
import json
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent
SCENARIOS = ("baseline", "corrected", "failure", "drift")
PAGE_SIZE = 2


def source_data(scenario: str) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown scenario")
    data = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    if scenario == "corrected":
        data["source_as_of"] = "2026-11-03T12:00:00Z"
        receipt = data["brokers"]["alder"]["receipts"][2]
        receipt.update(amount="30.00", revision=2)
    return data


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def page_html(title: str, content: str, broker: str | None = None) -> str:
    nav = ""
    if broker:
        nav = (
            '<nav aria-label="Carrier records"><a href="/policies">Policies</a>'
            '<a href="/receipts">Receipts</a></nav>'
            '<form action="/logout" method="post"><button class="quiet">Sign out</button></form>'
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)} · Brújula</title>'
        '<link rel="stylesheet" href="/static/tokens.css">'
        '<link rel="stylesheet" href="/static/style.css"></head><body>'
        '<a class="skip" href="#main">Skip to records</a>'
        '<header><a class="brand" href="/">Brújula <span>Seguros</span></a>'
        f'{nav}</header><main id="main">{content}</main>'
        '<footer>Fictional carrier · Synthetic records · Local assessment environment</footer>'
        '</body></html>'
    )


def login_html(error: str = "") -> str:
    alert = f'<p class="notice" role="alert">{esc(error)}</p>' if error else ""
    return page_html(
        "Broker access",
        '<section class="login" data-od-id="broker-access"><p class="context">Broker portal</p><h1>Access your book</h1>'
        '<p>Review policy records and receipt statements for your brokerage.</p>'
        f'{alert}<form action="/login" method="post" class="login-form">'
        '<label for="username">Broker account</label>'
        '<input id="username" name="username" autocomplete="username" required>'
        '<label for="password">Password</label>'
        '<input id="password" name="password" type="password" autocomplete="current-password" required>'
        '<button type="submit">Open broker book</button></form>'
        '<aside class="demo-note"><strong>Demo access</strong>'
        '<p>Account <code>alder</code> or <code>birch</code> · password <code>demo</code>.</p>'
        '<p>These are fictional accounts. Do not enter real credentials.</p></aside></section>',
    )


def records_html(data: dict, broker: str, entity: str, rows: list[dict], page: int = 1,
                 total: int | None = None, drift: bool = False) -> str:
    account = data["brokers"][broker]
    if entity == "policies":
        columns = [("policy_number", "Policy"), ("customer_reference", "Customer reference"),
                   ("line_of_business", "Line of business"), ("status", "Status")]
    else:
        columns = [("receipt_number", "Receipt"), ("policy_number", "Policy"),
                   ("amount", "Installment amount" if not drift else "Installment value"),
                   ("currency", "Currency"), ("status", "Status"),
                   ("due_date", "Due date"), ("revision", "Revision")]
    headings = "".join(f'<th scope="col">{label}</th>' for _, label in columns)
    body = []
    for row in rows:
        cells = []
        for key, _ in columns:
            value = "Not supplied" if key not in row else "Not stated (null)" if row[key] is None else row[key]
            rendered = esc(value)
            if key == "receipt_number":
                rendered = f'<a href="/receipts/{esc(value)}">{rendered}</a>'
            cells.append(f'<td class="field-{key}">{rendered}</td>')
        body.append('<tr>' + ''.join(cells) + '</tr>')
    total = len(rows) if total is None else total
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    pager = ""
    if entity == "receipts":
        back = f'<a href="/receipts?page={page - 1}">Previous page</a>' if page > 1 else '<span>Previous page</span>'
        forward = f'<a href="/receipts?page={page + 1}">Next page</a>' if page < pages else '<span>Next page</span>'
        pager = f'<nav class="pager" aria-label="Receipt pages">{back}<span>Page {page} of {pages} · {total} source rows</span>{forward}</nav>'
    content = (
        f'<p class="context">{esc(account["name"])} · Broker account <code>{esc(broker)}</code></p>'
        f'<div class="heading"><h1>{esc(entity.title())}</h1><span class="as-of">Source as of {esc(data["source_as_of"])}</span></div>'
        '<p class="source-note">Carrier records as reported. Workflow holds are managed by the brokerage.</p>'
        f'<div class="table-scroll" role="region" aria-label="{esc(entity)} table" tabindex="0">'
        f'<table><caption>{esc(account["name"])} {esc(entity)}</caption><thead><tr>{headings}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div>{pager}'
        f'<p class="export"><a href="/api/{entity}?page={page}">View this source response as JSON</a></p>'
    )
    return page_html(entity.title(), content, broker)


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], scenario: str):
        self.data = source_data(scenario)
        self.scenario = scenario
        self.sessions: dict[str, str] = {}
        super().__init__(address, PortalHandler)


class PortalHandler(BaseHTTPRequestHandler):
    server: PortalServer

    def log_message(self, format: str, *args: object) -> None:
        # No request-body or credential logging; a quiet demo source.
        pass

    def respond(self, status: int, body: str | bytes = b"", kind: str = "text/html; charset=utf-8",
                headers: dict[str, str] | None = None) -> None:
        payload = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def json_response(self, status: int, payload: dict) -> None:
        self.respond(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def broker(self) -> str | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        token = cookie.get("carrier_session")
        return self.server.sessions.get(token.value) if token else None

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/logout":
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie.get("carrier_session")
            if token:
                self.server.sessions.pop(token.value, None)
            self.respond(303, headers={"Location": "/login", "Set-Cookie": "carrier_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax"})
            return
        if path != "/login":
            self.json_response(405, {"error": "read_only_portal"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 <= length <= 2048:
            self.json_response(400, {"error": "invalid_login_request"})
            return
        try:
            fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        except UnicodeDecodeError:
            self.json_response(400, {"error": "invalid_login_request"})
            return
        username = fields.get("username", [""])[0]
        if username not in self.server.data["brokers"] or fields.get("password") != ["demo"]:
            self.respond(401, login_html("Account or password not recognized. Use one of the demo accounts below."))
            return
        token = secrets.token_urlsafe(24)
        self.server.sessions[token] = username
        self.respond(303, headers={"Location": "/receipts", "Set-Cookie": f"carrier_session={token}; Path=/; HttpOnly; SameSite=Lax"})

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        path, query = unquote(parsed.path), parse_qs(parsed.query)
        if path in ("/static/tokens.css", "/static/style.css"):
            self.respond(200, (ROOT / path.lstrip("/")).read_bytes(), "text/css; charset=utf-8")
            return
        if path == "/login":
            self.respond(200, login_html())
            return
        broker = self.broker()
        if not broker:
            if path.startswith("/api/"):
                self.json_response(401, {"error": "login_required"})
            else:
                self.respond(303, headers={"Location": "/login"})
            return
        if any(key in query for key in ("tenant", "broker", "account")):
            self.json_response(400, {"error": "account_is_selected_by_session"})
            return
        if path == "/":
            self.respond(303, headers={"Location": "/receipts"})
            return
        is_api = path.startswith("/api/")
        route = path.removeprefix("/api") if is_api else path
        parts = route.strip("/").split("/")
        if parts[0] not in ("policies", "receipts") or len(parts) > 2:
            self.json_response(404, {"error": "not_found"})
            return
        entity = parts[0]
        rows = copy.deepcopy(self.server.data["brokers"][broker][entity])
        try:
            page = int(query.get("page", ["1"])[0])
        except ValueError:
            page = 0
        pages = max(1, (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        if not 1 <= page <= pages or (entity == "policies" and page != 1):
            self.json_response(400, {"error": "invalid_page"})
            return
        detail = len(parts) == 2
        if detail:
            key = "receipt_number" if entity == "receipts" else "policy_number"
            selected = next((row for row in rows if row[key] == parts[1]), None)
            if selected is None:
                self.json_response(404, {"error": "not_found_in_this_account"})
                return
            page = 1 + rows.index(selected) // PAGE_SIZE
            shown = [selected]
        else:
            shown = rows if entity == "policies" else rows[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]
        if self.server.scenario == "failure" and broker == "alder" and entity == "receipts" and page == 2:
            self.json_response(503, {"error": "statement_temporarily_unavailable", "retryable": True})
            return
        drift = self.server.scenario == "drift" and broker == "alder" and entity == "receipts" and page == 2
        if is_api:
            payload = {"broker": broker, "source_as_of": self.server.data["source_as_of"], "page": page,
                       "total_rows": len(rows), "next_page": page + 1 if not detail and entity == "receipts" and page < pages else None}
            payload["record" if detail else "items" if drift else entity] = shown[0] if detail else shown
            self.json_response(200, payload)
        else:
            self.respond(200, records_html(self.server.data, broker, entity, shown, page, len(rows), drift))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="baseline")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = PortalServer(("127.0.0.1", args.port), args.scenario)
    print(f"Brújula demo: http://127.0.0.1:{server.server_port} · {args.scenario}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
