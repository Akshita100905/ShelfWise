"""Run:  cd backend && python tests/test_households.py
Uses a throwaway SQLite file, never your real database."""
import os, sys, tempfile, smtplib
from datetime import timedelta
from unittest import mock

db_file = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", DB_SSL="false", GEMINI_API_KEY="")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db, bcrypt
from app.models import User, Household, Membership, Invite, now
from app.services.membership import ensure_schema

app = create_app()
with app.app_context():
    ensure_schema()

passed = failed = 0
def check(name, cond, extra=""):
    global passed, failed
    if cond: passed += 1; print(f"  PASS  {name}")
    else:    failed += 1; print(f"  FAIL  {name} {extra}")

def client(): return app.test_client()
def signup(c, name, email, household=None, invite=None):
    body = {"name": name, "email": email, "password": "secret1"}
    if household: body["household_name"] = household
    if invite: body["invite_code"] = invite
    return c.post("/api/auth/register", json=body)
def households(c): return c.get("/api/households").get_json()
def add_item(c, name): return c.post("/api/items", json={"name": name, "category": "dairy"})
def item_names(c): return [i["name"] for i in c.get("/api/items").get_json()["items"]]

print("\n== Sign-up creates an owner membership")
A, B = client(), client()
r = signup(A, "Alice", "a@x.com", "Alpha"); check("Alice registered", r.status_code == 201)
r = signup(B, "Bob", "b@x.com", "Beta");    check("Bob registered", r.status_code == 201)
check("Alice is owner of Alpha", households(A)["households"][0]["role"] == "owner")
alpha_code = A.get("/api/households/current").get_json()["household"]["invite_code"]
beta_code  = B.get("/api/households/current").get_json()["household"]["invite_code"]
check("each household has its own distinct code", alpha_code != beta_code)
add_item(A, "Alpha Milk"); add_item(B, "Beta Cheese")

print("\n== Preview: code points at the RIGHT household")
r = A.get(f"/api/households/preview?value={beta_code}").get_json()
check("Beta's code previews as 'Beta'", r["household"]["name"] == "Beta", r)
r = client().get(f"/api/households/preview?value={alpha_code.lower()}").get_json()
check("lowercase Alpha code previews as 'Alpha' (logged out)", r["household"]["name"] == "Alpha", r)
r = client().get("/api/households/preview?value=NOPE123")
check("unknown code -> 404 with message", r.status_code == 404 and "isn't valid" in r.get_json()["error"])
r = client().get("/api/households/preview?value=")
check("empty code -> 404", r.status_code == 404)

print("\n== Joining a second household keeps the first")
r = B.post("/api/households/join", json={"invite_code": alpha_code})
check("Bob joins Alpha with its code (201)", r.status_code == 201, r.get_data(as_text=True))
check("join response names Alpha", r.get_json()["household"]["name"] == "Alpha")
hs = households(B)
check("Bob now belongs to 2 households", len(hs["households"]) == 2, hs)
check("active household is Alpha", [h["name"] for h in hs["households"] if h["active"]] == ["Alpha"])
check("Bob (in Alpha) sees Alpha's items, not Beta's", item_names(B) == ["Alpha Milk"], item_names(B))
check("Bob is a plain member of Alpha", [h["role"] for h in hs["households"] if h["name"] == "Alpha"] == ["member"])
beta_id = [h["id"] for h in hs["households"] if h["name"] == "Beta"][0]
r = B.post("/api/households/switch", json={"household_id": beta_id})
check("switch to Beta ok", r.status_code == 200)
check("now sees only Beta's items", item_names(B) == ["Beta Cheese"], item_names(B))
check("still owner of Beta", B.get("/api/households/current").get_json()["my_role"] == "owner")
r = B.post("/api/households/join", json={"invite_code": alpha_code})
check("re-joining a household you're in is harmless (200)", r.status_code == 200 and r.get_json()["already_member"])
check("still only 2 households (no duplicate row)", len(households(B)["households"]) == 2)
r = B.post("/api/households/join", json={"invite_code": "ZZZZZZZ"})
check("wrong code -> 400, nothing changes", r.status_code == 400 and len(households(B)["households"]) == 2)

print("\n== Data isolation / access control")
C = client(); signup(C, "Cara", "c@x.com", "Gamma")
gamma_id = households(C)["households"][0]["id"]
r = C.post("/api/households/switch", json={"household_id": beta_id})
check("can't switch into a household you're not in (403)", r.status_code == 403)
check("Cara still only sees her own", item_names(C) == [])
members = A.get("/api/households/current").get_json()["members"]
check("Alpha lists both Alice and Bob", sorted(m["name"] for m in members) == ["Alice", "Bob"], members)
check("roles are per-household in member list",
      {m["name"]: m["role"] for m in members} == {"Alice": "owner", "Bob": "member"})

print("\n== Invite links: sent, used once, verified")
r = A.post("/api/households/invite", json={"email": "dan@x.com"}, headers={"Origin": "http://localhost:5500"})
d = r.get_json()
check("invite created (201) with a link", r.status_code == 201 and "auth.html?invite=" in d["link"], d)
check("link uses the caller's frontend origin", d["link"].startswith("http://localhost:5500/auth.html?invite="))
check("no SMTP configured -> email_sent False but link still returned", d["email_sent"] is False and d["link"])
token = d["link"].split("invite=")[1]
pv = client().get(f"/api/households/preview?value={token}").get_json()
check("invite link previews as Alpha, names the inviter", pv["household"]["name"] == "Alpha" and pv["invited_by"] == "Alice", pv)
pv = client().get("/api/households/preview", query_string={"value": d["link"]}).get_json()
check("pasting the whole link also works", pv["household"]["name"] == "Alpha", pv)
D = client(); r = signup(D, "Dan", "dan@x.com", invite=d["link"])
check("Dan signs up with the pasted link", r.status_code == 201)
check("Dan lands in Alpha (not a new household)", households(D)["households"][0]["name"] == "Alpha" and len(households(D)["households"]) == 1)
check("Dan sees Alpha's items", item_names(D) == ["Alpha Milk"])
E = client(); signup(E, "Eve", "e@x.com", "Eves")
r = E.post("/api/households/join", json={"invite_token": token})
check("used link can't be reused by someone else (400)", r.status_code == 400 and "already been used" in r.get_json()["error"], r.get_json())
check("Eve did NOT get into Alpha", all(h["name"] != "Alpha" for h in households(E)["households"]))
r = client().post("/api/auth/register", json={"name": "Fay", "email": "f@x.com", "password": "secret1", "invite_code": "BADCODE"})
check("sign-up with bad code fails cleanly (400)", r.status_code == 400)
check("...and does not create the account", client().post("/api/auth/login", json={"email": "f@x.com", "password": "secret1"}).status_code == 401)

print("\n== Expiry and cancelling")
with app.app_context():
    inv = Invite.query.filter_by(token=token).first()
r = A.post("/api/households/invite", json={}); tok2 = r.get_json()["link"].split("invite=")[1]; inv2 = r.get_json()["invite"]["id"]
with app.app_context():
    i = Invite.query.filter_by(token=tok2).first(); i.expires_at = now() - timedelta(minutes=1); db.session.commit()
r = E.post("/api/households/join", json={"invite_token": tok2})
check("expired link rejected", r.status_code == 400 and "expired" in r.get_json()["error"], r.get_json())
r = A.post("/api/households/invite", json={}); tok3 = r.get_json()["link"].split("invite=")[1]; id3 = r.get_json()["invite"]["id"]
check("pending invites are listed", any(i["id"] == id3 for i in A.get("/api/households/invites").get_json()["invites"]))
check("non-owner can't cancel someone else's invite", B.delete(f"/api/households/invites/{id3}").status_code == 403)
check("owner can cancel", A.delete(f"/api/households/invites/{id3}").status_code == 200)
r = E.post("/api/households/join", json={"invite_token": tok3})
check("cancelled link rejected", r.status_code == 400 and "cancelled" in r.get_json()["error"], r.get_json())
r = A.post("/api/households/invite", json={"email": "dan@x.com"})
check("can't invite someone who's already a member", r.status_code == 400 and "already" in r.get_json()["error"], r.get_json())
check("bad email rejected", A.post("/api/households/invite", json={"email": "nope"}).status_code == 400)

print("\n== Email sending (SMTP mocked)")
app.config.update(SMTP_HOST="smtp.test", SMTP_FROM="ShelfWise <no-reply@test>", SMTP_USER="u", SMTP_PASSWORD="p", SMTP_PORT=587)
sent = {}
class FakeSMTP:
    def __init__(self, host, port, timeout=None): sent["host"] = (host, port)
    def starttls(self): sent["tls"] = True
    def login(self, u, p): sent["login"] = (u, p)
    def send_message(self, m): sent["msg"] = m
    def __enter__(self): return self
    def __exit__(self, *a): return False
with mock.patch.object(smtplib, "SMTP", FakeSMTP):
    r = A.post("/api/households/invite", json={"email": "gus@x.com"}, headers={"Origin": "http://localhost:5500"}).get_json()
check("email_sent True", r["email_sent"] is True, r)
m = sent.get("msg")
check("addressed to the invitee", m and m["To"] == "gus@x.com")
body = m.get_body(preferencelist=("plain",)).get_content()
check("email contains the working link and code", r["link"] in body and alpha_code in body)
check("subject names inviter + household", "Alice" in m["Subject"] and "Alpha" in m["Subject"], m["Subject"])
class BadSMTP(FakeSMTP):
    def login(self, u, p): raise smtplib.SMTPAuthenticationError(535, b"bad")
with mock.patch.object(smtplib, "SMTP", BadSMTP):
    r = A.post("/api/households/invite", json={"email": "hal@x.com"}).get_json()
check("SMTP failure is reported, link still returned", r["email_sent"] is False and r["link"] and "rejected" in r["email_error"], r)
app.config.update(SMTP_HOST="", SMTP_FROM="")

print("\n== Leaving, roles, removal")
r = A.post("/api/households/leave", json={})
check("sole owner can't abandon a household others are in (400)", r.status_code == 400, r.get_json())
bob_id = [m["id"] for m in A.get("/api/households/current").get_json()["members"] if m["name"] == "Bob"][0]
check("non-owner can't promote", B.post(f"/api/households/members/{bob_id}/role", json={"role": "owner"}).status_code in (403,))
r = A.post(f"/api/households/members/{bob_id}/role", json={"role": "owner"})
check("owner promotes Bob", r.status_code == 200)
r = A.post("/api/households/leave", json={})
check("Alice can leave now (another owner exists)", r.status_code == 200, r.get_json())
check("Alice's active household moved to none/another (still logged in)", A.get("/api/auth/me").get_json()["user"] is not None)
check("Alice can no longer read Alpha's data (403/400)", A.get("/api/items").status_code in (400, 403))
dan_id = [m["id"] for m in B.get("/api/households/current").get_json()["members"] if m["name"] == "Dan"] 
B.post("/api/households/switch", json={"household_id": [h["id"] for h in households(B)["households"] if h["name"] == "Alpha"][0]})
dan_id = [m["id"] for m in B.get("/api/households/current").get_json()["members"] if m["name"] == "Dan"][0]
check("owner removes Dan", B.delete(f"/api/households/members/{dan_id}").status_code == 200)
check("removed Dan is locked out immediately", D.get("/api/items").status_code in (400, 403))
check("owner can't remove themselves this way", B.delete(f"/api/households/members/{bob_id}").status_code == 400)

print("\n== Code reset")
B_alpha_code = B.get("/api/households/current").get_json()["household"]["invite_code"]
new = B.post("/api/households/regenerate-code").get_json()["code"]
check("code changed", new != B_alpha_code)
check("old code no longer joins", client().get(f"/api/households/preview?value={B_alpha_code}").status_code == 404)
check("new code previews Alpha", client().get(f"/api/households/preview?value={new}").get_json()["household"]["name"] == "Alpha")

print("\n== Legacy account (created before this update, no membership row)")
with app.app_context():
    h = Household(name="Legacy Home", invite_code="LEGACY1"); db.session.add(h); db.session.flush()
    u = User(name="Old Timer", email="old@x.com", password_hash=bcrypt.generate_password_hash("secret1").decode(), household_id=h.id, role="owner")
    db.session.add(u); db.session.commit()
L = client()
r = L.post("/api/auth/login", json={"email": "old@x.com", "password": "secret1"})
check("legacy user logs in and keeps their household", r.status_code == 200 and r.get_json()["user"]["household_id"], r.get_json())
check("legacy role preserved (owner)", r.get_json()["user"]["role"] == "owner")
check("legacy household appears in list", [h["name"] for h in households(L)["households"]] == ["Legacy Home"])
check("legacy user can use the app", add_item(L, "Old Jam").status_code == 201)
with app.app_context():
    check("ensure_schema is idempotent", ensure_schema() == 0)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
