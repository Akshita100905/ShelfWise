from datetime import date, timedelta
from collections import defaultdict
from flask import Blueprint, jsonify, session
from app.extensions import db
from app.models import PurchaseHistory, Item
from app.utils.decorators import household_required

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")

MONTH_LABELS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]


@bp.get("")
@household_required
def analytics_overview():
    household_id = session["household_id"]

    purchases = PurchaseHistory.query.filter_by(household_id=household_id).all()
    total_items = Item.query.filter_by(household_id=household_id).count()

    # Waste % + money-ish estimate: purchases marked was_wasted / total purchases
    wasted = [p for p in purchases if p.was_wasted]
    waste_pct = round(100 * len(wasted) / len(purchases)) if purchases else 0
    avg_item_cost = 2.2  # placeholder unit economics, tune per household currency
    saved_this_period = round(len(wasted) * avg_item_cost, 2)

    # Food wasted (kg) per month, last 6 months, by weight-ish proxy (quantity)
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m = (today.month - i - 1) % 12
        months.append(MONTH_LABELS[m])

    monthly_waste = defaultdict(float)
    for p in wasted:
        label = MONTH_LABELS[(p.purchase_date.month - 1) % 12]
        monthly_waste[label] += p.quantity

    food_wasted_series = [round(monthly_waste.get(m, 0), 1) for m in months]

    # Waste by category
    cat_waste = defaultdict(float)
    for p in wasted:
        cat_waste[p.category] += p.quantity
    total_cat = sum(cat_waste.values()) or 1
    waste_by_category = [
        {"category": cat, "amount": round(v, 2), "pct": round(100 * v / total_cat)}
        for cat, v in sorted(cat_waste.items(), key=lambda x: -x[1])
    ]

    return jsonify({
        "waste_pct": waste_pct,
        "saved_this_period": saved_this_period,
        "items_tracked": total_items,
        "food_wasted": {"months": months, "kg": food_wasted_series},
        "monthly_savings": {"months": months, "amount": [round(saved_this_period * (i + 1) / 6, 2) for i in range(6)]},
        "waste_by_category": waste_by_category,
    })
