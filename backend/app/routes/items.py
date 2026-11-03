from datetime import datetime, date
from flask import Blueprint, request, jsonify, session
from app.extensions import db
from app.models import Item, ConsumptionLog, PurchaseHistory
from app.services.risk_engine import score_item, household_consumption_rate
from app.utils.decorators import household_required

bp = Blueprint("items", __name__, url_prefix="/api/items")


def _parse_date(s):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _serialize_with_risk(item):
    rate = household_consumption_rate(db.session, item.household_id, item.category)
    risk = score_item(item, rate)
    return item.to_dict(risk=risk)


@bp.get("")
@household_required
def list_items():
    household_id = session["household_id"]
    storage = request.args.get("storage")
    category = request.args.get("category")

    q = Item.query.filter_by(household_id=household_id)
    if storage:
        q = q.filter_by(storage=storage)
    if category:
        q = q.filter_by(category=category)

    items = q.all()
    serialized = [_serialize_with_risk(i) for i in items]
    serialized.sort(key=lambda d: d["risk_score"], reverse=True)
    return jsonify({"items": serialized})


@bp.post("")
@household_required
def create_item():
    data = request.get_json(force=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Item name is required"}), 400

    item = Item(
        household_id=session["household_id"],
        name=name,
        category=data.get("category", "other"),
        quantity=float(data.get("quantity", 1)),
        unit=data.get("unit", "unit"),
        storage=data.get("storage", "fridge"),
        purchase_date=_parse_date(data.get("purchase_date")) or date.today(),
        expiry_date=_parse_date(data.get("expiry_date")),
        is_estimate=bool(data.get("is_estimate", not data.get("expiry_date"))),
    )
    db.session.add(item)

    # Also log this as a purchase, feeding Purchase History + "Don't Buy Yet"
    db.session.add(PurchaseHistory(
        household_id=session["household_id"],
        item_name=item.name,
        category=item.category,
        purchase_date=item.purchase_date,
        quantity=item.quantity,
        unit=item.unit,
    ))

    db.session.commit()
    return jsonify({"item": _serialize_with_risk(item)}), 201


@bp.put("/<int:item_id>")
@household_required
def update_item(item_id):
    item = Item.query.filter_by(id=item_id, household_id=session["household_id"]).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json(force=True) or {}
    for field in ["name", "category", "unit", "storage"]:
        if field in data:
            setattr(item, field, data[field])
    if "quantity" in data:
        item.quantity = float(data["quantity"])
    if "expiry_date" in data:
        item.expiry_date = _parse_date(data["expiry_date"])
        item.is_estimate = not item.expiry_date
    if "purchase_date" in data:
        item.purchase_date = _parse_date(data["purchase_date"])

    db.session.commit()
    return jsonify({"item": _serialize_with_risk(item)})


@bp.delete("/<int:item_id>")
@household_required
def delete_item(item_id):
    item = Item.query.filter_by(id=item_id, household_id=session["household_id"]).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/<int:item_id>/consume")
@household_required
def consume_item(item_id):
    item = Item.query.filter_by(id=item_id, household_id=session["household_id"]).first()
    if not item:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json(force=True) or {}
    amount = float(data.get("quantity", item.quantity))
    amount = min(amount, item.quantity) if item.quantity else amount

    db.session.add(ConsumptionLog(item_id=item.id, quantity_used=amount))
    item.quantity = max(0, item.quantity - amount)

    fully_used = item.quantity <= 0
    if fully_used:
        db.session.delete(item)

    db.session.commit()
    return jsonify({"ok": True, "removed": fully_used})
