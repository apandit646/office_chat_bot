// Backend address. When the page is served by FastAPI itself (http://127.0.0.1:8000) we use
// relative URLs. When it's opened as a file or from a dev server like VS Code Live Server
// (port 5500), we call the backend on port 8000 directly.
const BACKEND_URL = "http://127.0.0.1:8000";
const servedByOtherHost = location.protocol === "file:" || ["5500", "5501", "3000", "5173"].includes(location.port);
const API_BASE = servedByOtherHost ? BACKEND_URL : "";

const chat = document.getElementById("chat");
const welcome = document.getElementById("welcome");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const statusEl = document.getElementById("status");

let sessionId = sessionStorage.getItem("policy-bot-session") || null;
let busy = false;

// ---------- helpers ----------
function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Minimal markdown: paragraphs, bullet/numbered lists, **bold**, *italic*, `code`
function renderMarkdown(md) {
  const inline = (s) =>
    escapeHtml(s)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>")
      .replace(/`(.+?)`/g, "<code>$1</code>");

  const out = [];
  let list = null; // "ul" | "ol"
  const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };

  for (const raw of md.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[-*•]\s+(.*)/);
    const numbered = line.match(/^\d+[.)]\s+(.*)/);
    if (bullet || numbered) {
      const type = bullet ? "ul" : "ol";
      if (list !== type) { closeList(); out.push(`<${type}>`); list = type; }
      out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
    } else if (line === "") {
      closeList();
    } else {
      closeList();
      const heading = line.match(/^#{1,6}\s+(.*)/);
      out.push(heading ? `<p><strong>${inline(heading[1])}</strong></p>` : `<p>${inline(line)}</p>`);
    }
  }
  closeList();
  return out.join("");
}

function addMessage(role, html) {
  welcome.hidden = true;
  const row = document.createElement("div");
  row.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = html;
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
}

function sourcesHtml(sources) {
  if (!sources || !sources.length) return "";
  const items = sources
    .map((s) => `<li><span class="src-name">${escapeHtml(s.source)} · page ${s.page}</span>
      <span class="src-snippet">${escapeHtml(s.snippet)}…</span></li>`)
    .join("");
  return `<details class="sources"><summary>Sources (${sources.length})</summary><ul>${items}</ul></details>`;
}

function setBusy(value) {
  busy = value;
  sendBtn.disabled = value;
}

function autoResize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}

// ---------- API ----------
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    const data = await res.json();
    if (data.indexed_chunks > 0) {
      statusEl.textContent = `Online · ${data.indexed_chunks} policy sections indexed`;
      statusEl.className = "status ok";
    } else {
      statusEl.textContent = "No documents indexed. Run: python -m app.ingest";
      statusEl.className = "status bad";
    }
  } catch {
    statusEl.textContent = `Can't reach the backend at ${API_BASE || location.origin}. Is uvicorn running?`;
    statusEl.className = "status bad";
  }
}

async function ask(question) {
  if (busy || !question.trim()) return;
  setBusy(true);
  addMessage("user", escapeHtml(question));
  const pending = addMessage("bot", '<div class="typing"><span></span><span></span><span></span></div>');

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);

    sessionId = data.session_id;
    sessionStorage.setItem("policy-bot-session", sessionId);
    pending.querySelector(".bubble").innerHTML = renderMarkdown(data.answer) + sourcesHtml(data.sources);
  } catch (err) {
    pending.classList.add("error");
    const msg = err instanceof TypeError
      ? `Can't reach the backend at ${API_BASE || location.origin}. Start it with: uvicorn app.main:app --reload`
      : err.message;
    pending.querySelector(".bubble").textContent = `⚠ ${msg}`;
  } finally {
    setBusy(false);
    chat.scrollTop = chat.scrollHeight;
    input.focus();
  }
}

// ---------- events ----------
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value;
  input.value = "";
  autoResize();
  ask(q);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});
input.addEventListener("input", autoResize);

document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => ask(chip.dataset.q || chip.textContent.trim()))
);

document.getElementById("newChat").addEventListener("click", () => {
  sessionId = null;
  sessionStorage.removeItem("policy-bot-session");
  chat.querySelectorAll(".msg").forEach((m) => m.remove());
  welcome.hidden = false;
  input.focus();
});

checkHealth();
