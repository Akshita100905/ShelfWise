from datetime import datetime, date
from app.extensions import db


def now():
    return datetime.utcnow()


class Household(db.Model):
    __tablename__ = "households"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    invite_code = db.Column(db.String(12), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    # `members` = users whose *active* household this is (legacy column). Real
    # membership (a user can belong to several households) lives in `memberships`.
    members = db.relationship("User", back_populates="household", cascade="save-update, merge")
    memberships = db.relationship("Membership", back_populates="household", cascade="all, delete-orphan")
    items = db.relationship("Item", back_populates="household", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "invite_code": self.invite_code,
            "member_count": len(self.memberships),
        }


class Membership(db.Model):
    """A user belonging to a household. One user can have many of these."""
    __tablename__ = "household_members"
    __table_args__ = (db.UniqueConstraint("user_id", "household_id", name="uq_member_user_household"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(20), default="member")  # owner | member
    joined_at = db.Column(db.DateTime, default=now)

    user = db.relationship("User", back_populates="memberships")
    household = db.relationship("Household", back_populates="memberships")


class Invite(db.Model):
    """A single-use, expiring invite link to a household."""
    __tablename__ = "invites"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email = db.Column(db.String(180), nullable=True)      # optional: who it was sent to
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=now)
    expires_at = db.Column(db.DateTime, nullable=False)
    accepted_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    revoked = db.Column(db.Boolean, default=False)

    household = db.relationship("Household")
    invited_by = db.relationship("User", foreign_keys=[invited_by_id])

    @property
    def status(self):
        if self.accepted_at:
            return "accepted"
        if self.revoked:
            return "revoked"
        if self.expires_at <= now():
            return "expired"
        return "pending"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="member")  # owner | member
    created_at = db.Column(db.DateTime, default=now)

    # preferences (Settings screen)
    theme = db.Column(db.String(10), default="dark")       # light | dark | system
    language = db.Column(db.String(10), default="en")
    notify_expiry = db.Column(db.Boolean, default=True)
    notify_board = db.Column(db.Boolean, default=True)
    notify_ai_tips = db.Column(db.Boolean, default=False)

    household = db.relationship("Household", back_populates="members")
    memberships = db.relationship("Membership", back_populates="user", cascade="all, delete-orphan",
                                  passive_deletes=True)

    def initials(self):
        parts = self.name.split()
        return "".join(p[0] for p in parts[:2]).upper()

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "household_id": self.household_id,
            "initials": self.initials(),
            "theme": self.theme,
            "language": self.language,
            "notify_expiry": self.notify_expiry,
            "notify_board": self.notify_board,
            "notify_ai_tips": self.notify_ai_tips,
        }


CATEGORY_ICONS = {
    "produce": "🥦",
    "dairy": "🥛",
    "meat": "🥩",
    "bakery": "🍞",
    "grains": "🍝",
    "other": "📦",
}

STORAGE_LOCATIONS = ["fridge", "freezer", "pantry", "counter"]


class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(30), default="other")  # produce/dairy/meat/bakery/grains/other
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30), default="unit")
    storage = db.Column(db.String(20), default="fridge")  # fridge/freezer/pantry/counter
    purchase_date = db.Column(db.Date, default=date.today)
    expiry_date = db.Column(db.Date, nullable=True)
    is_estimate = db.Column(db.Boolean, default=False)     # "Estimate - limited data"
    created_at = db.Column(db.DateTime, default=now)

    household = db.relationship("Household", back_populates="items")
    consumption_logs = db.relationship("ConsumptionLog", back_populates="item", cascade="all, delete-orphan")

    def icon(self):
        return CATEGORY_ICONS.get(self.category, "📦")

    def to_dict(self, risk=None):
        days_left = None
        if self.expiry_date:
            days_left = (self.expiry_date - date.today()).days
        d = {
            "id": self.id,
            "household_id": self.household_id,
            "name": self.name,
            "category": self.category,
            "icon": self.icon(),
            "quantity": self.quantity,
            "unit": self.unit,
            "storage": self.storage,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "days_left": days_left,
            "is_estimate": self.is_estimate,
        }
        if risk is not None:
            d["risk_score"] = risk["score"]
            d["risk_label"] = risk["label"]
        return d


class ConsumptionLog(db.Model):
    __tablename__ = "consumption_log"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    quantity_used = db.Column(db.Float, nullable=False)
    used_at = db.Column(db.DateTime, default=now)

    item = db.relationship("Item", back_populates="consumption_logs")


class PurchaseHistory(db.Model):
    __tablename__ = "purchase_history"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(30), default="other")
    purchase_date = db.Column(db.Date, default=date.today)
    quantity = db.Column(db.Float, default=1)
    unit = db.Column(db.String(30), default="unit")
    was_wasted = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "item_name": self.item_name,
            "category": self.category,
            "purchase_date": self.purchase_date.isoformat(),
            "quantity": self.quantity,
            "unit": self.unit,
            "was_wasted": self.was_wasted,
        }


class ShoppingListItem(db.Model):
    __tablename__ = "shopping_list"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    added_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_purchased = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "is_purchased": self.is_purchased,
            "created_at": self.created_at.isoformat(),
        }


BOARD_COLORS = ["yellow", "orange", "green", "pink", "blue"]


class BoardNote(db.Model):
    __tablename__ = "board_notes"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    text = db.Column(db.String(150), nullable=False)
    color = db.Column(db.String(20), default="yellow")
    posted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_bought = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now)

    posted_by = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "color": self.color,
            "is_bought": self.is_bought,
            "posted_by": self.posted_by.name if self.posted_by else "Someone",
            "posted_by_initials": self.posted_by.initials() if self.posted_by else "??",
            "created_at": self.created_at.isoformat(),
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    household_id = db.Column(db.Integer, db.ForeignKey("households.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }
