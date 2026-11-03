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
