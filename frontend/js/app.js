// App shell: session bootstrap, router, drawer, toast, modal helpers.

const PAGE_RENDERERS = {
  "home": renderHomePage,
  "inventory": renderInventoryPage,
  "chat": renderChatPage,
  "board": renderBoardPage,
  "analytics": renderAnalyticsPage,
  "use-first": renderUseFirstPage,
  "dont-buy": renderDontBuyPage,
  "what-if": renderWhatIfPage,
  "shopping": renderShoppingPage,
  "purchase-history": renderPurchaseHistoryPage,
  "settings": renderSettingsPage,
  "household": renderHouseholdPage,
  "language": renderLanguagePage,
};

let currentUser = null;
let currentHousehold = null;
let currentRole = null;       // my role in the active household
let myHouseholds = [];         // every household I belong to

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2600);
}

function openDrawer() {
  document.getElementById("sidebar").classList.add("open");
  document.getElementById("drawerOverlay").classList.add("open");
}
function closeDrawer() {
  document.getElementById("sidebar").classList.remove("open");
  document.getElementById("drawerOverlay").classList.remove("open");
}

function navigate(page) {
  window.location.hash = page;
  closeDrawer();
}

async function router() {
  const page = (window.location.hash || "#home").slice(1);
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.page === page);
  });
  const main = document.getElementById("main");
  main.innerHTML = `<div class="empty-state">Loading…</div>`;
  const renderer = PAGE_RENDERERS[page] || renderHomePage;
  try {
    await renderer(main);
  } catch (err) {
    main.innerHTML = `<div class="empty-state">
      <div class="emoji">⚠️</div>
      <p>${err.message}</p>
    </div>`;
  }
}

// Wraps content in the styled .modal-card (callers pass bare content).
function showModal(html) {
  document.getElementById("modalRoot").innerHTML =
    `<div class="modal-overlay" id="modalOverlay"><div class="modal-card" role="dialog" aria-modal="true">${html}</div></div>`;
  document.getElementById("modalOverlay").addEventListener("click", (e) => {
    if (e.target.id === "modalOverlay") closeModal();
  });
  const firstInput = document.querySelector("#modalRoot input, #modalRoot textarea");
  if (firstInput) firstInput.focus();
}
function closeModal() {
  document.getElementById("modalRoot").innerHTML = "";
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeModal(); closeDrawer(); }
});

// ---- households: the active one + everything I belong to ----
async function refreshHouseholds() {
  const [cur, list] = await Promise.all([api.get("/households/current"), api.get("/households")]);
  currentHousehold = cur.household;
  currentRole = cur.my_role || null;
  myHouseholds = list.households;
  document.getElementById("householdNameLabel").textContent =
    currentHousehold ? currentHousehold.name : "Create or join a household";
  renderHouseholdMenu();
}

function renderHouseholdMenu() {
  const menu = document.getElementById("hhMenu");
  const initial = (n) => escapeHtml((n || "?").trim().charAt(0).toUpperCase());
  menu.innerHTML = `
    <div class="hh-menu-label">Your households</div>
    ${myHouseholds.map((h) => `
      <button class="hh-option ${h.active ? "active" : ""}" data-id="${h.id}" role="menuitem">
        <span class="hh-dot">${initial(h.name)}</span>
        <span class="hh-name">${escapeHtml(h.name)}<small>${capitalize(h.role)} · ${h.member_count} member${h.member_count === 1 ? "" : "s"}</small></span>
        ${h.active ? `<svg class="i i-sm" aria-hidden="true"><use href="#i-check"/></svg>` : ""}
      </button>`).join("") || `<div class="hh-empty">You're not in a household yet.</div>`}
    <div class="hh-menu-sep"></div>
    <button class="hh-option" onclick="closeHouseholdMenu();navigate('household')" role="menuitem"><span class="hh-dot alt"><svg class="i i-sm" aria-hidden="true"><use href="#i-sliders"/></svg></span><span class="hh-name">Manage &amp; invite</span></button>
    <button class="hh-option" onclick="closeHouseholdMenu();openJoinModal()" role="menuitem"><span class="hh-dot alt"><svg class="i i-sm" aria-hidden="true"><use href="#i-plus"/></svg></span><span class="hh-name">Join another household</span></button>`;
  menu.querySelectorAll(".hh-option[data-id]").forEach((b) => {
    b.onclick = () => switchHousehold(Number(b.dataset.id));
  });
}

function toggleHouseholdMenu(e) {
  e?.stopPropagation();
  const menu = document.getElementById("hhMenu");
  const open = menu.classList.toggle("open");
  document.getElementById("householdSwitchBtn").setAttribute("aria-expanded", open);
}
function closeHouseholdMenu() {
  document.getElementById("hhMenu").classList.remove("open");
  document.getElementById("householdSwitchBtn").setAttribute("aria-expanded", "false");
}
document.addEventListener("click", (e) => {
  if (!e.target.closest(".hh-wrap")) closeHouseholdMenu();
});

async function switchHousehold(id) {
  closeHouseholdMenu();
  if (currentHousehold && currentHousehold.id === id) return;
  try {
    await api.post("/households/switch", { household_id: id });
    await refreshHouseholds();
    closeDrawer();
    toast(`Switched to ${currentHousehold.name}`);
    router();
  } catch (err) { toast(err.message); }
}

async function bootstrap() {
  try {
    const { user } = await api.get("/auth/me");
    if (!user) {
      window.location.href = "auth.html";
      return;
    }
    currentUser = user;
    document.getElementById("userAvatar").textContent = user.initials;
    document.getElementById("userNameLabel").textContent = user.name;
    applyTheme(user.theme || "dark");

    if (!user.household_id) {
      window.location.hash = "household";
    }

    await refreshHouseholds();

    window.addEventListener("hashchange", router);
    router();
  } catch (err) {
    document.getElementById("main").innerHTML = `<div class="empty-state">
      <div class="emoji">🔌</div>
      <p>${err.message}</p>
    </div>`;
  }
}

bootstrap();
