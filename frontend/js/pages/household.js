/* =========================================================
   Household page: members, invites, switching, joining, leaving
   ========================================================= */

const svgI = (n, cls = "i i-sm") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${n}"/></svg>`;

async function copyText(text, okMsg = "Copied") {
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    // fallback for non-secure contexts
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    ta.remove();
  }
  toast(okMsg);
}

// The link is built from wherever THIS page is actually served (auth.html sits next to
// app.html), so it is correct whatever folder or host Live Server / your hosting uses.
function inviteUrl(token) {
  return new URL(`auth.html?invite=${encodeURIComponent(token)}`, window.location.href).href;
}
const authPageUrl = () => new URL("auth.html", window.location.href).href;

function fmtDate(iso) {
  try { return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" }); } catch (e) { return ""; }
}

/* ---------- join (works from the sidebar menu and this page) ---------- */
function openJoinModal(prefill = "") {
  showModal(`
    <h2>Join a household</h2>
    <p class="modal-note">Paste an invite link, or type the household code someone shared with you.</p>
    <div class="field">
      <label for="joinValue">Invite link or code</label>
      <input id="joinValue" type="text" placeholder="e.g. CHENFR1 or https://…/auth.html?invite=…" value="${escapeHtml(prefill)}" autocomplete="off">
    </div>
    <div id="joinPreview"></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" id="joinActionBtn">Find household</button>
    </div>`);

  const input = document.getElementById("joinValue");
  const btn = document.getElementById("joinActionBtn");
  const box = document.getElementById("joinPreview");
  let found = null;

  const reset = () => { found = null; box.innerHTML = ""; btn.textContent = "Find household"; };
  input.oninput = reset;
  input.onkeydown = (e) => { if (e.key === "Enter") btn.click(); };

  btn.onclick = async () => {
    const value = input.value.trim();
    if (!value) return toast("Enter a code or paste an invite link");
    btn.disabled = true;
    try {
      if (!found) {
        // Step 1: show exactly which household this points to BEFORE joining.
        const p = await api.get(`/households/preview?value=${encodeURIComponent(value)}`);
        found = p;
        box.innerHTML = `
          <div class="preview-card">
            <div class="hh-dot big">${escapeHtml(p.household.name.charAt(0).toUpperCase())}</div>
            <div>
              <div class="pv-name">${escapeHtml(p.household.name)}</div>
              <div class="pv-sub">${p.household.member_count} member${p.household.member_count === 1 ? "" : "s"}${p.invited_by ? ` · invited by ${escapeHtml(p.invited_by)}` : ""}</div>
              ${p.already_member ? `<div class="pv-sub ok">You're already in this household.</div>` : ""}
            </div>
          </div>`;
        btn.textContent = p.already_member ? `Switch to ${p.household.name}` : `Join ${p.household.name}`;
      } else {
        // Step 2: confirmed.
        const res = await api.post("/households/join", { invite_code: value });
        closeModal();
        await refreshHouseholds();
        toast(res.already_member ? `Switched to ${res.household.name}` : `Joined ${res.household.name}`);
        window.location.hash === "#home" ? router() : navigate("home");
      }
    } catch (err) {
      found = null;
      box.innerHTML = `<div class="auth-error" role="alert">${escapeHtml(err.message)}</div>`;
      btn.textContent = "Find household";
    } finally { btn.disabled = false; }
  };
  input.focus();
  if (prefill) btn.click();
}

/* ---------- create ---------- */
async function createHousehold(name) {
  if (!name) return toast("Give your household a name");
  await api.post("/households/create", { name });
  await refreshHouseholds();
  toast(`Created ${name}`);
  navigate("home");
}

/* ---------- leave ---------- */
function confirmLeave() {
  showModal(`
    <h2>Leave ${escapeHtml(currentHousehold.name)}?</h2>
    <p class="modal-note">You'll lose access to its items, board and shopping list. Your other households aren't affected.
    You can rejoin later with a new invite.</p>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Stay</button>
      <button class="btn btn-danger" id="leaveBtn">Leave household</button>
    </div>`);
  document.getElementById("leaveBtn").onclick = async () => {
    try {
      await api.post("/households/leave", { household_id: currentHousehold.id });
      closeModal();
      await refreshHouseholds();
      toast("You left the household");
      const target = currentHousehold ? "home" : "household";
      if (window.location.hash === "#" + target) router(); else navigate(target);
    } catch (err) { closeModal(); toast(err.message); }
  };
}

/* ---------- page ---------- */
async function renderHouseholdPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>Household</h1><p>Your kitchens, who's in them, and how to invite people.</p></div>
    <div id="hhBody"></div>`;
  await refreshHouseholds();
  const body = document.getElementById("hhBody");
  const others = myHouseholds.filter((h) => !currentHousehold || h.id !== currentHousehold.id);
  const isOwner = currentRole === "owner";

  let html = "";

  if (!currentHousehold) {
    html += `
      <div class="card settings-card">
        <h3>Create your household</h3>
        <p class="card-note">A household is one shared kitchen: everyone in it sees the same items, board and shopping list.</p>
        <div class="invite-row">
          <input id="newHhName" type="text" placeholder="The Chen-Ferreiras" autocomplete="off">
          <button class="btn btn-primary" id="createHhBtn">Create</button>
        </div>
      </div>
      <div class="card settings-card">
        <h3>Or join one</h3>
        <p class="card-note">Got an invite link or a household code? Paste it here.</p>
        <button class="btn btn-outline" onclick="openJoinModal()">${svgI("plus")} Join with a code or link</button>
      </div>`;
  } else {
    const { members, stats } = await api.get("/households/current");
    const { invites, email_configured } = await api.get("/households/invites");

    html += `
      <div class="card settings-card">
        <div class="hh-title-row">
          <div><h3 class="hh-title">${escapeHtml(currentHousehold.name)}</h3>
          <div class="card-note">${members.length} member${members.length === 1 ? "" : "s"} · ${stats.total_items} item${stats.total_items === 1 ? "" : "s"} tracked</div></div>
          <span class="role-tag ${currentRole}">${capitalize(currentRole)}</span>
        </div>
        <div id="memberList">
        ${members.map((m) => `
          <div class="member-row" data-uid="${m.id}">
            <div class="avatar">${escapeHtml(m.initials)}</div>
            <div class="info"><div class="name">${escapeHtml(m.name)}${m.id === currentUser.id ? ` <span class="you">(you)</span>` : ""}</div>
              <div class="role">${escapeHtml(m.email)}</div></div>
            <span class="role-tag ${m.role}">${capitalize(m.role)}</span>
            ${isOwner && m.id !== currentUser.id ? `
              <div class="member-actions">
                <button class="btn btn-ghost btn-sm" data-act="role" data-role="${m.role === "owner" ? "member" : "owner"}">${m.role === "owner" ? "Make member" : "Make owner"}</button>
                <button class="btn btn-ghost btn-sm danger-text" data-act="remove">Remove</button>
              </div>` : ""}
          </div>`).join("")}
        </div>
      </div>

      <div class="card settings-card" id="inviteCard">
        <h3>Invite someone</h3>
        <p class="card-note">Each invite is a personal, single-use link that expires in 7 days. They'll join <b>${escapeHtml(currentHousehold.name)}</b> and keep any households they're already in.</p>
        <div class="invite-row">
          <input id="inviteEmail" type="email" placeholder="Their email address" autocomplete="off">
          <button class="btn btn-primary" id="sendInviteBtn">${email_configured ? "Email invite" : "Create invite"}</button>
        </div>
        <button class="link-btn" id="makeLinkBtn">or create a link without an email</button>
        <div id="inviteResult"></div>

        <div class="code-row">
          <div><div class="lbl">Household code</div>
          <div class="sub">Reusable. Anyone who has it can join, so reset it if it leaks.</div></div>
          <div class="code-actions">
            <code class="code-chip" id="hhCode">${escapeHtml(currentHousehold.invite_code)}</code>
            <button class="icon-btn-lg" id="copyCodeBtn" title="Copy code" aria-label="Copy code">${svgI("copy")}</button>
            ${isOwner ? `<button class="btn btn-ghost btn-sm" id="resetCodeBtn">Reset</button>` : ""}
          </div>
        </div>

        ${invites.length ? `
        <div class="pending">
          <div class="lbl">Pending invites</div>
          ${invites.map((i) => `
            <div class="pending-row" data-id="${i.id}">
              <div class="info"><div class="name">${i.email ? escapeHtml(i.email) : "Link (no email)"}</div>
                <div class="sub">from ${escapeHtml(i.invited_by || "someone")} · expires ${fmtDate(i.expires_at)}</div></div>
              <button class="btn btn-ghost btn-sm" data-act="copy" data-link="${escapeHtml(inviteUrl(i.token))}">Copy link</button>
              <button class="btn btn-ghost btn-sm danger-text" data-act="cancel">Cancel</button>
            </div>`).join("")}
        </div>` : ""}
      </div>`;
  }

  // every household I'm in
  html += `
    <div class="card settings-card">
      <h3>Your households</h3>
      ${myHouseholds.map((h) => `
        <div class="hh-list-row">
          <div class="hh-dot">${escapeHtml(h.name.charAt(0).toUpperCase())}</div>
          <div class="info"><div class="name">${escapeHtml(h.name)}</div>
            <div class="sub">${capitalize(h.role)} · ${h.member_count} member${h.member_count === 1 ? "" : "s"}</div></div>
          ${h.active ? `<span class="role-tag active-tag">Active</span>` : `<button class="btn btn-outline btn-sm" data-switch="${h.id}">Switch</button>`}
        </div>`).join("") || `<div class="card-note">None yet.</div>`}
      ${currentHousehold ? `
      <div class="hh-add">
        <div class="invite-row">
          <input id="newHhName" type="text" placeholder="Name a new household (e.g. Parents' house)" autocomplete="off">
          <button class="btn btn-outline" id="createHhBtn">Create</button>
        </div>
        <button class="link-btn" onclick="openJoinModal()">or join another with a code or link</button>
      </div>` : ""}
    </div>
    ${currentHousehold ? `<button class="btn btn-outline btn-block danger-outline" onclick="confirmLeave()">Leave ${escapeHtml(currentHousehold.name)}</button>` : ""}`;

  body.innerHTML = html;

  /* ----- wiring ----- */
  const createBtn = document.getElementById("createHhBtn");
  if (createBtn) createBtn.onclick = async () => {
    try { await createHousehold(document.getElementById("newHhName").value.trim()); } catch (e) { toast(e.message); }
  };
  body.querySelectorAll("[data-switch]").forEach((b) => b.onclick = () => switchHousehold(Number(b.dataset.switch)));
  if (!currentHousehold) return;

  // member actions (owners)
  body.querySelectorAll("#memberList [data-act]").forEach((b) => {
    b.onclick = async () => {
      const uid = b.closest(".member-row").dataset.uid;
      try {
        if (b.dataset.act === "role") await api.post(`/households/members/${uid}/role`, { role: b.dataset.role });
        else {
          if (!confirm("Remove this person from the household?")) return;
          await api.del(`/households/members/${uid}`);
        }
        renderHouseholdPage(main);
      } catch (err) { toast(err.message); }
    };
  });

  // household code
  document.getElementById("copyCodeBtn").onclick = () => copyText(currentHousehold.invite_code, "Code copied");
  const reset = document.getElementById("resetCodeBtn");
  if (reset) reset.onclick = async () => {
    if (!confirm("Reset the household code? The old code will stop working.")) return;
    try { await api.post("/households/regenerate-code", {}); renderHouseholdPage(main); toast("Code reset"); }
    catch (err) { toast(err.message); }
  };

  // pending invites
  body.querySelectorAll(".pending-row [data-act]").forEach((b) => {
    b.onclick = async () => {
      if (b.dataset.act === "copy") return copyText(b.dataset.link, "Link copied");
      try { await api.del(`/households/invites/${b.closest(".pending-row").dataset.id}`); renderHouseholdPage(main); toast("Invite cancelled"); }
      catch (err) { toast(err.message); }
    };
  });

  // create invite
  const makeInvite = async (email) => {
    try {
      const res = await api.post("/households/invite", { email, link_base: authPageUrl() });
      res.link = inviteUrl(res.invite.token);
      showInviteResult(res, email);
      if (email) document.getElementById("inviteEmail").value = "";
    } catch (err) { toast(err.message); }
  };
  document.getElementById("sendInviteBtn").onclick = () => {
    const email = document.getElementById("inviteEmail").value.trim();
    if (!email) return toast("Enter an email, or use 'create a link without an email'");
    makeInvite(email);
  };
  document.getElementById("makeLinkBtn").onclick = () => makeInvite("");
  document.getElementById("inviteEmail").onkeydown = (e) => { if (e.key === "Enter") document.getElementById("sendInviteBtn").click(); };
}

/* Shows the freshly created link with every way to actually deliver it. */
function showInviteResult(res, email) {
  const text = `Join my "${currentHousehold.name}" kitchen on ShelfWise: ${res.link}`;
  const box = document.getElementById("inviteResult");
  const status = res.email_sent
    ? `<div class="invite-status ok">${svgI("check")} Emailed to ${escapeHtml(email)}. You can also share the link yourself:</div>`
    : email
      ? `<div class="invite-status warn">${escapeHtml(res.email_error || "Email wasn't sent")}. Send them this link instead:</div>`
      : `<div class="invite-status">Share this link with them:</div>`;
  box.innerHTML = `
    <div class="invite-result">
      ${status}
      <div class="link-box">
        <input id="inviteLink" type="text" readonly value="${escapeHtml(res.link)}" onclick="this.select()">
        <button class="btn btn-primary btn-sm" id="copyLinkBtn">${svgI("copy")} Copy</button>
      </div>
      <div class="share-row">
        ${navigator.share ? `<button class="btn btn-outline btn-sm" id="nativeShareBtn">Share…</button>` : ""}
        <a class="btn btn-outline btn-sm" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent(text)}">WhatsApp</a>
        <a class="btn btn-outline btn-sm" href="mailto:${encodeURIComponent(email || "")}?subject=${encodeURIComponent(`Join ${currentHousehold.name} on ShelfWise`)}&body=${encodeURIComponent(text)}">Email app</a>
      </div>
    </div>`;
  document.getElementById("copyLinkBtn").onclick = () => copyText(res.link, "Link copied");
  const ns = document.getElementById("nativeShareBtn");
  if (ns) ns.onclick = () => navigator.share({ title: "ShelfWise invite", text, url: res.link }).catch(() => {});
  if (!email || !res.email_sent) document.getElementById("inviteLink").select();
}
