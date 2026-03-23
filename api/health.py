from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from ._shared import json_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        json_response(self, 200, {"status": "ok"})
