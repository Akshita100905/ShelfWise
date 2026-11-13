import os
from flask import Flask, jsonify, send_from_directory
from app.config import Config
from app.extensions import db, bcrypt
from flask_cors import CORS


def create_app():

    frontend_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../../frontend"
        )
    )

    app = Flask(
        __name__,
        static_folder=frontend_path,
        static_url_path=""
    )

    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)

    # Keep CORS available for local development.
    CORS(app, resources={
        r"/api/*": {
            "origins": (
                r"https?://(localhost|127\.0\.0\.1"
                r"|192\.168\.\d{1,3}\.\d{1,3}"
                r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
                r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?"
            ),
            "supports_credentials": True,
        }
    })

    # Register API blueprints
    from app.routes import (
        auth, households, items, insights,
        shopping, board, analytics, chatbot, settings
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(households.bp)
    app.register_blueprint(items.bp)
    app.register_blueprint(insights.bp)
    app.register_blueprint(shopping.bp)
    app.register_blueprint(board.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(chatbot.bp)
    app.register_blueprint(settings.bp)

    # Frontend pages
    @app.get("/")
    def index():
        return send_from_directory(frontend_path, "index.html")

    @app.get("/auth.html")
    def auth_page():
        return send_from_directory(frontend_path, "auth.html")

    @app.get("/app.html")
    def dashboard():
        return send_from_directory(frontend_path, "app.html")

    # API health check
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # 404 handler
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Server error"}), 500

    return app
