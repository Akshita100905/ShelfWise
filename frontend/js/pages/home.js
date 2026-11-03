async function renderHomePage(main) {
  const [{ use_first, high_waste_risk }] = await Promise.all([
    api.get("/insights/use-first"),
  ]);

  const urgent = use_first.filter((i) => i.risk_label === "High Risk").length;
  const soon = use_first.filter((i) => i.risk_label === "Expiring Soon").length;
  const safe = use_first.filter((i) => i.risk_label === "Safe").length;

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const firstName = escapeHtml((currentUser.name || "").split(" ")[0]);
  const plural = (n) => `${n} item${n === 1 ? "" : "s"}`;
  const headline = urgent
    ? `<b>${plural(urgent)}</b> need using up today.`
    : soon
      ? `<b>${plural(soon)}</b> worth using soon. Nothing urgent.`
      : `Everything is fresh. Nice work.`;
  const total = urgent + soon + safe;
  const seg = (cls, n) => n ? `<span class="seg ${cls}" style="flex:${n}"></span>` : "";

  main.innerHTML = `
    <section class="hero">
      <img class="hero-mark" src="assets/logo-mark.png" alt="">
      <p class="hero-greeting">${greeting}, ${firstName}</p>
      <h1>${currentHousehold ? escapeHtml(currentHousehold.name) : "Your kitchen"}</h1>
      <p class="hero-sub">${headline}</p>
      <div class="status-bar" role="img" aria-label="${urgent} urgent, ${soon} use soon, ${safe} safe">
        ${total ? seg("urgent", urgent) + seg("soon", soon) + seg("safe", safe) : `<span class="seg none"></span>`}
      </div>
      <div class="status-legend">
        <button class="legend-item" onclick="navigate('use-first')"><span class="dot urgent"></span><b>${urgent}</b> Urgent</button>
        <button class="legend-item" onclick="navigate('use-first')"><span class="dot soon"></span><b>${soon}</b> Use soon</button>
        <button class="legend-item" onclick="navigate('inventory')"><span class="dot safe"></span><b>${safe}</b> Safe</button>
      </div>
    </section>

    <div class="quick-actions">
      <button class="btn btn-cta" onclick="navigate('use-first')"><svg class="i" aria-hidden="true"><use href="#i-zap"/></svg> Use First</button>
      <button class="btn btn-outline" onclick="navigate('what-if')"><svg class="i" aria-hidden="true"><use href="#i-flask"/></svg> What-If</button>
      <button class="btn btn-outline" onclick="openAddItemModal()"><svg class="i" aria-hidden="true"><use href="#i-plus"/></svg> Add item</button>
    </div>

    <div class="section-title">Use first <span class="count">${use_first.length}</span><a class="see-all" onclick="navigate('use-first')">See all</a></div>
    <div class="shelf">
      <div class="scroll-x" id="useFirstScroll"></div>
      <div class="shelf-rail"></div>
    </div>

    <div class="section-title">High waste risk <span class="count">${high_waste_risk.length}</span></div>
    <div id="highRiskList"></div>
  `;

  const scroll = document.getElementById("useFirstScroll");
  scroll.innerHTML = use_first.slice(0, 10).map((item) => `
    <div class="risk-card">
      <div class="emoji-badge">${item.icon}</div>
      ${riskRingSVG(item.risk_score, 54)}
      <div class="name">${escapeHtml(item.name)}</div>
      <div class="days" style="color:${riskColorVar(item.risk_label)}">${daysLeftLabel(item.days_left)}</div>
    </div>
  `).join("") || `<div class="empty-state" style="flex:1;margin-bottom:14px">Nothing urgent. Nice work! 🎉</div>`;

  document.getElementById("highRiskList").innerHTML = high_waste_risk.map(itemRowHTML).join("")
    || `<div class="empty-state">No high-risk items right now.</div>`;

  bindItemRowActions(main);
}
