const BOARD_COLORS = ["yellow", "orange", "green", "pink", "blue"];

async function renderBoardPage(main) {
  main.innerHTML = `
    <div class="board-canvas">
      <div class="board-header">
        <div class="ic">📌</div>
        <div><h2>Grocery Board</h2><p id="boardCount">0 items needed</p></div>
        <div class="avatars" id="boardAvatars"></div>
      </div>
      <div class="board-notes" id="boardNotes"></div>
      <div class="board-fab-row">
        <button class="board-add-fab" onclick="openAddNoteModal()" title="Add note">+</button>
      </div>
    </div>
  `;

  const { members } = await api.get("/households/current").catch(() => ({ members: [] }));
  document.getElementById("boardAvatars").innerHTML = (members || []).slice(0, 4)
    .map(m => `<div class="avatar" title="${m.name}">${m.initials}</div>`).join("");

  const { notes } = await api.get("/board");
  document.getElementById("boardCount").textContent = `${notes.length} item${notes.length === 1 ? "" : "s"} needed`;
  document.getElementById("boardNotes").innerHTML = notes.map(noteHTML).join("")
    || `<p style="color:rgba(255,255,255,.8);">Nothing on the board — add what you need to buy.</p>`;

  document.querySelectorAll(".sticky-note .buy-btn").forEach((btn) => {
    btn.onclick = async (e) => {
      const id = e.target.closest(".sticky-note").dataset.id;
      await api.put(`/board/${id}/bought`, {});
      toast("Nice — marked as bought");
      renderBoardPage(main);
    };
  });
}

function noteHTML(n) {
  const tilt = (Math.random() * 6 - 3).toFixed(1);
  const ago = timeAgo(n.created_at);
  return `
    <div class="sticky-note ${n.color}" style="--tilt:${tilt}deg" data-id="${n.id}">
      <div class="dot"></div>
      <div class="text">${escapeHtml(n.text)}</div>
      <div class="meta"><span class="avatar" style="width:16px;height:16px;font-size:8px;">${n.posted_by_initials}</span>${ago}</div>
      <button class="buy-btn">Bought ✅</button>
    </div>`;
}

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso + "Z").getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  const days = Math.round(hrs / 24);
  return days === 1 ? "Yesterday" : `${days} days ago`;
}

function openAddNoteModal() {
  showModal(`
    <h2>Add to Grocery Board</h2>
    <div class="field">
      <label>What do you need?</label>
      <input id="noteText" type="text" placeholder="e.g. Oat milk">
    </div>
    <label style="font-size:13px;font-weight:700;color:var(--text-secondary);">Note color</label>
    <div style="display:flex;gap:10px;margin:10px 0 20px;">
      ${BOARD_COLORS.map((c, i) => `
        <button type="button" class="sticky-note ${c}" data-color="${c}"
          style="width:34px;height:34px;min-height:0;padding:0;border-radius:8px;${i === 0 ? "outline:2px solid var(--brand-green);" : ""}"></button>
      `).join("")}
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" id="saveNoteBtn">Post to board</button>
    </div>
  `);
  let chosenColor = BOARD_COLORS[0];
  document.querySelectorAll("#modalOverlay [data-color]").forEach((btn) => {
    btn.onclick = () => {
      chosenColor = btn.dataset.color;
      document.querySelectorAll("#modalOverlay [data-color]").forEach(b => b.style.outline = "none");
      btn.style.outline = "2px solid var(--brand-green)";
    };
  });
  document.getElementById("saveNoteBtn").onclick = async () => {
    const text = document.getElementById("noteText").value.trim();
    if (!text) { toast("Add a short description first"); return; }
    try {
      await api.post("/board", { text, color: chosenColor });
      closeModal();
      router();
    } catch (err) { toast(err.message); }
  };
}
