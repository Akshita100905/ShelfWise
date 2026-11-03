from flask import Blueprint, request, jsonify, session
from app.extensions import db
from app.models import ShoppingListItem
from app.utils.decorators import household_required

bp = Blueprint("shopping", __name__, url_prefix="/api/shopping-list")


@bp.get("")
@household_required
def list_shopping():
    items = ShoppingListItem.query.filter_by(household_id=session["household_id"]).order_by(
        ShoppingListItem.is_purchased.asc(), ShoppingListItem.created_at.desc()
    ).all()
    return jsonify({"items": [i.to_dict() for i in items]})


@bp.post("")
@household_required
def add_shopping_item():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Item name is required"}), 400

    item = ShoppingListItem(
        household_id=session["household_id"],
        name=name,
        added_by_id=session["user_id"],
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"item": item.to_dict()}), 201


@bp.put("/<int:item_id>")
@household_required
def toggle_shopping_item(item_id):
    item = ShoppingListItem.query.filter_by(id=item_id, household_id=session["household_id"]).first()
    if not item:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json(force=True) or {}
    if "is_purchased" in data:
        item.is_purchased = bool(data["is_purchased"])
    db.session.commit()
    return jsonify({"item": item.to_dict()})


@bp.delete("/<int:item_id>")
@household_required
def delete_shopping_item(item_id):
    item = ShoppingListItem.query.filter_by(id=item_id, household_id=session["household_id"]).first()
    if not item:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})
