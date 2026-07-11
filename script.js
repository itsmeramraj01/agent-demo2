// Floating travel-planner chat widget.
// Mirrors the terminal Q&A flow from agent-demo2.py, then calls /api/plan
// (a Python serverless function running the same Claude prompt logic).

const QUESTIONS = [
  { key: "origin", prompt: "Where are you departing from (city/airport)?", default: "" },
  { key: "travelers", prompt: "How many travelers?", default: "1" },
  { key: "duration", prompt: "How long is the trip? (e.g. 5 days, 1 week)", default: "" },
  { key: "budget", prompt: "What's your budget? (e.g. $2000 total, or 'flexible')", default: "flexible" },
  { key: "travel_window", prompt: "Preferred travel dates or month?", default: "" },
  { key: "vibe", prompt: "Vacation style? (beach, mountains, city, adventure, relaxation, culture...)", default: "" },
  { key: "interests", prompt: "Any specific interests or must-haves? (food, hiking, nightlife, museums...)", default: "" },
  { key: "climate", prompt: "Climate preference? (warm, cold, or no preference)", default: "no preference" },
  { key: "pace", prompt: "Preferred pace? (relaxed, balanced, packed itinerary)", default: "balanced" },
  { key: "notes", prompt: "Anything else I should know? (allergies, mobility, visa constraints...)", default: "none" },
];

const widget = document.getElementById("chat-widget");
const fab = document.getElementById("chat-fab");
const openBtn = document.getElementById("open-chat");
const closeBtn = document.getElementById("close-chat");
const messagesEl = document.getElementById("chat-messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");

let step = 0;
let answers = {};
let started = false;
let awaitingReply = false;

function openWidget() {
  widget.classList.remove("closed");
  input.focus();
  if (!started) {
    started = true;
    startConversation();
  }
}

function closeWidget() {
  widget.classList.add("closed");
}

fab.addEventListener("click", openWidget);
openBtn.addEventListener("click", openWidget);
closeBtn.addEventListener("click", closeWidget);

function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.innerHTML = cls === "bot-html" ? text : escapeHtml(text);
  if (cls === "bot-html") div.className = "msg bot";
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

// Very small markdown-ish renderer for Claude's reply (headers, bold, bullets).
function renderReply(text) {
  const escaped = escapeHtml(text);
  return escaped
    .split("\n")
    .map((line) => {
      if (/^\s*#{1,4}\s+/.test(line)) {
        return `<strong>${line.replace(/^\s*#{1,4}\s+/, "")}</strong>`;
      }
      if (/^\s*[-*]\s+/.test(line)) {
        return `&nbsp;&nbsp;• ${line.replace(/^\s*[-*]\s+/, "")}`;
      }
      return line;
    })
    .join("\n")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function startConversation() {
  addMessage(
    "Hi! I'm your AI travel planner. Answer a few quick questions and I'll suggest destinations, flight options, and an itinerary.",
    "bot"
  );
  askCurrentQuestion();
}

function askCurrentQuestion() {
  const q = QUESTIONS[step];
  const hint = q.default ? ` (press Enter to use "${q.default}")` : "";
  addMessage(q.prompt + hint, "bot");
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  if (awaitingReply) return;

  const value = input.value.trim();
  input.value = "";

  if (step < QUESTIONS.length) {
    const q = QUESTIONS[step];
    const finalValue = value || q.default;
    addMessage(value || "(skipped)", "user");
    answers[q.key] = finalValue;
    step += 1;

    if (step < QUESTIONS.length) {
      askCurrentQuestion();
    } else {
      submitToClaude();
    }
  } else {
    // Conversation already finished — treat any input as "plan another trip".
    addMessage(value || "(start over)", "user");
    resetConversation();
  }
});

async function submitToClaude() {
  awaitingReply = true;
  input.disabled = true;
  const loadingEl = addMessage("Asking Claude for vacation guidance...", "loading");

  try {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(answers),
    });

    const data = await res.json();
    loadingEl.remove();

    if (!res.ok) {
      addMessage(data.error || "Something went wrong. Please try again.", "error");
    } else {
      addMessage(renderReply(data.reply), "bot-html");
      addMessage("Want to plan another trip? Type anything to start over.", "bot");
    }
  } catch (err) {
    loadingEl.remove();
    addMessage("Network error — could not reach the planner. Please try again.", "error");
  } finally {
    awaitingReply = false;
    input.disabled = false;
    input.focus();
  }
}

function resetConversation() {
  step = 0;
  answers = {};
  askCurrentQuestion();
}
