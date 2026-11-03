from flask import Flask, jsonify
from app.config import Config
from app.extensions import db, bcrypt, cors
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Allow the static frontend server to use any local development port.
    CORS(app, resources={
        r"/api/*": {
            "origins": (
                r"https?://(localhost|127\.0\.0\.1"
                # home/office network addresses, so a phone or another laptop can open the app
                r"|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
                r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?"
            ),
            "supports_credentials": True,
        }
    })

    db.init_app(app)
    bcrypt.init_app(app)

    from app.routes import auth, households, items, insights, shopping, board, analytics, chatbot, settings
    app.register_blueprint(auth.bp)
    app.register_blueprint(households.bp)
    app.register_blueprint(items.bp)
    app.register_blueprint(insights.bp)
    app.register_blueprint(shopping.bp)
    app.register_blueprint(board.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(chatbot.bp)
    app.register_blueprint(settings.bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Server error"}), 500

    return app
