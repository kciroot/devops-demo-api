"""HTTP routes: health checks, metrics and the /api/v1/tasks CRUD."""

from flask import Blueprint, Response, current_app, jsonify, request

from . import db

api = Blueprint("api", __name__)

MAX_TITLE = 200
MAX_DESCRIPTION = 2000


def _error(message: str, status: int = 400):
    return jsonify(error=message), status


def _validate(payload, partial: bool = False):
    """Return (clean_fields, error_message)."""
    if not isinstance(payload, dict):
        return None, "body must be a JSON object"
    unknown = set(payload) - {"title", "description", "done"}
    if unknown:
        return None, f"unknown fields: {', '.join(sorted(unknown))}"
    clean = {}
    if "title" in payload:
        title = payload["title"]
        if not isinstance(title, str) or not title.strip():
            return None, "title must be a non-empty string"
        if len(title) > MAX_TITLE:
            return None, f"title must be at most {MAX_TITLE} characters"
        clean["title"] = title.strip()
    elif not partial:
        return None, "title is required"
    if "description" in payload:
        desc = payload["description"]
        if not isinstance(desc, str) or len(desc) > MAX_DESCRIPTION:
            return None, f"description must be a string of at most {MAX_DESCRIPTION} characters"
        clean["description"] = desc
    if "done" in payload:
        if not isinstance(payload["done"], bool):
            return None, "done must be true or false"
        clean["done"] = payload["done"]
    if partial and not clean:
        return None, "nothing to update"
    return clean, None


# ---- Operations endpoints -------------------------------------------------

@api.get("/health")
def health():
    """Liveness: the process is up. Kubernetes restarts the pod if this fails."""
    return jsonify(status="ok", version=current_app.config["APP_VERSION"])


@api.get("/ready")
def ready():
    """Readiness: the app can serve traffic (database reachable)."""
    try:
        db.ping()
    except Exception:  # noqa: BLE001 - any DB failure means not ready
        return jsonify(status="unavailable", database="down"), 503
    return jsonify(status="ready", database="up")


@api.get("/metrics")
def metrics():
    count = db.get_db().execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    body = current_app.extensions["metrics"].render(current_app.config["APP_VERSION"], count)
    return Response(body, mimetype="text/plain; version=0.0.4")


# ---- Tasks CRUD -----------------------------------------------------------

@api.get("/api/v1/tasks")
def list_tasks():
    done_arg = request.args.get("done")
    done = None
    if done_arg is not None:
        if done_arg not in ("true", "false"):
            return _error("done must be true or false")
        done = done_arg == "true"
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _error("limit and offset must be integers")
    if not 1 <= limit <= 100 or offset < 0:
        return _error("limit must be 1-100 and offset >= 0")
    return jsonify(items=db.list_tasks(done, limit, offset), limit=limit, offset=offset)


@api.post("/api/v1/tasks")
def create_task():
    fields, err = _validate(request.get_json(silent=True))
    if err:
        return _error(err)
    task = db.create_task(**fields)
    return jsonify(task), 201, {"Location": f"/api/v1/tasks/{task['id']}"}


@api.get("/api/v1/tasks/<int:task_id>")
def get_task(task_id: int):
    task = db.get_task(task_id)
    return jsonify(task) if task else _error("task not found", 404)


@api.put("/api/v1/tasks/<int:task_id>")
@api.patch("/api/v1/tasks/<int:task_id>")
def update_task(task_id: int):
    fields, err = _validate(request.get_json(silent=True), partial=True)
    if err:
        return _error(err)
    task = db.update_task(task_id, fields)
    return jsonify(task) if task else _error("task not found", 404)


@api.delete("/api/v1/tasks/<int:task_id>")
def delete_task(task_id: int):
    if not db.delete_task(task_id):
        return _error("task not found", 404)
    return "", 204
