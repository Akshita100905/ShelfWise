from flask import Blueprint, request, jsonify, session
from app.extensions import db, bcrypt
from app.models import User
from app.utils.decorators import login_required

bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@bp.put("/preferences")
@login_required
def update_preferences():
    user = User.query.get(session["user_id"])
    data = request.get_json(force=True) or {}

    for field in ["theme", "language"]:
        if field in data:
            setattr(user, field, data[field])
    for field in ["notify_expiry", "notify_board", "notify_ai_tips"]:
        if field in data:
            setattr(user, field, bool(data[field]))

    db.session.commit()
    return jsonify({"user": user.to_dict()})


@bp.put("/password")
@login_required
def change_password():
    user = User.query.get(session["user_id"])
    data = request.get_json(force=True) or {}
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not bcrypt.check_password_hash(user.password_hash, current_pw):
        return jsonify({"error": "Current password is incorrect"}), 400
    if len(new_pw) < 6:
        return jsonify({"error": "New password must be at least 6 characters"}), 400

    user.password_hash = bcrypt.generate_password_hash(new_pw).decode("utf-8")
    db.session.commit()
    return jsonify({"ok": True})
