from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from ._shared import (
    as_bool,
    as_float,
    as_int,
    json_response,
    parse_query,
    run_backtest_payload,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        try:
            query = parse_query(self.path)
            points = as_int(query, "points", 180, 50, 5000)
            seed = as_int(query, "seed", 7, 0, 1_000_000)
            capital = as_float(query, "capital", 10_000.0, 100.0, 10_000_000.0)
            real_api = as_bool(query, "real_api", False)

            # Root returns real measurable output by default.
            quick_run = run_backtest_payload(
                points=points,
                seed=seed,
                capital=capital,
                real_api=real_api,
            )

            payload = {
                "name": "Reflex Alpha",
                "type": "backend-api",
                "status": "ready",
                "message": "Quick backtest executed at root endpoint.",
                "quick_backtest": quick_run,
                "endpoints": {
                    "health": "/health",
                    "backtest": "/backtest?points=420&seed=7&capital=10000",
                    "live_simulation": "/live-simulation?live_steps=40&warmup=60&seed=7&capital=10000",
                },
            }
            json_response(self, 200, payload)
        except Exception as exc:
            json_response(self, 400, {"error": str(exc)})
