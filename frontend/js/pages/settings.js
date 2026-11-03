/* ---------- Settings ---------- */
async function renderSettingsPage(main) {
  const theme = localStorage.getItem("shelfwise_theme") || "dark";
  main.innerHTML = `
    <div class="page-header"><h1>Settings</h1></div>

    <div class="card settings-card">
      <h3>Appearance</h3>
      <div class="theme-row" id="themeRow">
        <div class="theme-opt ${theme === "light" ? "active" : ""}" data-val="light"><span class="ic">☀️</span><span class="lbl">Light</span></div>
        <div class="theme-opt ${theme === "dark" ? "active" : ""}" data-val="dark"><span class="ic">🌙</span><span class="lbl">Dark</span></div>
        <div class="theme-opt ${theme === "system" ? "active" : ""}" data-val="system"><span class="ic">💻</span><span class="lbl">System</span></div>
      </div>
    </div>

    <div class="card settings-card">
      <h3>Language</h3>
      <div class="toggle-row" style="cursor:pointer" onclick="navigate('language')">
        <div><div class="lbl">App language</div><div class="sub" id="currentLangLabel">English</div></div>
        <span>›</span>
      </div>
    </div>

    <div class="card settings-card">
      <h3>Notifications</h3>
      <div class="toggle-row">
        <div><div class="lbl">Expiry alerts</div><div class="sub">Notify me when items are about to expire</div></div>
        <label class="switch"><input type="checkbox" id="notifyExpiry"><span class="track"><span class="thumb"></span></span></label>
      </div>
      <div class="toggle-row">
        <div><div class="lbl">Board alerts</div><div class="sub">Notify me when someone posts to the board</div></div>
        <label class="switch"><input type="checkbox" id="notifyBoard"><span class="track"><span class="thumb"></span></span></label>
      </div>
      <div class="toggle-row">
        <div><div class="lbl">AI tips</div><div class="sub">Occasional suggestions based on your inventory</div></div>
        <label class="switch"><input type="checkbox" id="notifyAiTips"><span class="track"><span class="thumb"></span></span></label>
      </div>
    </div>

    <div class="card settings-card">
      <h3>Account</h3>
      <div class="member-row">
        <div class="avatar">${currentUser.initials}</div>
        <div class="info"><div class="name">${currentUser.name}</div><div class="role">${currentUser.email}</div></div>
      </div>
      <div class="toggle-row" style="cursor:pointer" onclick="navigate('household')">
        <div><div class="lbl">Linked household</div><div class="sub">${currentHousehold ? currentHousehold.name : "None yet"}</div></div>
        <span>›</span>
      </div>
      <div class="toggle-row" style="cursor:pointer" onclick="openChangePasswordModal()">
        <div><div class="lbl">Change password</div></div>
        <span>›</span>
      </div>
    </div>

    <button class="btn btn-outline btn-block" onclick="logout()">Sign out</button>
  `;

  document.getElementById("notifyExpiry").checked = currentUser.notify_expiry;
  document.getElementById("notifyBoard").checked = currentUser.notify_board;
  document.getElementById("notifyAiTips").checked = currentUser.notify_ai_tips;

  document.querySelectorAll("#themeRow .theme-opt").forEach((el) => {
    el.onclick = async () => {
      const val = el.dataset.val;
      applyTheme(val);
      document.querySelectorAll("#themeRow .theme-opt").forEach(o => o.classList.toggle("active", o === el));
      try { await api.put("/settings/preferences", { theme: val }); currentUser.theme = val; } catch (e) {}
    };
  });

  ["notifyExpiry", "notifyBoard", "notifyAiTips"].forEach((id) => {
    document.getElementById(id).onchange = async (e) => {
      const key = id === "notifyExpiry" ? "notify_expiry" : id === "notifyBoard" ? "notify_board" : "notify_ai_tips";
      try {
        await api.put("/settings/preferences", { [key]: e.target.checked });
        currentUser[key] = e.target.checked;
      } catch (err) { toast(err.message); }
    };
  });
}

function openChangePasswordModal() {
  showModal(`
    <h2>Change password</h2>
    <div class="field"><label>Current password</label><input id="cpCurrent" type="password"></div>
    <div class="field"><label>New password</label><input id="cpNew" type="password" minlength="6"></div>
    <div class="modal-footer">
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
      <button class="btn btn-primary" id="cpSaveBtn">Save</button>
    </div>
  `);
  document.getElementById("cpSaveBtn").onclick = async () => {
    try {
      await api.put("/settings/password", {
        current_password: document.getElementById("cpCurrent").value,
        new_password: document.getElementById("cpNew").value,
      });
      closeModal();
      toast("Password updated");
    } catch (err) { toast(err.message); }
  };
}

async function logout() {
  await api.post("/auth/logout", {});
  window.location.href = "auth.html";
}

/* ---------- Language ---------- */
const LANGUAGES = [
  ["en", "English", "English"], ["es", "Español", "Spanish"], ["fr", "Français", "French"],
  ["de", "Deutsch", "German"], ["pt", "Português", "Portuguese"], ["it", "Italiano", "Italian"],
  ["hi", "हिन्दी", "Hindi"], ["ja", "日本語", "Japanese"], ["ko", "한국어", "Korean"],
  ["zh", "中文", "Chinese"], ["ar", "العربية", "Arabic"], ["nl", "Nederlands", "Dutch"],
];

async function renderLanguagePage(main) {
  main.innerHTML = `
    <div class="page-header-row">
      <div class="page-header"><h1>Language</h1></div>
      <button class="btn btn-ghost" onclick="navigate('settings')">← Back</button>
    </div>
    <div class="field language-search"><input id="langSearch" type="text" placeholder="Search languages"></div>
    <div class="card" style="padding:8px 12px;"><div class="language-list" id="langList"></div></div>
  `;
  const current = currentUser.language || "en";
  const renderList = (filter = "") => {
    const rows = LANGUAGES.filter(([code, native, eng]) =>
      native.toLowerCase().includes(filter.toLowerCase()) || eng.toLowerCase().includes(filter.toLowerCase()));
    document.getElementById("langList").innerHTML = rows.map(([code, native, eng]) => `
      <div class="language-row" data-code="${code}">
        <div><div class="native">${native}</div><div class="english">${eng}</div></div>
        ${code === current ? `<span class="check">✓</span>` : ""}
      </div>`).join("");
    document.querySelectorAll(".language-row").forEach((row) => {
      row.onclick = async () => {
        const code = row.dataset.code;
        try {
          await api.put("/settings/preferences", { language: code });
          currentUser.language = code;
          navigate("settings");
        } catch (err) { toast(err.message); }
      };
    });
  };
  renderList();
  document.getElementById("langSearch").oninput = (e) => renderList(e.target.value);
}
