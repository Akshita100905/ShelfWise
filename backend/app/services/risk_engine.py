"""
ShelfWise Waste Risk Score engine.

Produces a 0-100 score per item (higher = more likely to be wasted),
combining:
  - Expiry proximity (heaviest weight — matches the prototype's "days left"-driven UI)
  - Quantity on hand relative to typical household use
  - Consumption pace (are they actually eating through this category?)
  - "Estimate / limited data" penalty for items with no expiry date on file

Buckets (mirrors the prototype's badge colors):
  score >= 65  -> "High Risk"    (red ring)
  score >= 40  -> "Expiring Soon" (amber ring)
  else         -> "Safe"         (green ring)
"""
from datetime import date

HIGH_RISK_THRESHOLD = 65
SOON_THRESHOLD = 40

# Typical shelf life per category, in days — used when an item has no expiry
# date set, and as a normalizer for "days left".
CATEGORY_SHELF_LIFE = {
    "produce": 7,
    "dairy": 10,
    "meat": 4,
    "bakery": 6,
    "grains": 180,
    "other": 21,
}


def score_item(item, consumption_rate_per_day: float = 0.0) -> dict:
    """
    item: models.Item instance
    consumption_rate_per_day: average units/day the household gets through
                               this item's category (0 if unknown)
    """
    shelf_life = CATEGORY_SHELF_LIFE.get(item.category, 21)

    if item.expiry_date:
        days_left = (item.expiry_date - date.today()).days
    else:
        days_left = shelf_life // 2  # unknown expiry -> assume midlife

    # 1. Expiry proximity component (0-70 points): closer to/ past expiry -> higher
    if days_left <= 0:
        expiry_component = 70
    else:
        ratio = max(0.0, 1 - (days_left / shelf_life))
        expiry_component = round(ratio * 70)

    # 2. Quantity pressure (0-20 points): a lot left vs. how fast it's consumed
    if consumption_rate_per_day > 0 and days_left > 0:
        days_to_finish = item.quantity / consumption_rate_per_day
        quantity_component = 20 if days_to_finish > days_left else round(
            20 * min(1, days_to_finish / max(days_left, 1))
        )
    else:
        # No consumption data: mild pressure if quantity is large
        quantity_component = min(20, round(item.quantity))

    # 3. Data-confidence penalty (0-10 points) for items with no real expiry date
    estimate_component = 10 if item.is_estimate or not item.expiry_date else 0

    score = int(min(100, expiry_component + quantity_component + estimate_component))

    if score >= HIGH_RISK_THRESHOLD:
        label = "High Risk"
    elif score >= SOON_THRESHOLD:
        label = "Expiring Soon"
    else:
        label = "Safe"

    return {"score": score, "label": label, "days_left": days_left}


def household_consumption_rate(db_session, household_id, category):
    """
    Rough average units/day consumed for a category, from consumption_log,
    over the last 30 days. Returns 0 if there's not enough data.
    """
    from app.models import ConsumptionLog, Item
    from datetime import timedelta

    cutoff = date.today() - timedelta(days=30)
    rows = (
        db_session.query(ConsumptionLog)
        .join(Item, ConsumptionLog.item_id == Item.id)
        .filter(Item.household_id == household_id, Item.category == category)
        .filter(ConsumptionLog.used_at >= cutoff)
        .all()
    )
    if not rows:
        return 0.0
    total_used = sum(r.quantity_used for r in rows)
    return total_used / 30.0


# Product-specific defaults used only by the What-If simulator. These are
# broad planning estimates, not food-safety guarantees; the user-provided
# expiry date remains the source of truth for the simulation.
PRODUCT_SHELF_LIFE = {
    "tomato": 7, "tomatoes": 7, "spinach": 4, "lettuce": 5,
    "apple": 21, "apples": 21, "banana": 5, "bananas": 5,
    "potato": 30, "potatoes": 30, "onion": 30, "onions": 30,
    "cucumber": 7, "carrot": 21, "carrots": 21,
    "milk": 7, "curd": 7, "yogurt": 10, "paneer": 5,
    "butter": 30, "cheese": 30, "bread": 5,
    "chicken": 2, "fish": 2, "mutton": 3,
    "rice": 365, "flour": 180, "atta": 90, "dal": 180,
}


def product_consumption_rate(db_session, household_id, product_name, category, unit):
    """Return (units/day, source) using same-unit data to avoid mixing kg and pieces."""
    from app.models import ConsumptionLog, Item
    from datetime import timedelta

    cutoff = date.today() - timedelta(days=30)
    base = (db_session.query(ConsumptionLog)
            .join(Item, ConsumptionLog.item_id == Item.id)
            .filter(Item.household_id == household_id, Item.unit == unit)
            .filter(ConsumptionLog.used_at >= cutoff))

    exact_rows = base.filter(Item.name.ilike(product_name.strip())).all()
    if exact_rows:
        return sum(r.quantity_used for r in exact_rows) / 30.0, "product history"

    category_rows = base.filter(Item.category == category).all()
    if category_rows:
        return sum(r.quantity_used for r in category_rows) / 30.0, "category history"

    return 0.0, "no consumption history"


def calculate_simulated_risk(category, quantity, expires_in_days, consumption_rate, storage, historical_waste_rate=0.0, product_name=""):
    """Explainable 0-100 simulation score; does not create or modify inventory."""
    shelf_life = PRODUCT_SHELF_LIFE.get(product_name.strip().lower(), CATEGORY_SHELF_LIFE.get(category, 21))
    days_left = max(0, int(expires_in_days))

    # Expiry contributes up to 55 points. A longer-life item is normalized
    # against its category's typical shelf-life window.
    expiry_component = 55 if days_left == 0 else round(55 * max(0, 1 - days_left / shelf_life))

    if consumption_rate > 0 and days_left > 0:
        days_to_finish = quantity / consumption_rate
        quantity_component = 25 if days_to_finish > days_left else round(25 * min(1, days_to_finish / days_left))
        estimated_consumed = min(quantity, consumption_rate * days_left)
    else:
        days_to_finish = None
        quantity_component = min(25, round(quantity * 2))
        estimated_consumed = None

    # A conservative storage mismatch adjustment, not a shelf-life prediction.
    storage_mismatch = (category in ("dairy", "meat") and storage in ("pantry", "counter"))
    storage_component = 8 if storage_mismatch else 0
    history_component = round(12 * max(0.0, min(1.0, historical_waste_rate)))

    score = min(100, int(expiry_component + quantity_component + storage_component + history_component))
    label = "High Risk" if score >= HIGH_RISK_THRESHOLD else "Expiring Soon" if score >= SOON_THRESHOLD else "Safe"
    return {
        "score": score, "label": label, "days_left": days_left,
        "estimated_consumed": round(estimated_consumed, 2) if estimated_consumed is not None else None,
        "estimated_remaining": round(max(0, quantity - estimated_consumed), 2) if estimated_consumed is not None else None,
        "days_to_finish": round(days_to_finish, 1) if days_to_finish is not None else None,
        "components": {"expiry": expiry_component, "quantity": quantity_component,
                       "storage": storage_component, "purchase_history": history_component},
    }

