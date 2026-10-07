"""
app/__init__.py — Flask application factory.

Creates and configures the Flask app, registers all blueprints.
"""
from flask import Flask
from .config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Register blueprints ──────────────────────────────────────────────────
    from .routes.health import health_bp
    from .routes.patient import patient_bp
    from .routes.ocr import ocr_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(ocr_bp)

    return app

