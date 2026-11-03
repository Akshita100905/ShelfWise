/* =========================================================
   ShelfWise AI chat. The same assistant powers the mic:
   it can read your household data and ADD items / notes.
   ========================================================= */

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

/* Small, safe markdown: everything is escaped FIRST, then a few patterns become tags. */
function renderMarkdown(text) {
  const lines = escapeHtml(text).split("\n");
  const inline = (t) => t
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*(?!\s)(.+?)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
  let html = "", list = null;
  const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    let m;
    if ((m = line.match(/^\s*[*\-•]\s+(.*)$/))) {
      if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
      html += `<li>${inline(m[1])}</li>`;
    } else if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
      if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
      html += `<li>${inline(m[1])}</li>`;
    } else if ((m = line.match(/^#{1,4}\s+(.*)$/))) {
      closeList(); html += `<p><strong>${inline(m[1])}</strong></p>`;
    } else if (line.trim() === "") {
      closeList();
    } else {
      closeList(); html += `<p>${inline(line)}</p>`;
    }
  }
  closeList();
  return html;
}

function actionChipsHTML(actions) {
  if (!actions || !actions.length) return "";
  return `<div class="action-chips">${actions.map((a) => `
    <span class="action-chip ${escapeHtml(a.type)}"><svg class="i i-sm" aria-hidden="true"><use href="#i-check"/></svg>${escapeHtml(a.text)}</span>`).join("")}</div>`;
}

function chatBubbleHTML(m, actions) {
  if (m.role === "user") return `<div class="msg msg-user">${escapeHtml(m.content)}</div>`;
  return `<div class="msg msg-assistant md">${renderMarkdown(m.content)}${actionChipsHTML(actions)}</div>`;
}

/* ---- the one place the app talks to the AI (chat box AND mic use it) ---- */
async function askAssistant(text, { voice = false } = {}) {
  const res = await api.post("/chatbot/message", { message: text, voice });
  // The AI changed something (inventory / list / board): refresh whatever page is open.
  if ((res.actions || []).length && (window.location.hash || "#home").slice(1) !== "chat") router();
  return res;
}

/* If the chat page is open, mirror a spoken exchange into it so history stays visible. */
function mirrorIntoChat(userText, reply, actions) {
  const body = document.getElementById("chatBody");
  if (!body) return;
  body.querySelector(".chat-empty")?.remove();
  body.insertAdjacentHTML("beforeend", chatBubbleHTML({ role: "user", content: userText }) + chatBubbleHTML(reply, actions));
  body.scrollTop = body.scrollHeight;
}

async function renderChatPage(main) {
  main.innerHTML = `
    <div class="chat-shell">
      <div class="chat-header">
        <div class="ic">🌿</div>
        <div><h2>ShelfWise AI</h2><p>Ask, or tell me what to add. I can see your kitchen.</p></div>
        <div class="status-dot"></div>
      </div>
      <div class="chat-body" id="chatBody"></div>
      <div class="chat-input-row">
        <button class="mic-inline" onclick="toggleVoice()" aria-label="Speak"><svg class="i" aria-hidden="true"><use href="#i-mic"/></svg></button>
        <input id="chatInput" type="text" placeholder="Ask, or say “add milk to my list”…" onkeydown="if(event.key==='Enter')sendChatMessage()" autocomplete="off">
        <button class="send-btn" onclick="sendChatMessage()" aria-label="Send"><svg class="i" aria-hidden="true"><use href="#i-send"/></svg></button>
      </div>
      <div class="chat-disclaimer">AI suggestions · verify before consuming</div>
    </div>
  `;

  const { messages } = await api.get("/chatbot/history");
  const body = document.getElementById("chatBody");
  if (!messages.length) {
    body.innerHTML = `
      <div class="chat-empty">
        <div class="avatar-big">👩‍🍳</div>
        <h3>What can I help with?</h3>
        <p>I can suggest recipes from your real stock, tell you what's expiring, and <b>add things for you</b>: to your shopping list, inventory or the board.</p>
        <div class="suggestion-chips">
          <button class="suggestion-chip" onclick="askChat('What can I cook tonight?')">What can I cook tonight?</button>
          <button class="suggestion-chip" onclick="askChat(\`What's expiring soon?\`)">What's expiring soon?</button>
          <button class="suggestion-chip" onclick="askChat('Add milk to my shopping list')">Add milk to my list</button>
          <button class="suggestion-chip" onclick="askChat('Post a note on the board: we need olive oil')">Post a note on the board</button>
        </div>
      </div>`;
  } else {
    body.innerHTML = messages.map((m) => chatBubbleHTML(m)).join("");
    body.scrollTop = body.scrollHeight;
  }
}

function askChat(text) {
  document.getElementById("chatInput").value = text;
  sendChatMessage();
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";

  const body = document.getElementById("chatBody");
  body.querySelector(".chat-empty")?.remove();
  body.insertAdjacentHTML("beforeend", chatBubbleHTML({ role: "user", content: text }) +
    `<div class="msg msg-assistant typing" id="typingBubble"><span></span><span></span><span></span></div>`);
  body.scrollTop = body.scrollHeight;

  try {
    const { reply, actions } = await askAssistant(text);
    document.getElementById("typingBubble").outerHTML = chatBubbleHTML(reply, actions);
  } catch (err) {
    document.getElementById("typingBubble").outerHTML = chatBubbleHTML({ role: "assistant", content: err.message });
  }
  body.scrollTop = body.scrollHeight;
}
