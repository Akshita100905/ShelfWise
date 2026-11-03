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
const CATEGORY_CHIPS = [["all", "All"], ["produce", "🥦"], ["dairy", "🥛"], ["meat", "🥩"], ["bakery", "🍞"], ["grains", "🍝"]];
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
async function renderWhatIfPage(main) {
  main.innerHTML = `
    <div class="page-header"><h1>What-If Simulator</h1><p>See what buying this would do to your waste risk</p></div>

    <div class="category-icon-row" id="wiCats">
      ${ITEM_CATEGORIES.map(([val, ic]) => `<button class="category-icon-btn ${whatIfCategory === val ? "active" : ""}" data-val="${val}">${ic}</button>`).join("")}
    </div>

    <div class="card slider-card">
      <label>Expires in</label>
      <div class="slider-row">
        <input type="range" id="wiSlider" min="1" max="30" value="7">
        <span class="days-val" id="wiDaysVal">7 days</span>
      </div>
    </div>

    <button class="btn btn-cta btn-block" id="simulateBtn">Simulate purchase</button>

    <div id="wiResult" style="margin-top:18px;"></div>
  `;
  document.querySelectorAll("#wiCats .category-icon-btn").forEach((btn) => {
    btn.onclick = () => {
      whatIfCategory = btn.dataset.val;
      document.querySelectorAll("#wiCats .category-icon-btn").forEach(b => b.classList.toggle("active", b === btn));
    };
  });
  const slider = document.getElementById("wiSlider");
  slider.oninput = () => { document.getElementById("wiDaysVal").textContent = `${slider.value} days`; };
  document.getElementById("simulateBtn").onclick = runWhatIf;
}

async function runWhatIf() {
  const days = parseInt(document.getElementById("wiSlider").value, 10);
  const resultEl = document.getElementById("wiResult");
  resultEl.innerHTML = `<div class="empty-state">Simulating…</div>`;
  const data = await api.post("/insights/what-if", { category: whatIfCategory, expires_in_days: days, quantity: 1 });
  const color = riskColorVar(data.risk_label);
  resultEl.innerHTML = `
    <div class="card whatif-result">
      ${riskRingSVG(data.risk_score, 60)}
      <div class="info">
        <h4 style="color:${color}">${data.risk_label}</h4>
        <p>Projected Waste Risk Score</p>
        <p>Projected waste risk over 7 days</p>
        <div class="projection-bars">
          ${data.projection.map(v => `<div class="bar" style="height:${Math.max(6, v)}%; background:${v >= 65 ? "var(--risk-high)" : v >= 40 ? "var(--risk-mid)" : "var(--risk-safe)"}"></div>`).join("")}
        </div>
      </div>
    </div>`;
}
