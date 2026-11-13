let wasteChartInstance = null;
let savingsChartInstance = null;

async function renderAnalyticsPage(main) {
  const data = await api.get("/analytics");

  main.innerHTML = `
    <div class="page-header"><h1>Analytics</h1><p>Your waste reduction story</p></div>

    <div class="stat-cards">
      <div class="card stat-card warn"><div class="ic">📉</div><div class="value">${data.waste_pct}%</div><div class="label">waste reduced</div></div>
      <div class="card stat-card money"><div class="ic">💰</div><div class="value">₹${data.saved_this_period}</div><div class="label">saved this month</div></div>
      <div class="card stat-card"><div class="ic">📦</div><div class="value">${data.items_tracked}</div><div class="label">items tracked</div></div>
    </div>

    <div class="card chart-card">
      <div class="head"><h3>Food Wasted</h3><span class="sub">kg per month</span></div>
      <div class="chart-box"><canvas id="wasteChart"></canvas></div>
    </div>

    <div class="card chart-card">
      <div class="head"><h3>Monthly Savings</h3><span class="sub">Estimated ₹ saved vs baseline</span></div>
      <div class="chart-box"><canvas id="savingsChart"></canvas></div>
    </div>

    <div class="card chart-card">
      <div class="head"><h3>Waste by Category</h3></div>
      <div id="categoryBars"></div>
    </div>
  `;

  const barColors = ["#f7931e", "#ef4444", "#2f9e3a", "#7cd142", "#fa5a39", "#5cb812"];
  // Set chart text colors according to the active theme
  const isDarkMode =
    document.documentElement.getAttribute("data-theme") === "dark";

  const chartTextColor = isDarkMode ? "#ffffff" : "#4b6356";

// Apply default text color to all Chart.js elements
  Chart.defaults.color = chartTextColor;
  const ctx1 = document.getElementById("wasteChart");
  wasteChartInstance?.destroy();
  wasteChartInstance = new Chart(ctx1, {
    type: "bar",
    data: {
      labels: data.food_wasted.months,
      datasets: [{ data: data.food_wasted.kg, backgroundColor: data.food_wasted.months.map((_, i) => barColors[i % barColors.length]), borderRadius: 6 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: {color: chartTextColor} },
        y: { grid: { color: "rgba(128,128,128,.15)" }, ticks: { color: chartTextColor} },
      },
    },
  });

  const ctx2 = document.getElementById("savingsChart");
  savingsChartInstance?.destroy();
  savingsChartInstance = new Chart(ctx2, {
    type: "line",
    data: {
      labels: data.monthly_savings.months,
      datasets: [{
        data: data.monthly_savings.amount, borderColor: "#fa5a39", backgroundColor: "rgba(250,90,57,.12)",
        fill: true, tension: 0.35, pointBackgroundColor: "#fa5a39",
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false },ticks: {color: chartTextColor }},
        y: { grid: { color: "rgba(128,128,128,.15)" }, ticks: { color: chartTextColor} },
      },
    },
  });

  const catIcons = { produce: "🥦", dairy: "🥛", meat: "🥩", bakery: "🍞", grains: "🍝", other: "📦" };
  document.getElementById("categoryBars").innerHTML = data.waste_by_category.map(c => `
    <div class="category-bar-row">
      <div class="top"><span>${catIcons[c.category] || "📦"} ${capitalize(c.category)}</span><span>${c.amount}kg · ${c.pct}%</span></div>
      <div class="category-bar-track"><div class="category-bar-fill" style="width:${c.pct}%"></div></div>
    </div>
  `).join("") || `<div class="empty-state">Not enough data yet.</div>`;
}
