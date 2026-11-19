from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, jsonify, request, session
from app.extensions import db
from app.models import Item, PurchaseHistory
from app.utils.decorators import household_required

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")

# Convert only units with a defensible mass/volume conversion. We deliberately
# do not pretend that pieces, packets, bags, etc. are kilograms.
KG_FACTORS = {
    "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
    "g": 0.001, "gram": 0.001, "grams": 0.001,
    "mg": 0.000001,
}


def _wasted_quantity(purchase):
    """Support old rows whose only waste field was the boolean was_wasted."""
    qty = purchase.wasted_quantity or 0
    if qty <= 0 and purchase.was_wasted:
        return purchase.quantity or 0
    return min(qty, purchase.quantity or qty)


def _month_keys(today, count=6):
    keys = []
    year, month = today.year, today.month
    for _ in range(count):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return list(reversed(keys))


def _month_label(year, month):
    return date(year, month, 1).strftime("%b %Y")


@bp.get("")
@household_required
def analytics_overview():
    household_id = session["household_id"]
    today = date.today()
    month_keys = _month_keys(today, 6)
    month_labels = [_month_label(y, m) for y, m in month_keys]
    start_date = date(month_keys[0][0], month_keys[0][1], 1)

    purchases = (PurchaseHistory.query
                 .filter_by(household_id=household_id)
                 .filter(PurchaseHistory.purchase_date >= start_date)
                 .order_by(PurchaseHistory.purchase_date.asc()).all())
    total_items = Item.query.filter_by(household_id=household_id).count()

    # Purchase-based waste rate: quantity-weighted, not record-count weighted.
    wasted_qty_total = sum(_wasted_quantity(p) for p in purchases)
    purchases_with_waste = sum(1 for p in purchases if _wasted_quantity(p) > 0)
    # Quantities may be kg, litres, packs, etc.; a record-based rate avoids
    # adding unlike units together and presenting a misleading percentage.
    waste_pct = round(100 * purchases_with_waste / len(purchases), 1) if purchases else 0

    monthly_waste_kg = defaultdict(float)
    monthly_waste_cost = defaultdict(float)
    category_waste_kg = defaultdict(float)
    category_waste_cost = defaultdict(float)
    unconverted_waste = 0.0
    total_waste_cost = 0.0

    for p in purchases:
        wasted_qty = _wasted_quantity(p)
        if wasted_qty <= 0:
            continue
        key = (p.purchase_date.year, p.purchase_date.month)
        unit_key = (p.unit or "").strip().lower()
        factor = KG_FACTORS.get(unit_key)
        if factor is not None:
            kg = wasted_qty * factor
            monthly_waste_kg[key] += kg
            category_waste_kg[p.category or "other"] += kg
        else:
            unconverted_waste += wasted_qty

        cost = (wasted_qty * p.price_per_unit) if p.price_per_unit is not None else None
        if cost is not None:
            monthly_waste_cost[key] += cost
            category_waste_cost[p.category or "other"] += cost
            total_waste_cost += cost

    food_wasted_series = [round(monthly_waste_kg[k], 3) for k in month_keys]
    monthly_cost_series = [round(monthly_waste_cost[k], 2) for k in month_keys]
    total_kg = sum(monthly_waste_kg.values())
    waste_by_category = [
        {"category": cat, "amount": round(amount, 3),
         "pct": round(100 * amount / total_kg) if total_kg else 0, "unit": "kg"}
        for cat, amount in sorted(category_waste_kg.items(), key=lambda x: -x[1])
    ]

    priced_waste_qty = sum(
        _wasted_quantity(p) for p in purchases if p.price_per_unit is not None
    )
    unpriced_waste_qty = wasted_qty_total - priced_waste_qty

    return jsonify({
        "period": {"start": start_date.isoformat(), "end": today.isoformat()},
        "waste_pct": waste_pct,
        "saved_this_period": round(total_waste_cost, 2),  # kept for backwards compatibility
        "money_lost_to_waste": round(total_waste_cost, 2),
        "items_tracked": total_items,
        "purchases_count": len(purchases),
        "purchases_with_waste": purchases_with_waste,
        "wasted_quantity": round(wasted_qty_total, 3),
        "unconverted_waste_quantity": round(unconverted_waste, 3),
        "unpriced_waste_quantity": round(max(unpriced_waste_qty, 0), 3),
        "food_wasted": {"months": month_labels, "kg": food_wasted_series},
        "monthly_savings": {"months": month_labels, "amount": monthly_cost_series},
        "waste_by_category": waste_by_category,
    })


@bp.get("/purchases")
@household_required
def recent_purchases():
    rows = (PurchaseHistory.query
            .filter_by(household_id=session["household_id"])
            .order_by(PurchaseHistory.purchase_date.desc(), PurchaseHistory.id.desc())
            .limit(30).all())
    return jsonify({"purchases": [p.to_dict() for p in rows]})


@bp.post("/purchases/<int:purchase_id>/waste")
@household_required
def record_waste(purchase_id):
    purchase = PurchaseHistory.query.filter_by(
        id=purchase_id, household_id=session["household_id"]
    ).first()
    if not purchase:
        return jsonify({"error": "Purchase record not found"}), 404

    data = request.get_json(silent=True) or {}
    try:
        quantity = float(data.get("quantity", purchase.quantity or 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Waste quantity must be a number"}), 400
    if quantity <= 0 or quantity > (purchase.quantity or 0):
        return jsonify({"error": "Waste quantity must be greater than zero and no more than the purchased quantity"}), 400

    purchase.wasted_quantity = min(
        (purchase.wasted_quantity or 0) + quantity, purchase.quantity or quantity
    )
    purchase.was_wasted = purchase.wasted_quantity >= (purchase.quantity or 0)
    db.session.commit()
    return jsonify({"ok": True, "purchase": purchase.to_dict()})


@bp.delete("/demo-data")
@household_required
def remove_demo_data():
    """Remove only rows explicitly tagged as demo; never touches real records."""
    deleted = (PurchaseHistory.query
               .filter_by(household_id=session["household_id"], is_demo=True)
               .delete(synchronize_session=False))
    db.session.commit()
    return jsonify({"ok": True, "deleted_demo_purchases": deleted})
