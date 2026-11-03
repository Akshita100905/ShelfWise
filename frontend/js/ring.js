// Risk-score ring (SVG) + badge helpers shared across pages.
function riskColorVar(label) {
  if (label === "High Risk") return "var(--risk-high)";
  if (label === "Expiring Soon") return "var(--risk-mid)";
  return "var(--risk-safe)";
}

function riskBadgeClass(label) {
  if (label === "High Risk") return "badge-high";
  if (label === "Expiring Soon") return "badge-mid";
  return "badge-safe";
}

function riskRingSVG(score, size = 54) {
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (score / 100) * c;
  const color = score >= 65 ? "var(--risk-high)" : score >= 40 ? "var(--risk-mid)" : "var(--risk-safe)";
  return `
    <div class="ring-wrap" style="width:${size}px;height:${size}px;">
      <svg width="${size}" height="${size}">
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" stroke="var(--border)" stroke-width="${stroke}" fill="none"/>
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" stroke="${color}" stroke-width="${stroke}" fill="none"
          stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${offset}"/>
      </svg>
      <div class="ring-score" style="color:${color};">${score}</div>
    </div>`;
}

function daysLeftLabel(days) {
  if (days === null || days === undefined) return "No expiry set";
  if (days < 0) return "Expired";
  if (days === 0) return "Today!";
  if (days === 1) return "Tomorrow!";
  return `${days} days`;
}
