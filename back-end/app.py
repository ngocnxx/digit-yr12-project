"""Flask application factory - the JSON API, and the front-end files too,
so the whole app can run from one address.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import db
import s3db
from errors import ApiError
from routes.assessment import bp as assessment_bp
from routes.auth import bp as auth_bp
from routes.reviews import bp as reviews_bp
from routes.settings import bp as settings_bp
from routes.subjects import bp as subjects_bp
from routes.topics import bp as topics_bp
from routes.user import bp as user_bp

# Full paths, so it works no matter which folder the server is started from
HERE = Path(__file__).resolve().parent
FRONT_END = HERE.parent / "front-end"

'''config from the environment'''
def create_app(config: dict | None = None) -> Flask:
    load_dotenv(HERE / ".env")
    app = Flask(__name__, static_folder=str(FRONT_END), static_url_path="")
    # A relative DATABASE_PATH (like "navigator.db") means "inside back-end/",
    # not "wherever the server happened to be started from".
    db_path = Path(os.environ.get("DATABASE_PATH", "navigator.db"))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-insecure-change-me"),
        DATABASE_PATH=str(db_path if db_path.is_absolute() else HERE / db_path),
        # Biggest request we accept: one photo (about 2.8 MB) plus the text
        MAX_CONTENT_LENGTH=3 * 1024 * 1024,
    )
    """CORS for the split-origin front-end"""
    if config:
        app.config.update(config)
    _check_cloud_settings(app)
    CORS(app, resources={r"/api/*": {"origins": os.environ.get("CORS_ORIGIN", "*")}}); 

    """Resources blueprint"""
    app.register_blueprint(auth_bp);
    app.register_blueprint(user_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(topics_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(assessment_bp)

    app.teardown_appcontext(db.close_db)
    """JSON error handlers"""
    @app.errorhandler(ApiError) 
   
    def _handle_api_error(err: ApiError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(404)
    def _handle_404(_err):
        return jsonify(error="Not found."), 404

    @app.errorhandler(413)
    def _handle_413(_err):
        return jsonify(error="That upload is too big."), 413

    # API answers belong to one student, so a cache must never keep them
    @app.after_request
    def _no_store(resp):
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/api/health")
    def health():
        # Touch the database, so a missing database fails the health check
        try:
            db.get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone()
        except sqlite3.Error:
            return jsonify(error="Database unavailable."), 503
        return jsonify(status="ok")

    # The home page. Other files (js, css) are served from front-end/ automatically.
    @app.get("/")
    def home():
        return send_from_directory(FRONT_END, "index.html")

    # Keep the database in S3 when S3DB_BUCKET is set (does nothing otherwise)
    s3db.install(app)
    return app


def _check_cloud_settings(app: Flask) -> None:
    """In the cloud, refuse to start with settings that are unsafe or lose data."""
    on_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if not on_lambda and os.environ.get("APP_ENV") != "production":
        return
    # The dev key is public, so anyone could make a login token with it
    key = app.config.get("SECRET_KEY") or ""
    if key == "dev-insecure-change-me" or len(key) < 32:
        raise RuntimeError("SECRET_KEY must be a random value of at least 32 characters.")
    # On Lambda, local files are wiped, so the database must live in S3 or on a mount
    s3_bucket = app.config.get("S3DB_BUCKET") or os.environ.get("S3DB_BUCKET")
    if on_lambda and not s3_bucket and not app.config["DATABASE_PATH"].startswith("/mnt/"):
        raise RuntimeError("Set S3DB_BUCKET (or a /mnt/ DATABASE_PATH) so data is not lost.")


app = create_app()


if __name__ == "__main__":
    # Port 5050 is what the front-end asks for (see front-end/js/config.js)
    app.run(debug=True, port=5050)
