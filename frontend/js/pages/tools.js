/* ---------- Use First ---------- */
async function renderUseFirstPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>Use First</h1><p>Items closest to expiring — work through these first.</p></div>
    <div id="useFirstList"></div>
  `;
  const { use_first } = await api.get("/insights/use-first");
  document.getElementById("useFirstList").innerHTML = use_first.map(itemRowHTML).join("")
    || `<div class="empty-state">Nothing urgent right now 🎉</div>`;
  bindItemRowActions(main);
}

/* ---------- Don't Buy Yet ---------- */
const CATEGORY_CHIPS = [["all", "All"], ["produce", "🥬"], ["dairy", "🥛"], ["meat", "🥩"], ["bakery", "🥖"], ["grains", "🌾"]];
let dontBuyCategory = "all";

async function renderDontBuyPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>Don't Buy Yet</h1><p>Check if you already have enough at home</p></div>
    <div class="search-row">
      <input id="dbSearch" type="text" placeholder="e.g. Eggs" onkeydown="if(event.key==='Enter')checkSupply()">
    </div>
    <button class="btn btn-primary btn-block" onclick="checkSupply()">Check my supply</button>
    <div id="dbResult"></div>

    <div class="section-title" style="margin-top:32px;">Already well-stocked</div>
    <div class="filter-row" id="dbChips"></div>
    <div id="dbList"></div>
  `;
  document.getElementById("dbChips").innerHTML = CATEGORY_CHIPS.map(([val, label]) => `
    <button class="chip ${dontBuyCategory === val ? "active" : ""}" data-val="${val}">${label}</button>
  `).join("");
  document.querySelectorAll("#dbChips .chip").forEach((chip) => {
    chip.onclick = () => { dontBuyCategory = chip.dataset.val; renderDontBuyPage(main); };
  });

  const { items } = await api.get(`/insights/dont-buy/list${dontBuyCategory !== "all" ? "?category=" + dontBuyCategory : ""}`);
  document.getElementById("dbList").innerHTML = items.map(itemRowHTML).join("")
    || `<div class="empty-state">No well-stocked items to flag yet.</div>`;
  bindItemRowActions(main);
}

async function checkSupply() {
  const q = document.getElementById("dbSearch").value.trim();
  if (!q) return;
  const resultEl = document.getElementById("dbResult");
  resultEl.innerHTML = `<div class="empty-state">Checking…</div>`;
  const { result } = await api.get(`/insights/dont-buy?q=${encodeURIComponent(q)}`);
  if (!result || !result.found) {
    resultEl.innerHTML = `<div class="card result-card"><div class="info"><div class="name">${result ? result.message : "No match found"}</div></div></div>`;
    return;
  }
  const item = result.item;
  resultEl.innerHTML = `
    <div class="card result-card">
      <div class="emoji-badge">${item.icon}</div>
      <div class="info">
        <div class="name">${escapeHtml(item.name)}</div>
        <div class="sub">${item.quantity} ${item.unit} in ${item.storage}</div>
        <div class="stat-cols">
          <div><div>Estimated depletion</div><div>${result.estimated_depletion}</div></div>
          <div><div>Recommendation</div><div style="color:var(--brand-orange)">${result.recommendation}</div></div>
        </div>
        <div class="note">${result.note}</div>
      </div>
      <span class="badge badge-mid">⏸ Wait</span>
    </div>`;
}

/* ---------- What-If Simulator ---------- */
let whatIfCategory = "produce";
const WHAT_IF_CATEGORIES = [
  ["produce", "🥬", "Produce"], ["dairy", "🥛", "Dairy"],
  ["meat", "🥩", "Meat"], ["bakery", "🥖", "Bakery"],
  ["grains", "🌾", "Grains"], ["other", "📦", "Other"],
];
const WHAT_IF_PRODUCTS = {
  produce: ["Tomato", "Apple", "Banana", "Spinach", "Potato", "Onion", "Cucumber", "Carrot", "Lettuce"],
  dairy: ["Milk", "Curd", "Paneer", "Butter", "Yogurt", "Cheese"],
  meat: ["Chicken", "Fish", "Mutton"],
  bakery: ["Bread", "Cake", "Buns"],
  grains: ["Rice", "Flour", "Atta", "Dal", "Pulses"],
  other: ["Eggs", "Juice", "Sauce", "Snacks"],
};

async function renderWhatIfPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>What-If Simulator</h1><p>Try a hypothetical purchase and see how much of it your household may use before expiry.</p></div>
    <div class="card wi-form-card">
      <div class="field">
        <label for="wiName">What are you buying?</label>
        <input id="wiName" list="wiProductSuggestions" type="text" maxlength="150" placeholder="e.g. Tomatoes">
        <datalist id="wiProductSuggestions"></datalist>
      </div>
      <div class="field">
        <label>Category</label>
        <div class="category-icon-row" id="wiCats">
          ${WHAT_IF_CATEGORIES.map(([val, ic, label]) => `<button type="button" title="${label}" aria-label="${label}" class="category-icon-btn ${whatIfCategory === val ? "active" : ""}" data-val="${val}">${ic}</button>`).join("")}
        </div>
      </div>
      <div class="wi-fields-grid">
        <div class="field"><label for="wiQuantity">Quantity</label><input id="wiQuantity" type="number" min="0.1" max="100000" step="0.1" value="1"></div>
        <div class="field"><label for="wiUnit">Unit</label><select id="wiUnit">${["unit", "g", "kg", "ml", "litre", "pack", "bag", "loaf", "pots", "tub", "pieces"].map(u => `<option value="${u}">${u}</option>`).join("")}</select></div>
      </div>
      <div class="field">
        <label for="wiStorage">Where will you store it?</label>
        <select id="wiStorage">
          <option value="fridge">🧊 Refrigerator</option><option value="freezer">❄️ Freezer</option>
          <option value="pantry">🗄️ Pantry</option><option value="counter">🍽️ Countertop</option>
        </select>
      </div>
      <div class="card slider-card wi-expiry-card">
        <label for="wiSlider">Expected expiry</label>
        <div class="slider-row"><input type="range" id="wiSlider" min="0" max="60" value="7"><span class="days-val" id="wiDaysVal">7 days</span></div>
        <p class="wi-help">Enter the number of days until the product expires.</p>
      </div>
      <button class="btn btn-cta btn-block" id="simulateBtn">Simulate purchase</button>
    </div>
    <div id="wiResult" aria-live="polite" style="margin-top:18px;"></div>
  `;

  const updateSuggestions = () => {
    document.getElementById("wiProductSuggestions").innerHTML = (WHAT_IF_PRODUCTS[whatIfCategory] || []).map(n => `<option value="${n.replace(/&/g, "&amp;").replace(/\"/g, "&quot;")}"></option>`).join("");
  };
  updateSuggestions();
  document.querySelectorAll("#wiCats .category-icon-btn").forEach(btn => {
    btn.onclick = () => {
      whatIfCategory = btn.dataset.val;
      document.querySelectorAll("#wiCats .category-icon-btn").forEach(b => b.classList.toggle("active", b === btn));
      updateSuggestions();
    };
  });
  const slider = document.getElementById("wiSlider");
  slider.oninput = () => { document.getElementById("wiDaysVal").textContent = `${slider.value} ${Number(slider.value) === 1 ? "day" : "days"}`; };
  document.getElementById("simulateBtn").onclick = runWhatIf;
}

async function runWhatIf() {
  const name = document.getElementById("wiName").value.trim();
  const quantity = Number(document.getElementById("wiQuantity").value);
  const resultEl = document.getElementById("wiResult");
  if (!name) { toast("Enter the product you want to simulate"); document.getElementById("wiName").focus(); return; }
  if (!Number.isFinite(quantity) || quantity <= 0) { toast("Enter a quantity greater than zero"); document.getElementById("wiQuantity").focus(); return; }

  const button = document.getElementById("simulateBtn");
  button.disabled = true;
  resultEl.innerHTML = `<div class="empty-state">Simulating your purchase…</div>`;
  try {
    const data = await api.post("/insights/what-if", {
      name, category: whatIfCategory, storage: document.getElementById("wiStorage").value,
      quantity, unit: document.getElementById("wiUnit").value,
      expires_in_days: Number(document.getElementById("wiSlider").value),
    });
    const color = riskColorVar(data.risk_label);
    const consumedText = data.estimated_consumed == null
      ? "Not enough consumption data" : `${data.estimated_consumed} ${data.unit}`;
    const remainingText = data.estimated_remaining == null
      ? "Unavailable" : `${data.estimated_remaining} ${data.unit}`;
    resultEl.innerHTML = `
      <div class="card whatif-result wi-result-card">
        ${riskRingSVG(data.risk_score, 68)}
        <div class="info"><h4 style="color:${color}">${escapeHtml(data.risk_label)}</h4>
          <p><strong>${escapeHtml(data.product_name)}</strong> · ${data.quantity} ${escapeHtml(data.unit)} · ${escapeHtml(data.storage)}</p>
          <p>Projected waste risk score: <strong>${data.risk_score}/100</strong></p>
          <div class="projection-bars">${data.projection.map(v => `<div class="bar" title="${v}/100" style="height:${Math.max(6, v)}%;background:${v >= 65 ? "var(--risk-high)" : v >= 40 ? "var(--risk-mid)" : "var(--risk-safe)"}"></div>`).join("")}</div>
          <p class="wi-help">Projected risk over the next 7 days</p>
        </div>
      </div>
      <div class="card wi-breakdown">
        <h3>Purchase breakdown</h3>
        <div class="wi-metric-grid">
          <div><span>Expected expiry</span><strong>${data.expires_in_days} days</strong></div>
          <div><span>Estimated consumed</span><strong>${consumedText}</strong></div>
          <div><span>Potentially remaining</span><strong>${remainingText}</strong></div>
          <div><span>Past waste rate</span><strong>${data.historical_waste_rate}%</strong></div>
        </div>
        <p class="wi-help">${escapeHtml(data.note)}</p>
        <div class="wi-components"><span>Expiry: ${data.components.expiry}/55</span><span>Quantity: ${data.components.quantity}/25</span><span>Storage: ${data.components.storage}/8</span><span>Purchase history: ${data.components.purchase_history}/12</span></div>
      </div>
      <p class="wi-disclaimer">This is an estimate based on the information and history available. It does not add the product to your inventory.</p>
    `;
  } catch (err) {
    resultEl.innerHTML = `<div class="card"><p class="error-text">${escapeHtml(err.message || "Unable to run the simulation. Please try again.")}</p></div>`;
  } finally {
    button.disabled = false;
  }
}
