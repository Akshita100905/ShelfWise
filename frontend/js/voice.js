/* =========================================================
   Voice assistant: speak -> ShelfWise AI (Gemini) -> it acts on your household
   (add to list / inventory / board, read your stock, suggest recipes) -> the
   answer is shown and read aloud.

   Speech-to-text uses the browser's Web Speech API (Chrome / Edge / Safari).
   Chrome sends the audio to Google's speech service, so it needs internet.
   ========================================================= */
let recognition = null;
let listening = false;
let voiceMuted = localStorage.getItem("shelfwise_voice_muted") === "1";

const SPEECH_LANGS = {
  es: "es-ES", fr: "fr-FR", de: "de-DE", pt: "pt-BR", it: "it-IT", hi: "hi-IN",
  ja: "ja-JP", ko: "ko-KR", zh: "zh-CN", ar: "ar-SA", nl: "nl-NL",
};
function speechLang() {
  const code = (typeof currentUser !== "undefined" && currentUser && currentUser.language) || "en";
  if (code === "en") return /^en/i.test(navigator.language) ? navigator.language : "en-US";
  return SPEECH_LANGS[code] || navigator.language || "en-US";
}

const VOICE_EXAMPLES = [
  "Add oat milk to my list",
  "I bought two litres of milk",
  "Post a note: we need olive oil",
  "What's expiring soon?",
  "What can I cook tonight?",
];

/* ---------------- the panel ---------------- */
function ensureVoiceSheet() {
  let sheet = document.getElementById("voiceSheet");
  if (sheet) return sheet;
  sheet = document.createElement("div");
  sheet.id = "voiceSheet";
  sheet.className = "voice-sheet";
  sheet.setAttribute("role", "dialog");
  sheet.setAttribute("aria-label", "ShelfWise voice assistant");
  sheet.innerHTML = `
    <div class="vs-head">
      <div class="vs-title"><span class="vs-dot"></span> ShelfWise AI</div>
      <button class="vs-icon" id="vsMute" aria-label="Mute spoken replies"></button>
      <button class="vs-icon" id="vsClose" aria-label="Close"><svg class="i i-sm" aria-hidden="true"><use href="#i-x"/></svg></button>
    </div>
    <div class="vs-body" id="vsBody" aria-live="polite"></div>
    <div class="vs-foot">
      <button class="vs-mic" id="vsMic" aria-label="Speak"><svg class="i" aria-hidden="true"><use href="#i-mic"/></svg></button>
      <input id="vsInput" type="text" placeholder="…or type a request" autocomplete="off">
      <button class="vs-send" id="vsSend" aria-label="Send"><svg class="i i-sm" aria-hidden="true"><use href="#i-send"/></svg></button>
    </div>`;
  document.body.appendChild(sheet);
  document.getElementById("vsClose").onclick = closeVoiceSheet;
  document.getElementById("vsMic").onclick = toggleVoice;
  document.getElementById("vsMute").onclick = () => {
    voiceMuted = !voiceMuted;
    localStorage.setItem("shelfwise_voice_muted", voiceMuted ? "1" : "0");
    if (voiceMuted) cancelSpeech();
    paintMute();
  };
  const send = () => {
    const el = document.getElementById("vsInput"); const t = el.value.trim();
    if (t) { el.value = ""; processVoice(t); }
  };
  document.getElementById("vsSend").onclick = send;
  document.getElementById("vsInput").onkeydown = (e) => { if (e.key === "Enter") send(); };
  paintMute();
  return sheet;
}
function paintMute() {
  const b = document.getElementById("vsMute");
  if (!b) return;
  b.innerHTML = `<svg class="i i-sm" aria-hidden="true"><use href="#i-${voiceMuted ? "volume-off" : "volume"}"/></svg>`;
  b.title = voiceMuted ? "Spoken replies are off" : "Spoken replies are on";
  b.setAttribute("aria-pressed", voiceMuted ? "true" : "false");
}
function openVoiceSheet() { ensureVoiceSheet().classList.add("open"); document.body.classList.add("voice-open"); }
function closeVoiceSheet() {
  if (listening) recognition?.abort();
  cancelSpeech();
  document.getElementById("voiceSheet")?.classList.remove("open");
  document.body.classList.remove("voice-open");
}

function vsRender(state, d = {}) {
  openVoiceSheet();
  const body = document.getElementById("vsBody");
  const said = d.transcript ? `<div class="vs-said">“${escapeHtml(d.transcript)}”</div>` : "";
  document.getElementById("vsMic")?.classList.toggle("on", state === "listening");
  const html = {
    idle: `<p class="vs-hint">Tap the mic and just say it. I can see your kitchen and act on it:</p>
           <div class="vs-examples">${VOICE_EXAMPLES.map((e) => `<button class="vs-example" data-q="${escapeHtml(e)}">${escapeHtml(e)}</button>`).join("")}</div>`,
    listening: `<div class="vs-wave" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
                <p class="vs-status">Listening…</p>${said}`,
    thinking: `${said}<div class="typing vs-typing"><span></span><span></span><span></span></div>`,
    reply: `${said}<div class="vs-reply md">${renderMarkdown(d.reply || "")}</div>${actionChipsHTML(d.actions)}`,
    error: `${said}<p class="vs-error">${escapeHtml(d.message || "Something went wrong.")}</p>`,
  }[state];
  body.innerHTML = html;
  body.querySelectorAll(".vs-example").forEach((b) => (b.onclick = () => processVoice(b.dataset.q)));
}

/* ---------------- speech in / out ---------------- */
function cancelSpeech() { try { window.speechSynthesis?.cancel(); } catch (e) {} }
function speak(text) {
  if (voiceMuted || !("speechSynthesis" in window)) return;
  const clean = text.replace(/[*_`#>•]/g, "").replace(/\s+/g, " ").trim();
  if (!clean) return;
  cancelSpeech();
  const u = new SpeechSynthesisUtterance(clean);
  u.lang = speechLang();
  u.rate = 1.02;
  window.speechSynthesis.speak(u);
}

const SPEECH_ERRORS = {
  "not-allowed": "Microphone access is blocked. Click the lock icon in the address bar, allow the microphone, and try again.",
  "service-not-allowed": "This browser won't allow speech recognition here. Try Chrome or Edge.",
  "no-speech": "I didn't hear anything. Tap the mic and try again.",
  "audio-capture": "I can't find a microphone. Check that one is connected.",
  "network": "Speech recognition needs an internet connection (Chrome sends audio to Google's speech service).",
};

// Called by the floating mic button and the mic inside the chat box.
async function toggleVoice() {
  if (listening) { recognition?.stop(); return; }
  cancelSpeech();

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    vsRender("error", { message: "Voice input isn't supported in this browser. Try Chrome or Edge. You can also type a request below." });
    return;
  }
  const fab = document.getElementById("micFab");
  recognition = new SR();
  recognition.lang = speechLang();
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.maxAlternatives = 1;

  let finalText = "", interim = "", failure = null;
  recognition.onstart = () => { listening = true; fab.classList.add("listening"); vsRender("listening"); };
  recognition.onresult = (ev) => {
    interim = "";
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      const t = ev.results[i][0].transcript;
      if (ev.results[i].isFinal) finalText += t; else interim += t;
    }
    vsRender("listening", { transcript: (finalText + " " + interim).trim() });
  };
  recognition.onerror = (ev) => { failure = ev.error; };
  recognition.onend = () => {
    listening = false;
    fab.classList.remove("listening");
    const heard = (finalText || interim).trim();
    if (heard) processVoice(heard);
    else if (failure === "aborted") return;
    else vsRender("error", { message: SPEECH_ERRORS[failure] || "I didn't catch that. Tap the mic and try again." });
  };
  try { recognition.start(); } catch (e) { vsRender("error", { message: "Couldn't start the microphone. Try again." }); }
}

/* ---------------- speech -> AI -> actions -> answer ---------------- */
async function processVoice(text) {
  vsRender("thinking", { transcript: text });
  try {
    const { reply, actions } = await askAssistant(text, { voice: true });
    vsRender("reply", { transcript: text, reply: reply.content, actions });
    mirrorIntoChat(text, reply, actions);
    speak(reply.content);
  } catch (err) {
    vsRender("error", { transcript: text, message: err.message });
  }
}

// Opening the panel from the floating button starts listening straight away.
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeVoiceSheet(); });
