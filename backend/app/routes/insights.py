from datetime import date, timedelta
from flask import Blueprint, request, jsonify, session
from app.extensions import db
from app.models import Item, PurchaseHistory
from app.services.risk_engine import score_item, household_consumption_rate, CATEGORY_SHELF_LIFE
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
        .order_by(Item.expiry_date.asc().nullslast())
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
    """
    Simulate buying a new item that expires in N days, and project the
    resulting risk level — mirrors the prototype's What-If Simulator
    (category chips + 'Expires in X days' slider + Simulate Purchase button).
    """
    data = request.get_json(force=True) or {}
    category = data.get("category", "other")
    expires_in_days = int(data.get("expires_in_days", 7))
    quantity = float(data.get("quantity", 1))

    class Fake:
        pass
    fake_item = Fake()
    fake_item.category = category
    fake_item.quantity = quantity
    fake_item.expiry_date = date.today() + timedelta(days=expires_in_days)
    fake_item.is_estimate = False

    rate = household_consumption_rate(db.session, session["household_id"], category)
    risk = score_item(fake_item, rate)

    # simple 7-day projected waste curve for the chart in the prototype
    projection = []
    for day in range(7):
        remaining_days = max(0, expires_in_days - day)
        projected_score = min(100, risk["score"] + day * 5) if remaining_days <= 2 else max(0, risk["score"] - day * 3)
        projection.append(projected_score)

    return jsonify({
        "risk_score": risk["score"],
        "risk_label": risk["label"],
        "projection": projection,
    })
