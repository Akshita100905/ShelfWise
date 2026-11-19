"""Add clearly tagged, realistic demo purchase history to one household.

Usage:
    python seed_demo_analytics.py --household-id 1
    python seed_demo_analytics.py --household-id 1 --reset-demo

This script never deletes real purchases. It creates purchase-history activity
for the previous six months, with plausible Indian retail prices and partial
waste events. It does not create fake users or change login credentials.
"""
import argparse
from datetime import date, timedelta

from app import create_app
from app.extensions import db
from app.models import Household, PurchaseHistory

# (name, category, quantity, unit, ₹ per unit, waste fraction, days ago)
ROWS = [
    ("Milk", "dairy", 2, "litre", 64, 0.25, 8),
    ("Curd", "dairy", 1, "kg", 90, 0.15, 12),
    ("Paneer", "dairy", 0.2, "kg", 360, 0.50, 17),
    ("Spinach", "produce", 0.25, "kg", 80, 0.40, 5),
    ("Tomatoes", "produce", 1, "kg", 40, 0.20, 10),
    ("Bananas", "produce", 1, "kg", 55, 0.10, 14),
    ("Apples", "produce", 0.5, "kg", 160, 0.0, 19),
    ("Bread", "bakery", 0.4, "kg", 100, 0.50, 21),
    ("Rice", "grains", 2, "kg", 62, 0.0, 25),
    ("Wheat Flour", "grains", 2, "kg", 42, 0.0, 28),
    ("Chicken", "meat", 0.5, "kg", 280, 0.20, 31),
    ("Capsicum", "produce", 0.5, "kg", 70, 0.30, 34),
    ("Milk", "dairy", 2, "litre", 64, 0.0, 39),
    ("Curd", "dairy", 0.5, "kg", 90, 0.20, 43),
    ("Potatoes", "produce", 2, "kg", 30, 0.0, 46),
    ("Onions", "produce", 1, "kg", 35, 0.0, 49),
    ("Bread", "bakery", 0.4, "kg", 100, 0.25, 53),
    ("Paneer", "dairy", 0.2, "kg", 360, 0.0, 56),
    ("Milk", "dairy", 2, "litre", 64, 0.15, 62),
    ("Tomatoes", "produce", 1, "kg", 45, 0.35, 66),
    ("Cucumber", "produce", 0.5, "kg", 40, 0.20, 69),
    ("Rice", "grains", 2, "kg", 62, 0.0, 73),
    ("Yogurt", "dairy", 0.4, "kg", 150, 0.25, 77),
    ("Bread", "bakery", 0.4, "kg", 100, 0.50, 81),
    ("Milk", "dairy", 2, "litre", 60, 0.25, 91),
    ("Spinach", "produce", 0.25, "kg", 70, 0.50, 95),
    ("Carrots", "produce", 1, "kg", 45, 0.10, 99),
    ("Eggplant", "produce", 0.5, "kg", 50, 0.0, 103),
    ("Wheat Flour", "grains", 2, "kg", 40, 0.0, 108),
    ("Chicken", "meat", 0.5, "kg", 260, 0.40, 112),
    ("Curd", "dairy", 0.5, "kg", 85, 0.0, 119),
    ("Bananas", "produce", 1, "kg", 50, 0.30, 124),
    ("Tomatoes", "produce", 1, "kg", 38, 0.20, 132),
    ("Milk", "dairy", 2, "litre", 60, 0.10, 139),
    ("Bread", "bakery", 0.4, "kg", 95, 0.50, 145),
    ("Potatoes", "produce", 2, "kg", 28, 0.0, 151),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--household-id", type=int, required=True)
    parser.add_argument("--reset-demo", action="store_true", help="replace only this household's prior demo rows")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        household = db.session.get(Household, args.household_id)
        if not household:
            raise SystemExit(f"Household {args.household_id} does not exist")

        existing = PurchaseHistory.query.filter_by(household_id=household.id, is_demo=True).count()
        if existing and not args.reset_demo:
            raise SystemExit(f"This household already has {existing} demo rows. Use --reset-demo to replace them.")
        if args.reset_demo:
            PurchaseHistory.query.filter_by(household_id=household.id, is_demo=True).delete(synchronize_session=False)

        today = date.today()
        for name, category, qty, unit, price, waste_fraction, days_ago in ROWS:
            wasted = round(qty * waste_fraction, 3)
            db.session.add(PurchaseHistory(
                household_id=household.id,
                item_name=name,
                category=category,
                purchase_date=today - timedelta(days=days_ago),
                quantity=qty,
                unit=unit,
                was_wasted=(wasted >= qty and qty > 0),
                price_per_unit=price,
                wasted_quantity=wasted,
                is_demo=True,
            ))
        db.session.commit()
        print(f"Added {len(ROWS)} demo purchase records to household {household.id} ({household.name}).")
        print("All rows are tagged is_demo=True. Remove them with DELETE /api/analytics/demo-data or rerun with --reset-demo.")


if __name__ == "__main__":
    main()
