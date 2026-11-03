import re
from datetime import date
from flask import Blueprint, request, jsonify, session
from app.extensions import db
from app.models import Household, User, Item, Membership, Invite, now
from app.utils.decorators import login_required, household_required
from app.services.membership import (
    unique_code, get_membership, add_member, activate, resolve_active, resolve_invite,
    new_invite, invite_link, heal_legacy,
)
from app.services import mailer

bp = Blueprint("households", __name__, url_prefix="/api/households")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _me():
    user = User.query.get(session["user_id"])
    heal_legacy(user)
    return user


def _active_membership(user):
    """The caller's membership in their active household, or None."""
    if not user.household_id:
        return None
    return get_membership(user.id, user.household_id)


def _member_dict(m):
    d = m.user.to_dict()
    d["role"] = m.role                      # role in THIS household
    return {k: d[k] for k in ("id", "name", "email", "initials", "role")}


# ---------------------------------------------------------------- listing / current

@bp.get("")
@login_required
def list_mine():
    """Every household the signed-in user belongs to."""
    user = _me()
    rows = (
        db.session.query(Membership, Household)
        .join(Household, Household.id == Membership.household_id)
        .filter(Membership.user_id == user.id)
        .order_by(Membership.joined_at.asc())
        .all()
    )
    return jsonify({
        "active_id": user.household_id,
        "households": [
            {"id": h.id, "name": h.name, "role": m.role,
             "member_count": len(h.memberships), "active": h.id == user.household_id}
            for m, h in rows
        ],
    })


@bp.get("/current")
@login_required
def current():
    user = _me()
    mem = _active_membership(user)
    if not mem:
        return jsonify({"household": None, "members": []})

    household = mem.household
    members = (Membership.query.filter_by(household_id=household.id)
               .order_by(Membership.joined_at.asc()).all())
    total_items = Item.query.filter_by(household_id=household.id).count()

    return jsonify({
        "household": household.to_dict(),
        "my_role": mem.role,
        "members": [_member_dict(m) for m in members],
        "stats": {"total_items": total_items, "avg_days_per_month": 23},
    })


# ---------------------------------------------------------------- create / switch / leave

@bp.post("/create")
@login_required
def create():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Household name is required"}), 400

    user = _me()
    household = Household(name=name, invite_code=unique_code())
    db.session.add(household)
    db.session.flush()
    add_member(user, household, "owner")
    activate(user, household.id)
    db.session.commit()
    return jsonify({"household": household.to_dict()}), 201


@bp.post("/switch")
@login_required
def switch():
    data = request.get_json(force=True) or {}
    try:
        hid = int(data.get("household_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "household_id is required"}), 400

    user = _me()
    mem = get_membership(user.id, hid)
    if not mem:
        return jsonify({"error": "You're not a member of that household"}), 403
    activate(user, hid)
    db.session.commit()
    return jsonify({"household": mem.household.to_dict(), "role": mem.role})


@bp.post("/leave")
@login_required
def leave():
    data = request.get_json(force=True) or {}
    user = _me()
    hid = data.get("household_id") or user.household_id
    mem = get_membership(user.id, int(hid)) if hid else None
    if not mem:
        return jsonify({"error": "You're not a member of that household"}), 404

    others = Membership.query.filter(
        Membership.household_id == mem.household_id, Membership.user_id != user.id).all()
    if mem.role == "owner" and others and not any(o.role == "owner" for o in others):
        return jsonify({"error": "You're the only owner. Make someone else an owner before leaving."}), 400

    household = mem.household
    db.session.delete(mem)
    db.session.flush()

    if not others:
        # Last person out: retire the household's join code and cancel open invites.
        household.invite_code = unique_code()
        Invite.query.filter_by(household_id=household.id, accepted_at=None, revoked=False)\
            .update({"revoked": True})

    if user.household_id == household.id:
        nxt = Membership.query.filter_by(user_id=user.id).order_by(Membership.joined_at.asc()).first()
        activate(user, nxt.household_id if nxt else None)
    db.session.commit()
    return jsonify({"ok": True, "active_id": user.household_id})


# ---------------------------------------------------------------- joining (verify + join)

@bp.get("/preview")
def preview():
    """Public + read-only. Tells the person exactly which household a code or
    link points to BEFORE they join, so a mistyped code can't drop them into
    the wrong kitchen. Only reveals the household name and member count."""
    value = request.args.get("value") or request.args.get("invite") or request.args.get("code") or ""
    household, invite, err = resolve_invite(value, session.get("user_id"))
    if err:
        return jsonify({"error": err}), 404

    already = bool(session.get("user_id") and get_membership(session["user_id"], household.id))
    return jsonify({
        "household": {"name": household.name, "member_count": len(household.memberships)},
        "via": "invite_link" if invite else "code",
        "invited_by": invite.invited_by.name if invite and invite.invited_by else None,
        "expires_at": invite.expires_at.isoformat() + "Z" if invite else None,
        "already_member": already,
    })


@bp.post("/join")
@login_required
def join():
    data = request.get_json(force=True) or {}
    value = data.get("invite_token") or data.get("invite_code") or data.get("value") or ""
    user = _me()
    household, invite, err = resolve_invite(value, user.id)
    if err:
        return jsonify({"error": err}), 400

    mem, created = add_member(user, household, "member")
    if created and invite:
        invite.accepted_by_id = user.id
        invite.accepted_at = now()
    activate(user, household.id)
    db.session.commit()
    return jsonify({"household": household.to_dict(), "already_member": not created}), (201 if created else 200)


# ---------------------------------------------------------------- inviting

@bp.post("/invite")
@household_required
def invite():
    """Create a single-use invite link for the active household and, if an email
    was given and SMTP is configured, email it. Always returns the link so the
    UI can offer copy / share / WhatsApp / mailto as a fallback."""
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    link_base = data.get("link_base") or None   # the browser's own auth.html address
    user = _me()
    mem = _active_membership(user)
    household = mem.household

    if email:
        if not EMAIL_RE.match(email):
            return jsonify({"error": "That email address doesn't look right"}), 400
        existing = (User.query.join(Membership, Membership.user_id == User.id)
                    .filter(Membership.household_id == household.id, User.email == email).first())
        if existing:
            return jsonify({"error": f"{existing.name} is already in this household"}), 400
        # tidy: a new invite to the same address replaces the old open one
        Invite.query.filter_by(household_id=household.id, email=email, accepted_at=None, revoked=False)\
            .update({"revoked": True})

    inv = new_invite(household, user, email or None)
    db.session.commit()
    link = invite_link(inv.token, link_base)

    email_sent, email_error = False, None
    if email:
        email_sent, email_error = mailer.send_invite_email(email, user.name, household.name, link, household.invite_code)

    if email and email_sent:
        message = f"Invite emailed to {email}"
    elif email:
        message = f"{email_error}. Share the link yourself instead."
    else:
        message = "Invite link created"

    return jsonify({
        "ok": True, "message": message, "link": link, "code": household.invite_code,
        "email_sent": email_sent, "email_error": email_error,
        "invite": _invite_dict(inv, link_base), "email_configured": mailer.mail_configured(),
    }), 201


def _invite_dict(inv, link_base=None):
    return {
        "id": inv.id, "token": inv.token, "email": inv.email, "status": inv.status,
        "invited_by": inv.invited_by.name if inv.invited_by else None,
        "created_at": inv.created_at.isoformat() + "Z", "expires_at": inv.expires_at.isoformat() + "Z",
        "link": invite_link(inv.token, link_base),
    }


@bp.get("/invites")
@household_required
def list_invites():
    hid = session["household_id"]
    rows = Invite.query.filter_by(household_id=hid, accepted_at=None, revoked=False)\
        .order_by(Invite.created_at.desc()).all()
    return jsonify({
        "invites": [_invite_dict(i) for i in rows if i.status == "pending"],
        "email_configured": mailer.mail_configured(),
    })


@bp.delete("/invites/<int:invite_id>")
@household_required
def revoke_invite(invite_id):
    user = _me()
    mem = _active_membership(user)
    inv = Invite.query.filter_by(id=invite_id, household_id=mem.household_id).first()
    if not inv:
        return jsonify({"error": "Invite not found"}), 404
    if mem.role != "owner" and inv.invited_by_id != user.id:
        return jsonify({"error": "Only owners (or whoever sent it) can cancel an invite"}), 403
    inv.revoked = True
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/regenerate-code")
@household_required
def regenerate_code():
    """Owners: replace the reusable household code (e.g. if it leaked)."""
    mem = _active_membership(_me())
    if mem.role != "owner":
        return jsonify({"error": "Only owners can reset the household code"}), 403
    mem.household.invite_code = unique_code()
    db.session.commit()
    return jsonify({"code": mem.household.invite_code})


# ---------------------------------------------------------------- managing members (owners)

@bp.post("/members/<int:user_id>/role")
@household_required
def set_role(user_id):
    data = request.get_json(force=True) or {}
    role = data.get("role")
    if role not in ("owner", "member"):
        return jsonify({"error": "role must be 'owner' or 'member'"}), 400

    me = _active_membership(_me())
    if me.role != "owner":
        return jsonify({"error": "Only owners can change roles"}), 403
    target = get_membership(user_id, me.household_id)
    if not target:
        return jsonify({"error": "That person isn't in this household"}), 404
    if target.role == "owner" and role == "member":
        owners = Membership.query.filter_by(household_id=me.household_id, role="owner").count()
        if owners <= 1:
            return jsonify({"error": "A household needs at least one owner"}), 400
    target.role = role
    db.session.commit()
    return jsonify({"ok": True})


@bp.delete("/members/<int:user_id>")
@household_required
def remove_member(user_id):
    me = _active_membership(_me())
    if me.role != "owner":
        return jsonify({"error": "Only owners can remove people"}), 403
    if user_id == me.user_id:
        return jsonify({"error": "Use 'Leave household' to remove yourself"}), 400
    target = get_membership(user_id, me.household_id)
    if not target:
        return jsonify({"error": "That person isn't in this household"}), 404

    db.session.delete(target)
    db.session.flush()
    u = User.query.get(user_id)
    if u.household_id == me.household_id:
        nxt = Membership.query.filter_by(user_id=u.id).order_by(Membership.joined_at.asc()).first()
        u.household_id = nxt.household_id if nxt else None
    db.session.commit()
    return jsonify({"ok": True})
