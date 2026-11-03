const ITEM_CATEGORIES = [
  ["produce", "🥦", "Produce"], ["dairy", "🥛", "Dairy"], ["meat", "🥩", "Meat"],
  ["bakery", "🍞", "Bakery"], ["grains", "🍝", "Grains"], ["other", "📦", "Other"],
];
const STORAGE_OPTIONS = [
  ["fridge", "🧊", "Fridge"], ["freezer", "❄️", "Freezer"],
  ["pantry", "🗄️", "Pantry"], ["counter", "🍽️", "Counter"],
];

let wizardState = {};

function openAddItemModal() {
  wizardState = { step: 1, category: "produce", storage: "fridge", quantity: 1, unit: "unit", name: "", expires_in_days: 7 };
  renderWizardStep();
}

function renderWizardStep() {
  if (wizardState.step === 1) {
    showModal(`
      <div class="modal-progress"><div class="fill" style="width:50%"></div></div>
      <h2>What is it?</h2>
      <div class="field">
        <label>Item name</label>
        <input id="wName" type="text" placeholder="e.g. Whole Milk, Cherry Tomatoes" value="${escapeHtml(wizardState.name)}">
      </div>
      <label style="font-size:13px;font-weight:700;color:var(--text-secondary);">Category</label>
      <div class="wizard-grid" id="wCatGrid">
        ${ITEM_CATEGORIES.map(([val, ic, lbl]) => `
          <button type="button" class="wizard-cat-btn ${wizardState.category === val ? "active" : ""}" data-val="${val}">
            <span class="ic">${ic}</span>${lbl}
          </button>`).join("")}
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary" id="wNextBtn">Next →</button>
      </div>
    `);
    document.querySelectorAll("#wCatGrid .wizard-cat-btn").forEach((btn) => {
      btn.onclick = () => {
        // keep what's been typed — re-rendering the step would otherwise clear it
        wizardState.name = document.getElementById("wName").value;
        wizardState.category = btn.dataset.val;
        renderWizardStep();
      };
    });
    document.getElementById("wNextBtn").onclick = () => {
      wizardState.name = document.getElementById("wName").value.trim();
      if (!wizardState.name) { toast("Give the item a name first"); return; }
      wizardState.step = 2;
      renderWizardStep();
    };
  } else {
    const todayStr = new Date().toISOString().slice(0, 10);
    showModal(`
      <div class="modal-progress"><div class="fill" style="width:100%"></div></div>
      <h2>When does it expire?</h2>
      <div class="qty-row">
        <div class="field">
          <label>Quantity</label>
          <input id="wQty" type="number" min="0" step="0.1" value="${wizardState.quantity}">
        </div>
        <div class="field">
          <label>Unit</label>
          <select id="wUnit">
            ${["unit", "g", "kg", "ml", "litre", "pack", "bag", "loaf", "pots", "tub", "pieces"].map(u =>
              `<option value="${u}" ${wizardState.unit === u ? "selected" : ""}>${u}</option>`).join("")}
          </select>
        </div>
      </div>
      <label style="font-size:13px;font-weight:700;color:var(--text-secondary);">Where to store it</label>
      <div class="storage-grid" id="wStorageGrid" style="margin:10px 0 16px;">
        ${STORAGE_OPTIONS.map(([val, ic, lbl]) => `
          <button type="button" class="storage-btn ${wizardState.storage === val ? "active" : ""}" data-val="${val}">${ic} ${lbl}</button>
        `).join("")}
      </div>
      <div class="qty-row">
        <div class="field">
          <label>Purchase date</label>
          <input id="wPurchaseDate" type="date" value="${todayStr}">
        </div>
        <div class="field">
          <label>Expiry date</label>
          <input id="wExpiryDate" type="date">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" onclick="wizardState.step=1;renderWizardStep();">← Back</button>
        <button class="btn btn-primary" id="wSaveBtn">Save Item</button>
      </div>
    `);
    document.querySelectorAll("#wStorageGrid .storage-btn").forEach((btn) => {
      btn.onclick = () => {
        wizardState.storage = btn.dataset.val;
        document.querySelectorAll("#wStorageGrid .storage-btn").forEach(b => b.classList.toggle("active", b === btn));
      };
    });
    document.getElementById("wSaveBtn").onclick = saveWizardItem;
  }
}

async function saveWizardItem() {
  wizardState.quantity = parseFloat(document.getElementById("wQty").value) || 1;
  wizardState.unit = document.getElementById("wUnit").value;
  wizardState.purchase_date = document.getElementById("wPurchaseDate").value || null;
  wizardState.expiry_date = document.getElementById("wExpiryDate").value || null;

  const btn = document.getElementById("wSaveBtn");
  btn.disabled = true;
  try {
    await api.post("/items", {
      name: wizardState.name,
      category: wizardState.category,
      quantity: wizardState.quantity,
      unit: wizardState.unit,
      storage: wizardState.storage,
      purchase_date: wizardState.purchase_date,
      expiry_date: wizardState.expiry_date,
    });
    closeModal();
    toast(`${wizardState.name} added to your inventory`);
    router();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}
