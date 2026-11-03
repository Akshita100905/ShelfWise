// Light / dark / system theme handling, applied on every page.
function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
  localStorage.setItem("shelfwise_theme", theme);
}

function initTheme() {
  const saved = localStorage.getItem("shelfwise_theme") || "dark";
  applyTheme(saved);
  return saved;
}

initTheme();
