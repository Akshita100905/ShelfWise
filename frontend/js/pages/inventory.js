function itemRowHTML(item) {
  return `
    <div class="item-row" data-item-id="${item.id}" style="--risk:${riskColorVar(item.risk_label)}">
      <div class="emoji-badge">${item.icon}</div>
      <div class="info">
        <div class="name">${escapeHtml(item.name)}</div>
        <div class="meta">${item.quantity}${item.unit === "unit" ? "" : " " + item.unit} · ${capitalize(item.storage)}</div>
        <div class="badges">
          <span class="badge ${riskBadgeClass(item.risk_label)}"><span class="badge-dot"></span>${item.risk_label}</span>
          <span class="days-left">${daysLeftLabel(item.days_left)}</span>
        </div>
        ${item.is_estimate ? `<div class="estimate-flag">⚠ Estimate · limited data</div>` : ""}
      </div>
      ${riskRingSVG(item.risk_score, 50)}
      <div class="actions">
        <button class="icon-btn consume-btn" title="Mark used" aria-label="Mark used"><svg class="i" aria-hidden="true"><use href="#i-check"/></svg></button>
        <button class="icon-btn delete-btn" title="Remove" aria-label="Remove"><svg class="i" aria-hidden="true"><use href="#i-trash"/></svg></button>
      </div>
    </div>`;
}

function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

function bindItemRowActions(root) {
  root.querySelectorAll(".consume-btn").forEach((btn) => {
    btn.onclick = async (e) => {
      const row = e.currentTarget.closest(".item-row");
      const id = row.dataset.itemId;
      try {
        await api.post(`/items/${id}/consume`, {});
        toast("Marked as used");
        router();
      } catch (err) { toast(err.message); }
    };
  });
  root.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.onclick = async (e) => {
      const row = e.currentTarget.closest(".item-row");
      const id = row.dataset.itemId;
      try {
        await api.del(`/items/${id}`);
        toast("Item removed");
        router();
      } catch (err) { toast(err.message); }
    };
  });
}

let inventoryFilter = "all";

async function renderInventoryPage(main) {
  main.innerHTML = `
    <div class="page-header-row">
      <div class="page-header"><h1>Inventory</h1><p>Everything currently in your kitchen, sorted by waste risk.</p></div>
      <button class="btn btn-cta" onclick="openAddItemModal()"><svg class="i" aria-hidden="true"><use href="#i-plus"/></svg> Add item</button>
    </div>
    <div class="filter-row" id="invFilters"></div>
    <div id="invList"></div>
  `;

  const filters = [
    ["all", "All"], ["produce", "🥦 Produce"], ["dairy", "🥛 Dairy"],
    ["meat", "🥩 Meat"], ["bakery", "🍞 Bakery"], ["grains", "🍝 Grains"], ["other", "📦 Other"],
  ];
  document.getElementById("invFilters").innerHTML = filters.map(([val, label]) => `
    <button class="chip ${inventoryFilter === val ? "active" : ""}" data-val="${val}">${label}</button>
  `).join("");
  document.querySelectorAll("#invFilters .chip").forEach((chip) => {
    chip.onclick = () => { inventoryFilter = chip.dataset.val; renderInventoryPage(main); };
  });

  const qs = inventoryFilter !== "all" ? `?category=${inventoryFilter}` : "";
  const { items } = await api.get(`/items${qs}`);

  document.getElementById("invList").innerHTML = items.map(itemRowHTML).join("")
    || `<div class="empty-state"><div class="emoji">📦</div><p>No items yet — add your first one.</p></div>`;
  bindItemRowActions(main);
}
