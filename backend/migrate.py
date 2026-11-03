"""One-off (safe to re-run): adds the multi-household tables to an existing database
and moves existing users into them. `python run.py` does this automatically too.

    cd backend && python migrate.py
"""
from app import create_app
from app.services.membership import ensure_schema

app = create_app()
with app.app_context():
    n = ensure_schema()
    print(f"Done. Tables are up to date. {n} existing user(s) migrated.")
