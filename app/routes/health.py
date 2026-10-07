"""
app/routes/health.py

Lightweight keep-alive endpoints.
/ping and /health both return 200 OK with a JSON status payload.
Used by cron-job.org / UptimeRobot to prevent Render cold starts.
"""
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/ping")
def ping():
    return "pong", 200


@health_bp.route("/health")
def health():
    return jsonify({"status": "ok", "app": "MediHelp"}), 200
