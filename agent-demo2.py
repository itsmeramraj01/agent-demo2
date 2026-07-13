"""Travel Agent CLI powered by Claude (Anthropic API).

Run from a terminal: python agent-demo2.py
Collects vacation preferences interactively, then asks Claude to suggest
destinations and flight options based on the answers. Claude can also pull
from the Wanderly policy knowledge base (cancellation, baggage, insurance)
via an agentic tool-use loop - see agent_core.py and rag.py.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

from agent_core import build_itinerary_prompt, run_agent


def load_env() -> None:
    env_path = Path(__file__).resolve().parent / "config.env"
    load_dotenv(dotenv_path=env_path)
    if not os.environ.get("ANTHROPIC_API_KEY") or os.environ["ANTHROPIC_API_KEY"] == "your_anthropic_api_key_here":
        sys.exit(
            f"ANTHROPIC_API_KEY is not set. Add it to {env_path} "
            "(get a key at https://console.anthropic.com/settings/keys)."
        )


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


def main() -> None:
    load_env()
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prefs = collect_preferences()
    messages = [{"role": "user", "content": build_itinerary_prompt(prefs)}]

    print("\nAsking Claude for vacation guidance...\n")
    print(run_agent(client, messages))

    print("\n--- Ask a follow-up about cancellations, baggage, or insurance ---")
    print("(press Enter with no text to quit)\n")
    while True:
        question = ask("You")
        if not question:
            break
        messages.append({"role": "user", "content": question})
        print(f"\n{run_agent(client, messages)}\n")


if __name__ == "__main__":
    main()
