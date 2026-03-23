from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from ._shared import json_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        payload = {
            "name": "Reflex Alpha",
            "type": "backend-api",
            "status": "ready",
            "endpoints": {
                "health": "/health",
                "backtest": "/backtest?points=420&seed=7&capital=10000",
                "live_simulation": "/live-simulation?live_steps=40&warmup=60&seed=7&capital=10000",
            },
        }
        json_response(self, 200, payload)
