"""Household membership + invite helpers shared by the auth and household routes."""
import secrets
import string
from datetime import timedelta
from urllib.parse import urlparse, parse_qs

from flask import session, current_app, request
from sqlalchemy import inspect

from app.extensions import db
from app.models import Household, Membership, Invite, User, now


# ---------- schema / legacy data ----------

def ensure_schema():
    """Create any missing tables (never alters existing ones) and give every
    pre-existing user a membership row for the household they were already in.
    Safe to run any number of times."""
    db.create_all()
    created = 0
    for u in User.query.filter(User.household_id.isnot(None)).all():
        if not Membership.query.filter_by(user_id=u.id, household_id=u.household_id).first():
            db.session.add(Membership(user_id=u.id, household_id=u.household_id, role=u.role or "member"))
            created += 1
    if created:
        db.session.commit()
    return created


def missing_tables():
    have = set(inspect(db.engine).get_table_names())
    return {"household_members", "invites"} - have


# ---------- membership ----------

def get_membership(user_id, household_id):
    return Membership.query.filter_by(user_id=user_id, household_id=household_id).first()


def heal_legacy(user):
    """A user created before multi-household support has household_id but no
    membership row. Create it on the fly so nothing breaks before migration."""
    if user.household_id and not get_membership(user.id, user.household_id):
        db.session.add(Membership(user_id=user.id, household_id=user.household_id, role=user.role or "member"))
        db.session.commit()


def add_member(user, household, role="member"):
    m = get_membership(user.id, household.id)
    if m:
        return m, False
    m = Membership(user_id=user.id, household_id=household.id, role=role)
    db.session.add(m)
    return m, True


def activate(user, household_id):
    """Make `household_id` (or None) the household the user is currently working in."""
    user.household_id = household_id
    session["household_id"] = household_id
    if household_id is None:
        session.pop("household_id", None)


def resolve_active(user):
    """Pick a valid active household for the user (their saved one if they're
    still a member, else their oldest membership, else none) and sync the session."""
    heal_legacy(user)
    m = get_membership(user.id, user.household_id) if user.household_id else None
    if not m:
        m = (Membership.query.filter_by(user_id=user.id).order_by(Membership.joined_at.asc()).first())
        user.household_id = m.household_id if m else None
        db.session.commit()
    activate(user, user.household_id)
    return m


def user_payload(user, membership=None):
    d = user.to_dict()
    if membership is None and user.household_id:
        membership = get_membership(user.id, user.household_id)
    d["role"] = membership.role if membership else None   # role in the ACTIVE household
    return d


# ---------- codes & invites ----------

def unique_code(n=7):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(n))
        if not Household.query.filter_by(invite_code=code).first():
            return code


def new_invite(household, invited_by, email=None):
    days = current_app.config.get("INVITE_EXPIRY_DAYS", 7)
    inv = Invite(
        household_id=household.id,
        invited_by_id=invited_by.id,
        email=(email or None),
        token=secrets.token_urlsafe(24),
        expires_at=now() + timedelta(days=days),
    )
    db.session.add(inv)
    return inv


def invite_link(token, link_base=None):
    """Where an invite link should point. The server can't know which folder the
    frontend is served from (e.g. Live Server serving the project root puts the
    page at /frontend/auth.html), so:
      1. FRONTEND_URL, if you set it (best for production);
      2. else the address the caller's browser sent as `link_base`, but only if it
         is on the same origin as the request, so it can't be abused to make the
         server email arbitrary links;
      3. else <Origin>/auth.html as a last resort."""
    configured = current_app.config.get("FRONTEND_URL")
    if configured:
        return f"{configured}/auth.html?invite={token}"

    origin = (request.headers.get("Origin") or "").rstrip("/")
    if link_base:
        u = urlparse(link_base)
        base_origin = f"{u.scheme}://{u.netloc}"
        if u.scheme in ("http", "https") and base_origin == origin and u.path.endswith("auth.html"):
            return f"{base_origin}{u.path}?invite={token}"
    return f"{origin}/auth.html?invite={token}" if origin else f"auth.html?invite={token}"


def parse_invite_value(value):
    """Accept a bare code, a bare token, or a pasted invite link."""
    v = (value or "").strip()
    if v.lower().startswith(("http://", "https://")):
        q = parse_qs(urlparse(v).query)
        v = ((q.get("invite") or q.get("code") or [""])[0]).strip()
    return v


def resolve_invite(value, user_id=None):
    """Work out which household a code/token/link points at.
    Returns (household, invite_or_None, error_message_or_None)."""
    v = parse_invite_value(value)
    if not v:
        return None, None, "Enter an invite code or link"

    inv = Invite.query.filter_by(token=v).first()
    if inv:
        if inv.accepted_at and inv.accepted_by_id and inv.accepted_by_id == user_id:
            return inv.household, inv, None          # you already used this link: harmless
        status = inv.status
        if status == "accepted":
            return None, None, "This invite link has already been used. Ask for a new one."
        if status == "revoked":
            return None, None, "This invite was cancelled. Ask for a new one."
        if status == "expired":
            return None, None, "This invite link has expired. Ask for a new one."
        return inv.household, inv, None

    household = Household.query.filter_by(invite_code=v.upper()).first()
    if household:
        return household, None, None
    return None, None, "That invite code or link isn't valid. Check it and try again."
