"""Loopback-only UI with request authentication, origin checks and a fixed API."""
from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .controller import ROOT, Organizer
from .core import SortError


def make_server(organizer: Organizer, port: int = 8766) -> ThreadingHTTPServer:
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None:
            pass  # Do not log private API bodies or tokens.

        def respond(self, status: int, data: object, content_type: str = "application/json; charset=utf-8") -> None:
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def host_ok(self) -> bool:
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in allowed:
                self.respond(403, {"error": "只接受本机地址。"})
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + value for value in allowed}:
                self.respond(403, {"error": "拒绝其他网页的请求。"})
                return False
            return True

        def authorized(self) -> bool:
            if not self.host_ok():
                return False
            supplied = self.headers.get("X-AppSort-Token", "")
            if not secrets.compare_digest(token, supplied):
                self.respond(403, {"error": "本地会话已过期，请刷新页面。"})
                return False
            return True

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if not self.host_ok():
                return
            if path == "/":
                text = (ROOT / "web/index.html").read_text().replace("__SESSION_TOKEN__", token)
                self.respond(200, text.encode(), "text/html; charset=utf-8")
            elif path == "/favicon.ico":
                self.respond(204, b"", "image/x-icon")
            elif path.startswith("/icons/"):
                supplied = parse_qs(urlsplit(self.path).query).get("token", [""])[0]
                name = path.removeprefix("/icons/")
                if not secrets.compare_digest(token, supplied) or len(name) != 68 or not name.endswith(".png") or any(c not in "0123456789abcdef" for c in name[:-4]):
                    self.respond(403, {"error": "无效请求。"})
                    return
                image = organizer.state / "icons" / name
                self.respond(200, image.read_bytes(), "image/png") if image.exists() else self.respond(404, {})
            elif path == "/api/state" and self.authorized():
                self.respond(200, organizer.view())
            elif path == "/api/devices" and self.authorized():
                try:
                    self.respond(200, {"devices": organizer.adapter.inventory() if not organizer.demo else []})
                except (SortError, OSError) as error:
                    self.respond(400, {"error": str(error)})
            elif path == "/api/export" and self.authorized():
                view = organizer.view()
                self.respond(200, {"device": view["device"], "usage": view["usage"], "proposal": view["proposal"],
                                   "current": view["current"], "proposed": view["proposed"]})
            else:
                self.respond(404, {"error": "没有这个接口。"})

        def do_POST(self) -> None:
            if not self.authorized():
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.respond(415, {"error": "需要 JSON。"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= 2 * 1024 * 1024:
                    raise SortError("请求过大。")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise SortError("请求格式无效。")
                route = urlsplit(self.path).path
                if route == "/api/read":
                    result = organizer.read_phone(str(body.get("udid", "")))
                elif route == "/api/copy-usage":
                    result = organizer.copy_usage()
                elif route == "/api/usage":
                    result = organizer.collect(str(body.get("stream", "")), int(body.get("days", 7)))
                elif route == "/api/import":
                    result = organizer.import_usage(str(body.get("csv", "")), int(body.get("days", 7)))
                elif route == "/api/propose":
                    result = organizer.propose({"metric": body.get("metric", "opens"), "days": body.get("days", 7),
                                               "folders": body.get("folders", "flatten"), "capacity": body.get("capacity", 8),
                                               "pinned": body.get("pinned", []), "widget_mode": body.get("widget_mode", "separate"),
                                               "page_limit": body.get("page_limit", 15)})
                elif route == "/api/profile":
                    result = organizer.save_profile(str(body.get("name", "")), body.get("options", {}))
                elif route in ("/api/test", "/api/apply", "/api/restore"):
                    if body.get("confirmed") is not True:
                        raise SortError("请先确认具体操作及小组件说明。")
                    backend = str(body.get("backend", "native"))
                    if route == "/api/test":
                        result = organizer.test(backend, str(body.get("expected_hash", "")))
                    elif route == "/api/apply":
                        result = organizer.apply(backend, str(body.get("proposal_hash", "")))
                    else:
                        result = organizer.restore(str(body.get("backup", "")), backend)
                else:
                    self.respond(404, {"error": "没有这个接口。"})
                    return
                self.respond(200, result)
            except (SortError, ValueError, TypeError, KeyError, OSError) as error:
                self.respond(400, {"error": str(error)})
            except Exception as error:
                self.respond(500, {"error": "操作没有完成：" + type(error).__name__ + ": " + str(error)})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
