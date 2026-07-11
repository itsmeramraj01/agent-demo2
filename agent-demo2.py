"""Travel Agent CLI powered by Claude (Anthropic API).

Run from a terminal: python agent-demo2.py
Collects vacation preferences interactively, then asks Claude to suggest
destinations and flight options based on the answers.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096


def load_api_key() -> str:
    env_path = Path(__file__).resolve().parent / "config.env"
    load_dotenv(dotenv_path=env_path)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or api_key == "your_anthropic_api_key_here":
        sys.exit(
            f"ANTHROPIC_API_KEY is not set. Add it to {env_path} "
            "(get a key at https://console.anthropic.com/settings/keys)."
        )
    return api_key


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def collect_preferences() -> dict:
    print("=== Vacation Planner ===")
    print("Answer a few questions and Claude will suggest a trip.\n")

    prefs = {
        "origin": ask("Departure city/airport"),
        "travelers": ask("Number of travelers", "1"),
        "duration": ask("Trip length (e.g. 5 days, 1 week)"),
        "budget": ask("Budget (e.g. $2000 total, flexible)", "flexible"),
        "travel_window": ask("Preferred travel dates or month"),
        "vibe": ask("Vacation style (beach, mountains, city, adventure, relaxation, culture...)"),
        "interests": ask("Specific interests or must-haves (food, hiking, nightlife, museums...)"),
        "climate": ask("Climate preference (warm, cold, no preference)", "no preference"),
        "pace": ask("Pace (relaxed, balanced, packed itinerary)", "balanced"),
        "notes": ask("Anything else Claude should know? (allergies, mobility, visa constraints...)", "none"),
    }
    return prefs


def build_prompt(prefs: dict) -> str:
    return f"""A traveler wants vacation guidance. Their details:

- Departure city/airport: {prefs['origin']}
- Number of travelers: {prefs['travelers']}
- Trip length: {prefs['duration']}
- Budget: {prefs['budget']}
- Preferred travel dates/month: {prefs['travel_window']}
- Vacation style: {prefs['vibe']}
- Interests: {prefs['interests']}
- Climate preference: {prefs['climate']}
- Pace: {prefs['pace']}
- Additional notes: {prefs['notes']}

Based on this, please:
1. Recommend 3 well-matched vacation destinations, each with a short rationale tied to their preferences.
2. For each destination, suggest realistic flight options from their departure city (typical airlines/routing, approximate flight time, and a rough price range) - make clear these are estimates, not live bookings.
3. Give a brief day-by-day style outline (or highlights) for the top recommendation.
4. Flag any budget, timing, or logistical concerns worth considering.

Keep the response well-organized with headers, concise but useful.
"""


def main() -> None:
    api_key = load_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    prefs = collect_preferences()
    prompt = build_prompt(prefs)

    print("\nAsking Claude for vacation guidance...\n")

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            print(block.text)


if __name__ == "__main__":
    main()
