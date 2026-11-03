"""Run:  cd backend && python tests/test_agent.py

Runs the REAL google-genai SDK (including its automatic function-calling loop)
against a tiny fake Gemini server on localhost, so no API key or internet is
needed and nothing touches your real database."""
import os, sys, json, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.update(DATABASE_URL=f"sqlite:///{os.path.join(tempfile.mkdtemp(), 't.db')}", DB_SSL="false", GEMINI_API_KEY="fake-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ------------------------------------------------------------------ fake Gemini
SCRIPT, REQUESTS = [], []           # queued responses / bodies the server received

class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        REQUESTS.append({"path": self.path, "body": body})
        step = SCRIPT.pop(0) if SCRIPT else {"text": "(script ran out)"}
        if "error" in step:
            payload, status = {"error": {"code": step["error"], "message": "fake failure", "status": "UNAVAILABLE"}}, step["error"]
        else:
            parts = ([{"functionCall": {"name": n, "args": a}} for n, a in step["calls"]] if "calls" in step
                     else [{"text": step["text"]}])
            payload, status = {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP", "index": 0}]}, 200
        out = json.dumps(payload).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ["GOOGLE_GEMINI_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"

from unittest import mock
from app import create_app
from app.extensions import db
from app.models import ShoppingListItem, BoardNote, Item, PurchaseHistory
from app.services.membership import ensure_schema

app = create_app()
with app.app_context(): ensure_schema()
app.config.update(GEMINI_MODEL="main-model", GEMINI_FALLBACK_MODEL="")

passed = failed = 0
def check(name, cond, extra=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {name}")
    else: failed += 1; print(f"  FAIL  {name}  {extra}")

def script(*steps): SCRIPT[:] = list(steps); REQUESTS.clear()
def say(c, msg, voice=False):
    r = c.post("/api/chatbot/message", json={"message": msg, "voice": voice}); return r.get_json()
def rows(model, **kw):
    with app.app_context(): return model.query.filter_by(**kw).all()
def out(fr):
    """The tool's return value as the SDK delivered it to the model."""
    r = fr["response"]
    return r["result"] if set(r) == {"result"} else r["output"] if set(r) == {"output"} else r
def last_tool_results(n=-1):
    """functionResponse parts the SDK sent back to the model in request n."""
    out = []
    for c in REQUESTS[n]["body"]["contents"]:
        for p in c.get("parts", []):
            if "functionResponse" in p: out.append(p["functionResponse"])
    return out

c = app.test_client()
c.post("/api/auth/register", json={"name": "Mia Chen", "email": "m@x.com", "password": "secret1", "household_name": "The Chens"})
hid = c.get("/api/households/current").get_json()["household"]["id"]
c.post("/api/items", json={"name": "Spinach", "category": "produce", "expiry_date": "2099-01-01"})
c.post("/api/items", json={"name": "Whole Milk", "category": "dairy"})

print("\n== 'Add milk to my list' by voice")
script({"calls": [("add_to_shopping_list", {"item_name": "oat milk"})]}, {"text": "Added oat milk to your list."})
r = say(c, "add oat milk to my list", voice=True)
check("reply is the model's final sentence", r["reply"]["content"] == "Added oat milk to your list.", r)
check("row really exists in the shopping list table", [x.name for x in rows(ShoppingListItem, household_id=hid)] == ["oat milk"])
check("action reported to the UI", r["actions"] == [{"type": "shopping_added", "text": "Added oat milk to the shopping list"}], r["actions"])
check("SDK sent 2 requests (call -> result -> answer)", len(REQUESTS) == 2)
first = REQUESTS[0]["body"]
names = [d["name"] for t in first["tools"] for d in t["functionDeclarations"]]
check("all 6 tools were offered to Gemini", sorted(names) == sorted(["get_inventory", "get_shopping_list", "get_board_notes", "add_to_shopping_list", "add_board_note", "add_inventory_item"]), names)
sysi = first["systemInstruction"]["parts"][0]["text"]
check("system prompt: knows the household + user", "The Chens" in sysi and "Mia Chen" in sysi)
check("system prompt: knows today's date", __import__("datetime").date.today().strftime("%Y") in sysi)
check("system prompt: has the REAL inventory", "Spinach" in sysi and "Whole Milk" in sysi)
check("voice flag switches to spoken-style answers", "VOICE MODE" in sysi)
check("the model got the tool's result back", out(last_tool_results()[0])["ok"] is True)
check("uses the model from settings", "main-model" in REQUESTS[0]["path"], REQUESTS[0]["path"])

print("\n== Several actions in one sentence")
script({"calls": [("add_inventory_item", {"name": "Eggs", "category": "dairy", "quantity": 12, "unit": "unit", "storage": "fridge", "expires_in_days": 21}),
                  ("add_inventory_item", {"name": "Bread", "category": "bakery", "storage": "counter", "expires_in_days": 4}),
                  ("add_board_note", {"text": "Need olive oil"})]},
       {"text": "Done: eggs and bread added, note posted."})
r = say(c, "I bought 12 eggs and bread, and put a note that we need olive oil")
kinds = sorted(a["type"] for a in r["actions"])
check("3 actions performed", kinds == ["inventory_added", "inventory_added", "note_added"], kinds)
eggs = rows(Item, household_id=hid, name="Eggs")[0]
check("eggs saved with quantity, storage and expiry date", eggs.quantity == 12 and eggs.storage == "fridge" and eggs.expiry_date is not None and not eggs.is_estimate)
bread = rows(Item, household_id=hid, name="Bread")[0]
check("bread: category + counter storage", bread.category == "bakery" and bread.storage == "counter")
check("purchase history logged (feeds analytics)", len(rows(PurchaseHistory, household_id=hid, item_name="Eggs")) == 1)
check("note is on the board", [n.text for n in rows(BoardNote, household_id=hid)] == ["Need olive oil"])
with app.app_context():
    poster = BoardNote.query.filter_by(household_id=hid).first().posted_by.name
check("board note credited to the person who spoke", poster == "Mia Chen", poster)
inv = c.get("/api/items").get_json()["items"]
check("new items show up in the normal inventory API", {"Eggs", "Bread"} <= {i["name"] for i in inv})

print("\n== Reading household data")
script({"calls": [("get_inventory", {"category": "dairy"})]}, {"text": "You have milk and eggs."})
r = say(c, "what dairy do we have?")
res = out(last_tool_results()[0])
check("model receives the real dairy items", sorted(i["name"] for i in res["items"]) == ["Eggs", "Whole Milk"], res)
check("...with quantities, storage and expiry info", all({"quantity", "storage", "expires", "days_left", "waste_risk"} <= set(i) for i in res["items"]))
check("a read-only question changes nothing", r["actions"] == [])
script({"calls": [("get_inventory", {"expiring_within_days": 5})]}, {"text": "Bread expires soon."})
say(c, "what's expiring this week?")
res = out(last_tool_results()[0])
check("expiry filter works (only bread is within 5 days)", [i["name"] for i in res["items"]] == ["Bread"], res)
script({"calls": [("get_shopping_list", {}), ("get_board_notes", {})]}, {"text": "ok"})
say(c, "what's on my list and the board?")
outs = {fr["name"]: out(fr) for fr in last_tool_results()}
check("shopping list + board readable", outs["get_shopping_list"]["items"] == ["oat milk"] and outs["get_board_notes"]["notes"][0]["text"] == "Need olive oil", outs)

print("\n== Recipes")
script({"text": "Try a spinach omelette: 2 eggs per person..."})
r = say(c, "recipe for 3 people")
check("recipe answers come straight through, no side effects", r["reply"]["content"].startswith("Try a spinach omelette") and r["actions"] == [])

print("\n== Safe against bad model output")
script({"calls": [("add_inventory_item", {"name": "Candy", "category": "sweets", "quantity": -5, "storage": "attic"})]}, {"text": "ok"})
say(c, "add candy")
candy = rows(Item, household_id=hid, name="Candy")[0]
check("invalid category/storage/quantity are corrected, not stored", (candy.category, candy.storage, candy.quantity) == ("other", "fridge", 1.0), (candy.category, candy.storage, candy.quantity))
script({"calls": [("add_board_note", {"text": "   "}), ("add_to_shopping_list", {"item_name": ""})]}, {"text": "Couldn't."})
r = say(c, "add nothing")
check("empty names are refused", r["actions"] == [] and all(out(fr)["ok"] is False for fr in last_tool_results()))
script({"calls": [("add_to_shopping_list", {"item_name": "OAT MILK"})]}, {"text": "It's already there."})
r = say(c, "add oat milk again")
check("duplicate shopping items aren't added twice", len(rows(ShoppingListItem, household_id=hid)) == 1 and r["actions"] == [])
script({"calls": [("delete_everything", {})]}, {"text": "I can't do that."})
r = say(c, "delete all my data")
check("unknown/unsafe tool names can't do anything", r["actions"] == [] and len(rows(Item, household_id=hid)) > 0)

print("\n== Temporary Gemini overload mid-action: never duplicates")
script({"calls": [("add_to_shopping_list", {"item_name": "butter"})]},   # SDK runs tool, then...
       {"error": 503},                                                   # ...the follow-up request is overloaded
       {"calls": [("add_to_shopping_list", {"item_name": "butter"})]},   # retry: model asks again
       {"text": "Added butter."})
import time; real_sleep = time.sleep
with mock.patch("time.sleep"):
    r = say(c, "add butter to my list")
check("user still gets the final answer", r["reply"]["content"] == "Added butter.", r)
check("butter is on the list exactly ONCE", [x.name for x in rows(ShoppingListItem, household_id=hid)].count("butter") == 1)
check("and reported once", len(r["actions"]) == 1, r["actions"])

script({"calls": [("add_to_shopping_list", {"item_name": "jam"})]}, {"error": 503}, {"error": 503}, {"error": 503})
with mock.patch("time.sleep"):
    r = say(c, "add jam")
check("if Gemini stays down AFTER an action, the reply is honest about what was done", "overloaded" in r["reply"]["content"] and "Added jam" in r["reply"]["content"], r["reply"]["content"])

print("\n== Conversation memory")
script({"text": "First answer"}); say(c, "remember the number 42")
script({"text": "Second answer"}); say(c, "what number?")
turns = [(x["role"], x["parts"][0]["text"]) for x in REQUESTS[0]["body"]["contents"] if "text" in x["parts"][0]]
check("earlier turns are sent so follow-ups work", ("user", "remember the number 42") in turns and ("model", "First answer") in turns, turns)
check("the newest question is last", turns[-1] == ("user", "what number?"))
check("history starts with a user turn", turns[0][0] == "user")

print("\n== Household isolation")
d = app.test_client()
d.post("/api/auth/register", json={"name": "Dan", "email": "d@x.com", "password": "secret1", "household_name": "Dans"})
script({"calls": [("get_inventory", {}), ("get_shopping_list", {}), ("get_board_notes", {})]}, {"text": "Nothing."})
say(d, "what do we have?")
outs = {fr["name"]: out(fr) for fr in last_tool_results()}
check("Dan's AI sees none of Mia's inventory/list/notes", outs["get_inventory"]["count"] == 0 and outs["get_shopping_list"]["count"] == 0 and outs["get_board_notes"]["count"] == 0, outs)
script({"calls": [("add_to_shopping_list", {"item_name": "dan-only"})]}, {"text": "ok"}); say(d, "add dan-only")
check("Dan's additions land in Dan's household only", len(rows(ShoppingListItem, household_id=hid, name="dan-only")) == 0)
check("Dan's system prompt has no Mia data", "Spinach" not in REQUESTS[0]["body"]["systemInstruction"]["parts"][0]["text"])

print(f"\n{passed} passed, {failed} failed"); sys.exit(1 if failed else 0)
