from flask import Blueprint, request, jsonify, session
from app.extensions import db, bcrypt
from app.models import User, Household, now

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


from app.services.membership import (
    unique_code, add_member, activate, resolve_active, resolve_invite, user_payload, get_membership,
)

@bp.post("/register")
def register():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    household_name = (data.get("household_name") or "").strip()
    invite_value = data.get("invite_token") or data.get("invite_code") or ""
    invite_value = str(invite_value).strip()

    if not name or not email or len(password) < 6:
        return jsonify({"error": "Name, valid email, and a password (6+ chars) are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    # Validate the invite BEFORE creating anything, so a bad code never leaves a half-made account.
    household, invite, err = (None, None, None)
    if invite_value:
        household, invite, err = resolve_invite(invite_value)
        if err:
            return jsonify({"error": err}), 400

    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(name=name, email=email, password_hash=pw_hash)
    db.session.add(user)
    db.session.flush()

    role = "member"
    if household:
        add_member(user, household, "member")
        if invite:
            invite.accepted_by_id = user.id
            invite.accepted_at = now()
    elif household_name:
        household = Household(name=household_name, invite_code=unique_code())
        db.session.add(household)
        db.session.flush()
        add_member(user, household, "owner")
        role = "owner"

    if household:
        user.household_id = household.id
        user.role = role
    db.session.commit()

    session["user_id"] = user.id
    activate(user, user.household_id)
    return jsonify({"user": user_payload(user)}), 201


@bp.post("/login")
def login():
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"] = user.id
    resolve_active(user)
    return jsonify({"user": user_payload(user)})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@bp.get("/me")
def me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None})
    user = User.query.get(user_id)
    if not user:
        session.clear()
        return jsonify({"user": None})
    resolve_active(user)
    return jsonify({"user": user_payload(user)})
