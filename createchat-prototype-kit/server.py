#!/usr/bin/env python3
"""HTTP wrapper around mock_tools, for a prototype in any language.

    python server.py               # http://127.0.0.1:8765
    python server.py --port 9000

Routes (JSON in, JSON out):
    GET  /health
    GET  /tools                          tool definitions (function-calling format)
    POST /tools/<name>                   body = tool arguments
    POST /proposals/<id>/approve         the client's Approve tap
    POST /proposals/<id>/reject          the client's Decline tap
    POST /reset                          reload the dataset (drops every change)
    GET  /state                          current records, for debugging

Who is calling: header `X-Mock-User: clt_001` (or clt_002, clt_003). Leave it
out to act as an anonymous visitor. Tool errors return HTTP 200 with an
`error` field, the same as the model would see them; only a bad request to the
server itself is a 4xx.
"""
from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mock_tools import TOOLS, MockOPAH, tool_schemas

API = MockOPAH()
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = "CreateChatMock/1.0"

    def _send(self, status: int, body) -> None:
        data = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _user(self):
        return (self.headers.get("X-Mock-User") or "").strip() or None

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("body must be a JSON object")
        return value

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Mock-User")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"status": "ok", "dataset_today": API.meta["dataset_today"]})
        if self.path == "/tools":
            return self._send(200, tool_schemas())
        if self.path == "/state":
            with LOCK:
                return self._send(200, API.snapshot())
        return self._send(404, {"error": "not_found"})

    def do_POST(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        try:
            body = self._body()
        except ValueError as exc:
            return self._send(400, {"error": "bad_request", "message": str(exc)})
        with LOCK:
            if len(parts) == 2 and parts[0] == "tools":
                if parts[1] not in TOOLS:
                    return self._send(404, {"error": "unknown_tool"})
                return self._send(200, API.call(parts[1], body, user=self._user()))
            if len(parts) == 3 and parts[0] == "proposals" and parts[2] in ("approve", "reject"):
                fn = API.approve_proposal if parts[2] == "approve" else API.reject_proposal
                return self._send(200, fn(parts[1], self._user()))
            if parts == ["reset"]:
                API.reset()
                return self._send(200, {"status": "reset"})
        return self._send(404, {"error": "not_found"})

    def log_message(self, fmt, *args):
        print(f"{self.command} {self.path} user={self._user() or 'anonymous'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="CREATEchat mock tool server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CREATEchat mock server on http://{args.host}:{args.port} (dataset day {API.meta['dataset_today']})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
