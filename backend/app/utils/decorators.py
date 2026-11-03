from functools import wraps
from flask import session, jsonify


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return wrapper


def household_required(f):
    """Must be logged in AND currently an actual member of the active household.
    Membership is re-checked on every request, so leaving or being removed from
    a household takes effect immediately."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        hid = session.get("household_id")
        if not hid:
            return jsonify({"error": "No household selected"}), 400

        from app.models import User
        from app.services.membership import get_membership, heal_legacy
        user = User.query.get(session["user_id"])
        if user is None:
            session.clear()
            return jsonify({"error": "Not authenticated"}), 401
        if user.household_id == hid:
            heal_legacy(user)   # pre-migration accounts get their membership row on first use
        if not get_membership(user.id, hid):
            session.pop("household_id", None)
            return jsonify({"error": "You're no longer a member of this household"}), 403
        return f(*args, **kwargs)
    return wrapper
