"""Actions ShelfWise AI can perform for the signed-in user's ACTIVE household.

Gemini's automatic function calling reads each function's signature and docstring
to decide when to call it, so the docstrings below are written for the model.

Safety by design:
  * every query/insert is scoped to `household_id` (taken from the session, never
    from the model),
  * the tools only READ or ADD data, nothing here can delete or edit,
  * calls are idempotent within one request: if a request is retried (e.g. after a
    temporary Gemini overload) the same call returns its first result instead of
    adding the item twice.
"""
import json
import random
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    Item, PurchaseHistory, ShoppingListItem, BoardNote, BOARD_COLORS, STORAGE_LOCATIONS,
)
from app.services.risk_engine import score_item, household_consumption_rate

CATEGORIES = ["produce", "dairy", "meat", "bakery", "grains", "other"]
MAX_ROWS = 60


def build_tools(household_id, user_id):
    """Returns (tools, actions). `tools` is the list of callables to hand to Gemini;
    `actions` fills up with a record of every change made, for the UI to show."""
    actions = []
    cache = {}

    def once(name, args, fn):
        key = (name, json.dumps(args, sort_keys=True, default=str))
        if key not in cache:
            cache[key] = fn()
        return cache[key]

    # ------------------------------------------------------------------ reading

    def get_inventory(category: str = "", expiring_within_days: int = -1) -> dict:
        """Read the household's current inventory (what food is in the kitchen).
        Use this to answer what is in the fridge/pantry, what is expiring, or to
        pick ingredients for a recipe.

        Args:
            category: Optional filter: produce, dairy, meat, bakery, grains or other.
                Leave empty for everything.
            expiring_within_days: Optional. If 0 or more, only return items that expire
                within that many days (0 = today or already expired). -1 means no filter.
        """
        q = Item.query.filter_by(household_id=household_id)
        cat = (category or "").strip().lower()
        if cat:
            q = q.filter_by(category=cat)
        rows = []
        for item in q.all():
            rate = household_consumption_rate(db.session, household_id, item.category)
            risk = score_item(item, rate)
            days_left = (item.expiry_date - date.today()).days if item.expiry_date else None
            if expiring_within_days >= 0 and (days_left is None or days_left > expiring_within_days):
                continue
            rows.append({
                "name": item.name, "category": item.category,
                "quantity": item.quantity, "unit": item.unit, "storage": item.storage,
                "expires": item.expiry_date.isoformat() if item.expiry_date else "unknown",
                "days_left": days_left, "waste_risk": risk["label"], "_score": risk["score"],
            })
        rows.sort(key=lambda r: r["_score"], reverse=True)
        for r in rows:
            r.pop("_score")
        return {"count": len(rows), "items": rows[:MAX_ROWS]}

    def get_shopping_list() -> dict:
        """Read the household's shopping list (items still to buy)."""
        rows = ShoppingListItem.query.filter_by(household_id=household_id, is_purchased=False) \
            .order_by(ShoppingListItem.created_at.desc()).limit(MAX_ROWS).all()
        return {"count": len(rows), "items": [r.name for r in rows]}

    def get_board_notes() -> dict:
        """Read the sticky notes currently on the household's grocery board
        (things people have asked others to buy)."""
        rows = BoardNote.query.filter_by(household_id=household_id, is_bought=False) \
            .order_by(BoardNote.created_at.desc()).limit(MAX_ROWS).all()
        return {"count": len(rows), "notes": [{"text": n.text, "posted_by": n.posted_by.name if n.posted_by else "Someone"} for n in rows]}

    # ------------------------------------------------------------------ writing

    def add_to_shopping_list(item_name: str) -> dict:
        """Add ONE item to the shopping list (things to buy). Use when the user says
        'add X to my list / shopping list' or 'we need X'. Call once per item.

        Args:
            item_name: The thing to buy, e.g. 'oat milk'.
        """
        def run():
            name = (item_name or "").strip()[:150]
            if not name:
                return {"ok": False, "message": "No item name given"}
            dup = ShoppingListItem.query.filter(
                ShoppingListItem.household_id == household_id,
                ShoppingListItem.is_purchased.is_(False),
                db.func.lower(ShoppingListItem.name) == name.lower()).first()
            if dup:
                return {"ok": True, "message": f"'{dup.name}' is already on the shopping list", "already_there": True}
            db.session.add(ShoppingListItem(household_id=household_id, name=name, added_by_id=user_id))
            db.session.commit()
            actions.append({"type": "shopping_added", "text": f"Added {name} to the shopping list"})
            return {"ok": True, "message": f"Added '{name}' to the shopping list"}
        return once("shop", {"n": item_name}, run)

    def add_board_note(text: str) -> dict:
        """Post a sticky note on the household's shared grocery board so other members
        see it (e.g. 'Need olive oil'). Use when the user says 'add a note', 'post on
        the board', or asks to tell/remind the household about something to buy.

        Args:
            text: The note, short and clear (max 150 characters).
        """
        def run():
            t = (text or "").strip()[:150]
            if not t:
                return {"ok": False, "message": "The note was empty"}
            color = random.choice(BOARD_COLORS)
            db.session.add(BoardNote(household_id=household_id, text=t, color=color, posted_by_id=user_id))
            db.session.commit()
            actions.append({"type": "note_added", "text": f"Posted a note on the board: {t}"})
            return {"ok": True, "message": f"Posted the note '{t}' on the board"}
        return once("note", {"t": text}, run)

    def add_inventory_item(name: str, category: str = "other", quantity: float = 1.0,
                           unit: str = "unit", storage: str = "fridge", expires_in_days: int = -1) -> dict:
        """Add ONE food item to the household's inventory (food the household HAS now).
        Use when the user says they bought/got something or asks to add X to the
        inventory, fridge, freezer or pantry. Call once per item.

        Args:
            name: The food, e.g. 'Whole milk'.
            category: One of produce, dairy, meat, bakery, grains, other.
            quantity: How many/much. Default 1.
            unit: e.g. 'litre', 'pack', 'kg', 'bag', 'unit'.
            storage: One of fridge, freezer, pantry, counter.
            expires_in_days: Days until it expires, if the user said or it is well known
                (milk about 7). Use -1 if unknown and an estimate will be used.
        """
        def run():
            n = (name or "").strip()[:150]
            if not n:
                return {"ok": False, "message": "No item name given"}
            cat = (category or "other").strip().lower()
            cat = cat if cat in CATEGORIES else "other"
            stor = (storage or "fridge").strip().lower()
            stor = stor if stor in STORAGE_LOCATIONS else "fridge"
            try:
                qty = float(quantity)
            except (TypeError, ValueError):
                qty = 1.0
            qty = qty if 0 < qty <= 10000 else 1.0
            u = (unit or "unit").strip()[:30] or "unit"
            expiry = date.today() + timedelta(days=int(expires_in_days)) if expires_in_days is not None and int(expires_in_days) >= 0 else None

            item = Item(household_id=household_id, name=n, category=cat, quantity=qty, unit=u,
                        storage=stor, purchase_date=date.today(), expiry_date=expiry,
                        is_estimate=expiry is None)
            db.session.add(item)
            db.session.add(PurchaseHistory(household_id=household_id, item_name=n, category=cat,
                                           purchase_date=date.today(), quantity=qty, unit=u))
            db.session.commit()
            shown = f"{qty:g} {u} " if u != "unit" or qty != 1 else ""
            actions.append({"type": "inventory_added", "text": f"Added {shown}{n} to the {stor}"})
            return {"ok": True, "message": f"Added {shown}{n} to the {stor}",
                    "expires": expiry.isoformat() if expiry else "estimated"}
        return once("inv", {"n": name, "c": category, "q": quantity, "u": unit, "s": storage, "e": expires_in_days}, run)

    tools = [get_inventory, get_shopping_list, get_board_notes,
             add_to_shopping_list, add_board_note, add_inventory_item]
    return tools, actions
