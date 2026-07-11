"""Vercel serverless function powering the travel-planner chat widget.

Ports the same prompt logic as agent-demo2.py (the terminal CLI version) so
the website behaves identically, just driven by JSON instead of input().
"""

import json
import os
from http.server import BaseHTTPRequestHandler

import anthropic

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096


def build_prompt(prefs: dict) -> str:
    def get(key: str, default: str = "") -> str:
        value = (prefs.get(key) or "").strip()
        return value or default

    return f"""A traveler wants vacation guidance. Their details:

- Departure city/airport: {get('origin')}
- Number of travelers: {get('travelers', '1')}
- Trip length: {get('duration')}
- Budget: {get('budget', 'flexible')}
- Preferred travel dates/month: {get('travel_window')}
- Vacation style: {get('vibe')}
- Interests: {get('interests')}
- Climate preference: {get('climate', 'no preference')}
- Pace: {get('pace', 'balanced')}
- Additional notes: {get('notes', 'none')}

Based on this, please:
1. Recommend 3 well-matched vacation destinations, each with a short rationale tied to their preferences.
2. For each destination, suggest realistic flight options from their departure city (typical airlines/routing, approximate flight time, and a rough price range) - make clear these are estimates, not live bookings.
3. Give a brief day-by-day style outline (or highlights) for the top recommendation.
4. Flag any budget, timing, or logistical concerns worth considering.

Keep the response well-organized with headers, concise but useful.
"""


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            prefs = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body."})
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._send_json(
                500, {"error": "Server is missing ANTHROPIC_API_KEY. Set it in the Vercel project's environment variables."}
            )
            return

        client = anthropic.Anthropic(api_key=api_key)
        prompt = build_prompt(prefs)

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 - surface any Claude API failure to the widget
            self._send_json(502, {"error": f"Claude request failed: {exc}"})
            return

        text = "".join(block.text for block in response.content if block.type == "text")
        self._send_json(200, {"reply": text})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
