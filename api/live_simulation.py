from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from ._shared import as_bool, as_float, as_int, json_response, parse_query, run_live_payload


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        try:
            query = parse_query(self.path)
            live_steps = as_int(query, "live_steps", 40, 5, 1000)
            warmup = as_int(query, "warmup", 60, 10, 1000)
            seed = as_int(query, "seed", 7, 0, 1_000_000)
            capital = as_float(query, "capital", 10_000.0, 100.0, 10_000_000.0)
            real_api = as_bool(query, "real_api", False)

            payload = run_live_payload(
                live_steps=live_steps,
                warmup=warmup,
                seed=seed,
                capital=capital,
                real_api=real_api,
            )
            json_response(self, 200, payload)
        except Exception as exc:
            json_response(self, 400, {"error": str(exc)})
