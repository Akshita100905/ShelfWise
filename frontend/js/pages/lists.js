/* ---------- Shopping List ---------- */
async function renderShoppingPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>Shopping List</h1><p>What you still need to pick up</p></div>
    <div class="card" style="padding:16px 18px;">
      <div id="shoppingRows"></div>
      <div class="add-inline-row">
        <input id="newShoppingItem" type="text" placeholder="Add item…" onkeydown="if(event.key==='Enter')addShoppingItem()">
        <button class="btn btn-primary" onclick="addShoppingItem()">Add</button>
      </div>
    </div>
  `;
  await refreshShoppingList();
}

async function refreshShoppingList() {
  const { items } = await api.get("/shopping-list");
  const rows = document.getElementById("shoppingRows");
  rows.innerHTML = items.map(i => `
    <div class="check-row ${i.is_purchased ? "done" : ""}" data-id="${i.id}">
      <input type="checkbox" ${i.is_purchased ? "checked" : ""} class="shop-check">
      <div class="name">${escapeHtml(i.name)}</div>
      <button class="shop-delete" title="Remove">✕</button>
    </div>
  `).join("") || `<div class="empty-state">Your list is empty.</div>`;

  rows.querySelectorAll(".shop-check").forEach((cb) => {
    cb.onchange = async (e) => {
      const id = e.target.closest(".check-row").dataset.id;
      await api.put(`/shopping-list/${id}`, { is_purchased: e.target.checked });
      refreshShoppingList();
    };
  });
  rows.querySelectorAll(".shop-delete").forEach((btn) => {
    btn.onclick = async (e) => {
      const id = e.target.closest(".check-row").dataset.id;
      await api.del(`/shopping-list/${id}`);
      refreshShoppingList();
    };
  });
}

async function addShoppingItem() {
  const input = document.getElementById("newShoppingItem");
  const name = input.value.trim();
  if (!name) return;
  input.value = "";
  try {
    await api.post("/shopping-list", { name });
    refreshShoppingList();
  } catch (err) { toast(err.message); }
}

/* ---------- Purchase History ---------- */
async function renderPurchaseHistoryPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>Purchase History</h1><p>Browse purchases by month</p></div>
    <div class="card" style="padding:16px 18px; margin-bottom:16px;">
      <div class="field" style="margin:0;">
        <label for="purchaseMonth">Select month</label>
        <select id="purchaseMonth" aria-label="Select purchase month"></select>
      </div>
    </div>
    <div id="historyGroups"></div>
  `;

  const selector = document.getElementById("purchaseMonth");
  selector.onchange = () => loadPurchaseHistoryMonth(selector.value);
  await loadPurchaseHistoryMonth("");
}

async function loadPurchaseHistoryMonth(month) {
  const container = document.getElementById("historyGroups");
  if (!container) return;
  container.innerHTML = `<div class="empty-state">Loading purchase history…</div>`;
  try {
    const query = month ? `?month=${encodeURIComponent(month)}` : "";
    const data = await api.get(`/analytics/purchases${query}`);
    const selector = document.getElementById("purchaseMonth");
    if (!selector) return;

    // Rebuild options only when the available month list changes.
    const options = data.months || [];
    const signature = options.join("|");
    if (selector.dataset.months !== signature) {
      selector.innerHTML = options.map(m => {
        const [year, monthNumber] = m.split("-").map(Number);
        const label = new Date(year, monthNumber - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
        return `<option value="${escapeHtml(m)}">${escapeHtml(label)}</option>`;
      }).join("");
      selector.dataset.months = signature;
    }
    selector.value = data.selected_month || "";
    selector.disabled = !options.length;

    const purchases = data.purchases || [];
    container.innerHTML = purchases.map(p => {
      const [year, monthNumber, day] = (p.purchase_date || "").split("-").map(Number);
      const dateLabel = p.purchase_date
        ? new Date(year, monthNumber - 1, day).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })
        : "";
      const icon = ({ produce: "🥬", dairy: "🥛", meat: "🥩", bakery: "🥖", grains: "🌾", other: "📦" })[p.category] || "📦";
      return `
        <div class="history-row">
          <div class="emoji-badge">${icon}</div>
          <div class="info">
            <div class="name">${escapeHtml(p.item_name)}</div>
            <div class="sub">${escapeHtml(p.quantity)} ${escapeHtml(p.unit)}${p.was_wasted ? " · Marked as wasted" : ""}</div>
          </div>
          <div class="date">${escapeHtml(dateLabel)}</div>
        </div>`;
    }).join("") || `<div class="empty-state">${options.length ? "No purchases recorded for this month." : "No purchases logged yet."}</div>`;
  } catch (err) {
    container.innerHTML = `<div class="empty-state">${escapeHtml(err.message || "Could not load purchase history.")}</div>`;
  }
}
