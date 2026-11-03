function setAuthMode(mode) {
  const isSignup = mode === "signup";
  document.getElementById("signupForm").classList.toggle("hidden", !isSignup);
  document.getElementById("loginForm").classList.toggle("hidden", isSignup);
  document.getElementById("tabSignup").classList.toggle("active", isSignup);
  document.getElementById("tabLogin").classList.toggle("active", !isSignup);
  document.getElementById("authTitle").textContent = isSignup ? "Create account" : "Welcome back";
  document.getElementById("authSub").textContent = isSignup
    ? "Start wasting less in 15 seconds"
    : "Sign in to your kitchen";
  document.title = isSignup ? "ShelfWise — Create account" : "ShelfWise — Sign in";
  document.getElementById("authSwitchLine").innerHTML = isSignup
    ? `Already have an account? <a href="#" onclick="setAuthMode('login');return false;">Sign in</a>`
    : `New here? <a href="#" onclick="setAuthMode('signup');return false;">Create an account</a>`;
  hideAuthError();
}

// After a successful login/register, confirm the browser really kept the
// session cookie before leaving. If it didn't, say why instead of looping
// between auth.html and app.html.
async function goToApp() {
  const { user } = await api.get("/auth/me");
  if (!user) {
    throw new Error(
      "You're signed in, but your browser didn't keep the session. Open this page from the same host as the API " +
      `(currently ${window.location.hostname}) and make sure the backend is running on port 5000.`
    );
  }
  window.location.href = "app.html";
}

function showAuthError(msg) {
  const el = document.getElementById("authError");
  el.textContent = msg;
  el.classList.remove("hidden");
}
function hideAuthError() {
  document.getElementById("authError").classList.add("hidden");
}

/* ---------- invite links: auth.html?invite=TOKEN (or ?code=CODE) ---------- */
const _params = new URLSearchParams(window.location.search);
const INVITE = (_params.get("invite") || _params.get("code") || "").trim();
let invitePreview = null;   // set only if the link/code checked out

const esc = (t) => { const d = document.createElement("div"); d.textContent = t; return d.innerHTML; };

function showInviteBanner(html, bad = false) {
  const el = document.getElementById("inviteBanner");
  el.className = "invite-banner" + (bad ? " bad" : "");
  el.innerHTML = html;
}

// Shows which household the link points to BEFORE anything is created or joined.
async function loadInvitePreview() {
  if (!INVITE) return;
  try {
    invitePreview = await api.get(`/households/preview?value=${encodeURIComponent(INVITE)}`);
    const h = invitePreview.household;
    showInviteBanner(`
      <div style="font-size:30px">🏠</div>
      <div><div class="ib-title">You're invited to join ${esc(h.name)}</div>
      <div class="ib-sub">${h.member_count} member${h.member_count === 1 ? "" : "s"}${invitePreview.invited_by ? ` · invited by ${esc(invitePreview.invited_by)}` : ""}</div>
      <div id="inviteBannerActions"></div></div>`);
    // signing up via an invite: no need to name a new household
    document.getElementById("suInvite").value = INVITE;
    document.getElementById("suInvite").closest(".field").classList.add("hidden");   // token is carried invisibly
    document.getElementById("suHousehold").closest(".field").classList.add("hidden");
    document.querySelector("#signupForm button[type=submit]").textContent = `Create account & join ${h.name}`;
    document.querySelector("#loginForm button[type=submit]").textContent = `Sign in & join ${h.name}`;
  } catch (err) {
    showInviteBanner(`<div style="font-size:30px">⚠️</div>
      <div><div class="ib-title">This invite can't be used</div><div class="ib-sub">${esc(err.message)}</div></div>`, true);
  }
}

// After signing in with an invite link open: actually join the household.
async function joinInviteIfAny() {
  if (!invitePreview) return;
  await api.post("/households/join", { invite_token: INVITE });
}

async function handleSignup(e) {
  e.preventDefault();
  hideAuthError();
  const payload = {
    name: document.getElementById("suName").value.trim(),
    email: document.getElementById("suEmail").value.trim(),
    password: document.getElementById("suPassword").value,
    household_name: document.getElementById("suHousehold").value.trim(),
    invite_code: document.getElementById("suInvite").value.trim(),
  };
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api.post("/auth/register", payload);
    await goToApp();
  } catch (err) {
    console.error("SIGNUP ERROR:", err);
    showAuthError(err.message);
  } finally {
    btn.disabled = false;
  }
  return false;
}

async function handleLogin(e) {
  e.preventDefault();
  hideAuthError();
  const payload = {
    email: document.getElementById("liEmail").value.trim(),
    password: document.getElementById("liPassword").value,
  };
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api.post("/auth/login", payload);
    await joinInviteIfAny();
    await goToApp();
  } catch (err) {
    console.error("LOGIN ERROR:", err);
    showAuthError(err.message);
  } finally {
    btn.disabled = false;
  }
  return false;
}

// Startup: show the invite (if any), then either continue into the app or,
// if the person is already signed in, ask before joining.
(async function init() {
  await loadInvitePreview();
  try {
    const { user } = await api.get("/auth/me");
    if (!user) return;

    if (INVITE && invitePreview && !invitePreview.already_member) {
      const h = invitePreview.household;
      // Already signed in: this page is just a confirmation, not a sign-up form.
      ["signupForm", "loginForm", "authSwitchLine"].forEach((id) => document.getElementById(id).classList.add("hidden"));
      document.querySelector(".auth-tabs").classList.add("hidden");
      document.getElementById("authTitle").textContent = "Join another household";
      document.getElementById("authSub").textContent = "Your other households stay exactly as they are.";
      document.getElementById("inviteBannerActions").innerHTML = `
        <div class="ib-sub" style="margin-top:6px">You're signed in as ${esc(user.name)}.</div>
        <div class="ib-actions">
          <button class="btn btn-primary btn-sm" id="ibJoin">Join ${esc(h.name)}</button>
          <a class="btn btn-ghost btn-sm" href="app.html" style="text-decoration:none">Not now</a>
        </div>`;
      document.getElementById("ibJoin").onclick = async (ev) => {
        ev.target.disabled = true;
        try { await joinInviteIfAny(); window.location.href = "app.html"; }
        catch (err) { showAuthError(err.message); ev.target.disabled = false; }
      };
      return;                       // stay here until they choose
    }
    if (INVITE && !invitePreview) {  // bad link: let them read the message, then go on
      document.querySelector("#inviteBanner div:last-child").insertAdjacentHTML("beforeend",
        `<div class="ib-actions"><a class="btn btn-outline btn-sm" href="app.html" style="text-decoration:none">Continue to ShelfWise</a></div>`);
      return;
    }
    window.location.href = "app.html";
  } catch (err) {
    console.error("SESSION CHECK ERROR:", err);
    showAuthError(err.message);
  }
})();
