"""
Creates the database (if missing and permitted) and all tables, then inserts
a sample household so the frontend has something to show immediately.

Works against local MySQL or a hosted MySQL (set DATABASE_URL in .env instead
of the individual DB_* fields — see .env.example).

Usage:
    cd backend
    pip install -r requirements.txt   # if you haven't already
    python seed.py
"""
import pymysql
from datetime import date, timedelta
from app import create_app
from app.extensions import db, bcrypt
from app.models import Membership, Household, User, Item, PurchaseHistory, ShoppingListItem, BoardNote
from app.config import Config


def ensure_database_exists():
    """
    Only relevant when connecting via the separate DB_* fields to a server
    where your user is allowed to CREATE DATABASE (typical for local MySQL).
    Hosted/managed MySQL usually gives you a database that already exists
    and a user without CREATE DATABASE rights — in that case this step is
    skipped automatically, which is fine.
    """
    if Config.DATABASE_URL:
        print("Using DATABASE_URL — assuming the database already exists on your host.")
        return
    try:
        connect_kwargs = {
            "host": Config.DB_HOST,
            "port": int(Config.DB_PORT),
            "user": Config.DB_USER,
            "password": Config.DB_PASSWORD,
        }
        if Config.DB_SSL:
            connect_kwargs["ssl"] = {"ca": Config.DB_SSL_CA} if Config.DB_SSL_CA else {}
        conn = pymysql.connect(**connect_kwargs)
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4")
            conn.commit()
        finally:
            conn.close()
    except pymysql.err.OperationalError as e:
        print(f"Note: couldn't auto-create the database ({e}). "
              f"If it already exists on your host, this is safe to ignore.")


def seed():
    ensure_database_exists()
    app = create_app()
    with app.app_context():
        db.create_all()

        if Household.query.first():
            print("Database already seeded — skipping.")
            return

        household = Household(name="The Chen-Ferreiras", invite_code="CHENFR1")
        db.session.add(household)
        db.session.flush()

        mia = User(
            household_id=household.id,
            name="Mia Chen",
            email="mia@example.com",
            password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
            role="owner",
        )
        luca = User(
            household_id=household.id,
            name="Luca Ferreira",
            email="luca@example.com",
            password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
            role="member",
        )
        db.session.add_all([mia, luca])
        db.session.flush()
        db.session.add_all([
            Membership(user_id=mia.id, household_id=household.id, role="owner"),
            Membership(user_id=luca.id, household_id=household.id, role="member"),
        ])
        db.session.flush()

        today = date.today()
        sample_items = [
            ("Whole Milk", "dairy", 0.4, "litre", "fridge", 2),
            ("Spinach", "produce", 1, "bag", "fridge", 1),
            ("Blueberries", "produce", 1, "punnet", "fridge", 3),
            ("Chicken Breast", "meat", 2, "pieces", "fridge", 3),
            ("Greek Yogurt", "dairy", 3, "pots", "fridge", 4),
            ("Cherry Tomatoes", "produce", 1, "pack", "fridge", 4),
            ("Hummus", "other", 1, "tub", "fridge", 6),
            ("Sourdough Bread", "bakery", 0.5, "loaf", "counter", 5),
            ("Orange Juice", "other", 1.2, "litre", "fridge", 7),
            ("Cheddar Cheese", "dairy", 200, "g", "fridge", 16),
            ("Frozen Peas", "other", 500, "g", "freezer", 164),
            ("Pasta", "grains", 500, "g", "pantry", 309),
        ]
        for name, cat, qty, unit, storage, days in sample_items:
            db.session.add(Item(
                household_id=household.id, name=name, category=cat,
                quantity=qty, unit=unit, storage=storage,
                purchase_date=today - timedelta(days=2),
                expiry_date=today + timedelta(days=days),
                is_estimate=False,
            ))
            db.session.add(PurchaseHistory(
                household_id=household.id, item_name=name, category=cat,
                purchase_date=today - timedelta(days=2), quantity=qty, unit=unit,
                was_wasted=(days <= 1),
            ))

        db.session.add(ShoppingListItem(household_id=household.id, name="Eggs", added_by_id=mia.id))
        db.session.add(ShoppingListItem(household_id=household.id, name="Bananas", added_by_id=luca.id))

        db.session.add(BoardNote(household_id=household.id, text="Oat milk", color="yellow", posted_by_id=mia.id))
        db.session.add(BoardNote(household_id=household.id, text="Olive oil", color="blue", posted_by_id=mia.id))

        db.session.commit()
        print("Seeded database with household 'The Chen-Ferreiras'.")
        print("Login with: mia@example.com / password123")


if __name__ == "__main__":
    seed()
