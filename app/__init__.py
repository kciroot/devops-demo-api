"""Tasks API: a small REST service used to demonstrate a full DevOps flow."""

import json
import logging
import os
import time

from flask import Flask, g, jsonify, request

from . import db
from .metrics import Metrics
from .routes import api


class JsonFormatter(logging.Formatter):
    """Structured logs: one JSON object per line, easy to ship to ELK or Loki."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def _configure_logging() -> logging.Logger:
    logger = logging.getLogger("tasks_api")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logger.propagate = False
    return logger


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        DATABASE_PATH=os.environ.get("DATABASE_PATH", "/data/tasks.db"),
        APP_VERSION=os.environ.get("APP_VERSION", "dev"),
        MAX_CONTENT_LENGTH=16 * 1024,  # reject bodies over 16 KB
        JSON_SORT_KEYS=False,
    )
    if config:
        app.config.update(config)

    logger = _configure_logging()
    metrics = Metrics()
    app.extensions["metrics"] = metrics

    db.init_app(app)
    app.register_blueprint(api)

    @app.before_request
    def _start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def _record(response):
        duration = time.perf_counter() - g.get("start", time.perf_counter())
        route = request.url_rule.rule if request.url_rule else "unmatched"
        metrics.observe(request.method, route, response.status_code, duration)
        if route not in ("/health", "/metrics"):
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(404)
    def _not_found(_err):
        return jsonify(error="not found"), 404

    @app.errorhandler(405)
    def _method_not_allowed(_err):
        return jsonify(error="method not allowed"), 405

    @app.errorhandler(413)
    def _too_large(_err):
        return jsonify(error="request body too large"), 413

    @app.errorhandler(500)
    def _server_error(_err):
        logger.exception("unhandled error")
        return jsonify(error="internal server error"), 500

    return app
