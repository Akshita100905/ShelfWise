from app import create_app
from app.extensions import db
from app.services.membership import ensure_schema

app = create_app()

# Creates the household_members / invites tables if they don't exist yet and gives
# existing users a membership for the household they were already in. Idempotent.
with app.app_context():
    try:
        n = ensure_schema()
        if n:
            print(f"Migrated {n} existing user(s) into the new household_members table.")
    except Exception as e:  # e.g. database unreachable: the API will report it per request
        print(f"WARNING: couldn't verify the database schema: {e}")

if __name__ == "__main__":
    import os
    # Set FLASK_HOST=0.0.0.0 to let other devices on your Wi-Fi reach the API
    # (needed if you want a friend on the same network to open an invite link).
    app.run(debug=True, host=os.getenv("FLASK_HOST", "127.0.0.1"), port=5000)
