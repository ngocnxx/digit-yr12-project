"""Flask application factory — JSON API only (it renders no HTML).

Wires config from the environment, CORS for the split-origin front-end, the
resource blueprints, JSON error handlers, and the per-request DB teardown.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

import db
from errors import ApiError
from routes.auth import bp as auth_bp
from routes.subjects import bp as subjects_bp
from routes.topics import bp as topics_bp
from routes.user import bp as user_bp


def create_app(config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-insecure-change-me"),
        DATABASE_PATH=os.environ.get("DATABASE_PATH", "navigator.db"),
    )
    if config:
        app.config.update(config)

    CORS(app, resources={r"/api/*": {"origins": os.environ.get("CORS_ORIGIN", "*")}})

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(topics_bp)

    app.teardown_appcontext(db.close_db)

    @app.errorhandler(ApiError)
    def _handle_api_error(err: ApiError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(404)
    def _handle_404(_err):
        return jsonify(error="Not found."), 404

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
