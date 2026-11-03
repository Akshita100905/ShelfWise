from flask import Blueprint, request, jsonify, session
from app.extensions import db
from app.models import BoardNote, BOARD_COLORS
from app.utils.decorators import household_required
import random

bp = Blueprint("board", __name__, url_prefix="/api/board")


@bp.get("")
@household_required
def list_notes():
    notes = BoardNote.query.filter_by(
        household_id=session["household_id"], is_bought=False
    ).order_by(BoardNote.created_at.desc()).all()
    return jsonify({"notes": [n.to_dict() for n in notes]})


@bp.post("")
@household_required
def add_note():
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Note text is required"}), 400

    note = BoardNote(
        household_id=session["household_id"],
        text=text,
        color=data.get("color") or random.choice(BOARD_COLORS),
        posted_by_id=session["user_id"],
    )
    db.session.add(note)
    db.session.commit()
    return jsonify({"note": note.to_dict()}), 201


@bp.put("/<int:note_id>/bought")
@household_required
def mark_bought(note_id):
    note = BoardNote.query.filter_by(id=note_id, household_id=session["household_id"]).first()
    if not note:
        return jsonify({"error": "Not found"}), 404
    note.is_bought = True
    db.session.commit()
    return jsonify({"ok": True})


@bp.delete("/<int:note_id>")
@household_required
def delete_note(note_id):
    note = BoardNote.query.filter_by(id=note_id, household_id=session["household_id"]).first()
    if not note:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(note)
    db.session.commit()
    return jsonify({"ok": True})
