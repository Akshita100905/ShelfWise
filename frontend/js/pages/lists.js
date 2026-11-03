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
    <div class="page-header"><h1>Purchase History</h1><p>Everything you've added, most recent first</p></div>
    <div id="historyGroups"></div>
  `;
  const { items } = await api.get("/items"); // current items double as recent purchase context
  // Group by month using purchase_date
  const groups = {};
  items
    .slice()
    .sort((a, b) => (b.purchase_date || "").localeCompare(a.purchase_date || ""))
    .forEach((item) => {
      const d = item.purchase_date ? new Date(item.purchase_date) : new Date();
      const label = d.toLocaleDateString(undefined, { month: "long", year: "numeric" });
      groups[label] = groups[label] || [];
      groups[label].push(item);
    });

  const container = document.getElementById("historyGroups");
  container.innerHTML = Object.entries(groups).map(([label, rows]) => `
    <div class="history-group">
      <h4>${label}</h4>
      ${rows.map(r => `
        <div class="history-row">
          <div class="emoji-badge">${r.icon}</div>
          <div class="info">
            <div class="name">${r.name}</div>
            <div class="sub">${r.quantity} ${r.unit}</div>
          </div>
          <div class="date">${r.purchase_date || ""}</div>
        </div>
      `).join("")}
    </div>
  `).join("") || `<div class="empty-state">No purchases logged yet.</div>`;
}
