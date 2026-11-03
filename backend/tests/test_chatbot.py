"""Run:  cd backend && python tests/test_chatbot.py
Gemini is stubbed, so this needs no API key and makes no network calls."""
import os, sys, tempfile
from types import SimpleNamespace
from unittest import mock

os.environ.update(DATABASE_URL=f"sqlite:///{os.path.join(tempfile.mkdtemp(), 't.db')}", DB_SSL="false", GEMINI_API_KEY="")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.genai import errors
from app import create_app
from app.extensions import db
from app.services.membership import ensure_schema
import app.routes.chatbot as bot

app = create_app()
with app.app_context(): ensure_schema()
c = app.test_client()
c.post("/api/auth/register", json={"name": "T", "email": "t@x.com", "password": "secret1", "household_name": "H"})
c.post("/api/items", json={"name": "Spinach", "category": "produce", "quantity": 1, "unit": "bag"})

passed = failed = 0
def check(name, cond, extra=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {name}")
    else: failed += 1; print(f"  FAIL  {name} {extra}")
def ask(q="What can I cook?"): return c.post("/api/chatbot/message", json={"message": q}).get_json()["reply"]["content"]

print("\n== Setup / prompt")
check("no key -> friendly setup message", "GEMINI_API_KEY" in ask())

app.config["GEMINI_API_KEY"] = "fake-key"
seen = {}
class FakeModels:
    def generate_content(self, model, contents, config):
        seen.update(model=model, contents=contents, system=config.system_instruction, max=config.max_output_tokens)
        return SimpleNamespace(text="Try a spinach omelette!")
class FakeClient:
    def __init__(self, api_key=None): seen["key"] = api_key; self.models = FakeModels()

with mock.patch("google.genai.Client", FakeClient):
    check("success returns Gemini's text", ask("What can I cook tonight?") == "Try a spinach omelette!")
check("uses the configured key", seen["key"] == "fake-key")
check("default model is gemini-flash-latest", seen["model"] == "gemini-flash-latest")
check("user's question is the last turn sent", seen["contents"][-1].parts[0].text == "What can I cook tonight?" and seen["contents"][-1].role == "user")
check("system prompt carries the REAL inventory", "Spinach" in seen["system"] and "ShelfWise AI" in seen["system"])
check("token limit is generous (>=1024)", seen["max"] >= 1024)
app.config["GEMINI_MODEL"] = "gemini-2.5-flash"
with mock.patch("google.genai.Client", FakeClient): ask()
check("GEMINI_MODEL setting is honoured", seen["model"] == "gemini-2.5-flash")

print("\n== Empty / blocked answer")
class EmptyModels(FakeModels):
    def generate_content(self, **k): return SimpleNamespace(text=None)
class EmptyClient(FakeClient):
    def __init__(self, api_key=None): self.models = EmptyModels()
with mock.patch("google.genai.Client", EmptyClient):
    check("blocked/empty answer -> polite message, no crash", "rephras" in ask())

print("\n== Error messages")
def err_reply(exc):
    class M(FakeModels):
        def generate_content(self, **k): raise exc
    class C(FakeClient):
        def __init__(self, api_key=None): self.models = M()
    with mock.patch("google.genai.Client", C): return ask()
mk = lambda cls, code, msg, status="": cls(code, {"error": {"code": code, "message": msg, "status": status}})
r = err_reply(mk(errors.ClientError, 400, "API key not valid. Please pass a valid API key.", "INVALID_ARGUMENT"))
check("bad key (400) -> says key invalid", "GEMINI_API_KEY" in r and "invalid" in r, r)
check("403 -> key/permission message", "GEMINI_API_KEY" in err_reply(mk(errors.ClientError, 403, "Permission denied", "PERMISSION_DENIED")))
r = err_reply(mk(errors.ClientError, 429, "Quota exceeded", "RESOURCE_EXHAUSTED"))
check("429 -> rate limit / quota message", "rate limit" in r or "quota" in r, r)
r = err_reply(mk(errors.ClientError, 404, "model not found", "NOT_FOUND"))
check("404 -> unknown model message", "GEMINI_MODEL" in r, r)
r = err_reply(mk(errors.ServerError, 503, "overloaded", "UNAVAILABLE"))
check("503 -> temporarily unavailable", "overloaded" in r or "unavailable" in r, r)
import httpx
check("network failure -> can't reach Gemini", "couldn't reach" in err_reply(httpx.ConnectError("boom")))
r = err_reply(ValueError("weird"))
check("unknown error -> generic message naming the type", "ValueError" in r, r)
check("errors never leak raw exception text/keys", "fake-key" not in r)

print("\n== Temporary overloads: retry, then fall back")
app.config.update(GEMINI_MODEL="main-model", GEMINI_FALLBACK_MODEL="backup-model")
def scripted(plan):
    """plan: list of exceptions/strings consumed per call. Returns (client_cls, calls)."""
    calls = []
    class M:
        def generate_content(self, model, contents, config):
            calls.append(model); step = plan[min(len(calls) - 1, len(plan) - 1)]
            if isinstance(step, Exception): raise step
            return SimpleNamespace(text=step)
    class C:
        def __init__(self, api_key=None): self.models = M()
    return C, calls
S503 = lambda: mk(errors.ServerError, 503, "The model is overloaded.", "UNAVAILABLE")
with mock.patch("time.sleep"):
    C, calls = scripted([S503(), "Recovered on retry"])
    with mock.patch("google.genai.Client", C): r = ask()
    check("one 503 then success -> user just gets the answer", r == "Recovered on retry", r)
    check("...by retrying the SAME model", calls == ["main-model", "main-model"], calls)
    C, calls = scripted([S503(), S503(), "Answered by backup"])
    with mock.patch("google.genai.Client", C): r = ask()
    check("main model down -> falls back to backup model", r == "Answered by backup" and calls == ["main-model", "main-model", "backup-model"], (r, calls))
    C, calls = scripted([mk(errors.ClientError, 429, "quota", "RESOURCE_EXHAUSTED"), mk(errors.ClientError, 429, "quota", "RESOURCE_EXHAUSTED"), "Backup has its own quota"])
    with mock.patch("google.genai.Client", C): r = ask()
    check("rate limit on main -> backup model used", r == "Backup has its own quota", r)
    C, calls = scripted([S503()])
    with mock.patch("google.genai.Client", C): r = ask()
    check("everything overloaded -> friendly message after 4 tries", "overloaded" in r and len(calls) == 4, (r, len(calls)))
    C, calls = scripted([mk(errors.ClientError, 403, "denied", "PERMISSION_DENIED")])
    with mock.patch("google.genai.Client", C): r = ask()
    check("bad key is NOT retried (1 call, immediate message)", len(calls) == 1 and "GEMINI_API_KEY" in r, (r, calls))
    app.config["GEMINI_FALLBACK_MODEL"] = ""
    C, calls = scripted([S503()])
    with mock.patch("google.genai.Client", C): r = ask()
    check("empty fallback disables it (main only, 2 tries)", calls == ["main-model", "main-model"], calls)

print("\n== Real SDK constructs a client with the key (no network call)")
from google import genai
check("genai.Client(api_key=...) builds", genai.Client(api_key="x") is not None)

print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
