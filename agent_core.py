"""Shared Claude prompt + agentic tool-use loop for the travel planner.

Used by both the terminal CLI (agent-demo2.py) and the Vercel serverless
functions (api/plan.py, api/ask.py) so the itinerary prompt and the
retrieval-augmented tool loop behave identically everywhere.
"""

import traceback

from rag import SEARCH_POLICIES_TOOL, search_policies

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 4

TOOLS = [SEARCH_POLICIES_TOOL]

PLANNER_SYSTEM_PROMPT = """You are Wanderly's AI travel planning assistant.

You have a search_travel_policies tool backed by Wanderly's knowledge base of
cancellation, baggage, and travel insurance policies. Use it whenever a
traveler's notes or questions touch on those topics, so you can cite accurate
policy details instead of guessing. Don't call it for unrelated questions."""


def build_itinerary_prompt(prefs: dict) -> str:
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
5. If the traveler's notes raise a cancellation, baggage, or insurance question, look it up and answer it using accurate policy details.

Keep the response well-organized with headers, concise but useful.
"""


def run_agent(client, messages: list, system: str = PLANNER_SYSTEM_PROMPT) -> str:
    """Runs the Claude <-> tool loop until Claude returns a final text answer.

    `messages` is mutated in place so callers can keep the full transcript
    (e.g. for a multi-turn follow-up chat).
    """
    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "search_travel_policies":
                try:
                    result_text = search_policies(block.input.get("query", ""))
                except Exception as exc:  # noqa: BLE001 - surface as a tool result, not a crash
                    traceback.print_exc()
                    result_text = f"Policy lookup failed: {exc}"
            else:
                result_text = f"Unknown tool: {block.name}"
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result_text}
            )
        messages.append({"role": "user", "content": tool_results})

    return "I looked into that but couldn't finish checking our policies in time - please try rephrasing your question."
