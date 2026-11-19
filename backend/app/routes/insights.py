from datetime import date, timedelta
from flask import Blueprint, request, jsonify, session
from app.extensions import db
from app.models import Item, PurchaseHistory
from app.services.risk_engine import (score_item, household_consumption_rate, CATEGORY_SHELF_LIFE,
                                      product_consumption_rate, calculate_simulated_risk, PRODUCT_SHELF_LIFE)
from app.utils.decorators import household_required

bp = Blueprint("insights", __name__, url_prefix="/api/insights")


@bp.get("/use-first")
@household_required
def use_first():
    household_id = session["household_id"]
    items = Item.query.filter_by(household_id=household_id).all()
    scored = []
    for item in items:
        rate = household_consumption_rate(db.session, household_id, item.category)
        risk = score_item(item, rate)
        scored.append(item.to_dict(risk=risk))
    scored.sort(key=lambda d: d["risk_score"], reverse=True)

    high_risk = [d for d in scored if d["risk_label"] == "High Risk"]
    return jsonify({"use_first": scored, "high_waste_risk": high_risk})


@bp.get("/dont-buy")
@household_required
def dont_buy_search():
    """
    Prototype: search bar + 'Check my supply' button -> shows whether the
    household already has enough of that item at home.
    """
    household_id = session["household_id"]
    query = (request.args.get("q") or "").strip().lower()
    if not query:
        return jsonify({"result": None})

    item = (
    Item.query.filter(Item.household_id == household_id)
    .filter(Item.name.ilike(f"%{query}%"))
    .order_by(
        Item.expiry_date.is_(None).asc(),
        Item.expiry_date.asc()
    )
    .first()
)
    if not item:
        return jsonify({"result": {
            "found": False,
            "message": f"No {query} currently in your inventory — safe to buy.",
        }})

    rate = household_consumption_rate(db.session, household_id, item.category)
    days_to_deplete = round(item.quantity / rate) if rate > 0 else CATEGORY_SHELF_LIFE.get(item.category, 7)
    depletion_date = date.today() + timedelta(days=days_to_deplete)

    recommendation = "Don't buy yet" if days_to_deplete >= 3 else "OK to buy soon"

    return jsonify({"result": {
        "found": True,
        "item": item.to_dict(),
        "estimated_depletion": depletion_date.isoformat(),
        "recommendation": recommendation,
        "note": f"Enough {item.name.lower()} to last ~{days_to_deplete} days at your current rate.",
    }})


@bp.get("/dont-buy/list")
@household_required
def dont_buy_list():
    """List view behind the 'Don't Buy Yet' tool, with category filter chips."""
    household_id = session["household_id"]
    category = request.args.get("category")

    items = Item.query.filter_by(household_id=household_id)
    if category and category != "all":
        items = items.filter_by(category=category)
    items = items.all()

    results = []
    for item in items:
        rate = household_consumption_rate(db.session, household_id, item.category)
        risk = score_item(item, rate)
        if risk["label"] != "High Risk":  # plenty of runway = don't buy more
            results.append(item.to_dict(risk=risk))
    return jsonify({"items": results})


@bp.post("/what-if")
@household_required
def what_if():
    """Simulate a hypothetical purchase without writing to inventory/history."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:150]
    category = str(data.get("category", "other")).strip().lower()
    storage = str(data.get("storage", "fridge")).strip().lower()
    unit = str(data.get("unit", "unit")).strip().lower()[:30]

    allowed_categories = {"produce", "dairy", "meat", "bakery", "grains", "other"}
    allowed_storage = {"fridge", "freezer", "pantry", "counter"}
    allowed_units = {"unit", "g", "kg", "ml", "litre", "pack", "bag", "loaf", "pots", "tub", "pieces"}
    if not name:
        return jsonify({"error": "Please enter a product name."}), 400
    if category not in allowed_categories:
        return jsonify({"error": "Please select a valid category."}), 400
    if storage not in allowed_storage:
        return jsonify({"error": "Please select a valid storage location."}), 400
    if unit not in allowed_units:
        return jsonify({"error": "Please select a valid unit."}), 400

    try:
        quantity = float(data.get("quantity", 1))
        expires_in_days = int(data.get("expires_in_days", 7))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity and expiry must be valid numbers."}), 400
    if not (0 < quantity <= 100000):
        return jsonify({"error": "Quantity must be greater than 0."}), 400
    if not (0 <= expires_in_days <= 3650):
        return jsonify({"error": "Expiry must be between 0 and 3650 days."}), 400

    household_id = session["household_id"]
    rate, history_source = product_consumption_rate(
        db.session, household_id, name, category, unit
    )

    # Purchase history is used only when the same product has prior purchases.
    purchases = (PurchaseHistory.query
                 .filter_by(household_id=household_id, category=category)
                 .filter(PurchaseHistory.item_name.ilike(name), PurchaseHistory.unit == unit)
                 .all())
    total_purchased = sum(float(row.quantity or 0) for row in purchases)
    total_wasted = sum(float(row.wasted_quantity or (row.quantity if row.was_wasted else 0)) for row in purchases)
    historical_waste_rate = min(1.0, total_wasted / total_purchased) if total_purchased > 0 else 0.0

    risk = calculate_simulated_risk(
        category, quantity, expires_in_days, rate, storage, historical_waste_rate, name
    )

    projection = []
    for day in range(7):
        remaining_days = max(0, expires_in_days - day)
        remaining_quantity = max(0, quantity - (rate * day if rate > 0 else 0))
        if remaining_days == 0:
            projected = min(100, risk["score"] + 12)
        elif rate > 0:
            projected = min(100, max(0, risk["score"] + (remaining_quantity / max(quantity, 0.01)) * 8 - day * 2))
        else:
            projected = min(100, max(0, risk["score"] + day * 2))
        projection.append(int(projected))

    return jsonify({
        "product_name": name, "category": category, "storage": storage,
        "quantity": quantity, "unit": unit, "expires_in_days": expires_in_days,
        "risk_score": risk["score"], "risk_label": risk["label"],
        "projection": projection, "estimated_consumed": risk["estimated_consumed"],
        "estimated_remaining": risk["estimated_remaining"],
        "days_to_finish": risk["days_to_finish"],
        "history_source": history_source,
        "historical_waste_rate": round(historical_waste_rate * 100, 1),
        "components": risk["components"],
        "note": ("Based on your product's consumption history." if history_source == "product history"
                 else "Using category-level consumption because product-specific history is unavailable."
                 if history_source == "category history" else "No matching consumption history yet; estimate is based on expiry, quantity and storage."),
    })
