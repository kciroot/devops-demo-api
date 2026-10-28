def _create(client, **body):
    body.setdefault("title", "Aprender Kubernetes")
    return client.post("/api/v1/tasks", json=body)


# ---- Health, readiness and metrics ----------------------------------------

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "version": "test"}


def test_ready(client):
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.get_json()["database"] == "up"


def test_ready_reports_database_down(app, client, monkeypatch):
    from app import db

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "ping", boom)
    res = client.get("/ready")
    assert res.status_code == 503
    assert res.get_json()["database"] == "down"


def test_metrics_exposes_prometheus_format(client):
    _create(client)
    client.get("/api/v1/tasks")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'app_info{version="test"} 1' in body
    assert "tasks_total 1" in body
    assert 'http_requests_total{method="POST",route="/api/v1/tasks",status="201"} 1' in body
    assert "http_request_duration_seconds_bucket" in body


def test_security_headers(client):
    res = client.get("/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"


# ---- CRUD -----------------------------------------------------------------

def test_create_and_get_task(client):
    res = _create(client, title="  Configurar CI  ", description="GitHub Actions")
    assert res.status_code == 201
    task = res.get_json()
    assert task["title"] == "Configurar CI"
    assert task["done"] is False
    assert res.headers["Location"] == f"/api/v1/tasks/{task['id']}"

    got = client.get(f"/api/v1/tasks/{task['id']}")
    assert got.status_code == 200
    assert got.get_json() == task


def test_list_filter_and_pagination(client):
    _create(client, title="a")
    _create(client, title="b", done=True)
    _create(client, title="c")

    all_items = client.get("/api/v1/tasks").get_json()["items"]
    assert [t["title"] for t in all_items] == ["a", "b", "c"]

    done = client.get("/api/v1/tasks?done=true").get_json()["items"]
    assert [t["title"] for t in done] == ["b"]

    page = client.get("/api/v1/tasks?limit=1&offset=1").get_json()
    assert [t["title"] for t in page["items"]] == ["b"]


def test_update_task(client):
    task = _create(client).get_json()
    res = client.put(f"/api/v1/tasks/{task['id']}", json={"done": True})
    assert res.status_code == 200
    assert res.get_json()["done"] is True
    assert res.get_json()["title"] == task["title"]


def test_delete_task(client):
    task = _create(client).get_json()
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 404


def test_update_missing_task_returns_404(client):
    assert client.put("/api/v1/tasks/999", json={"done": True}).status_code == 404


# ---- Validation -----------------------------------------------------------

def test_rejects_missing_title(client):
    res = client.post("/api/v1/tasks", json={"description": "x"})
    assert res.status_code == 400
    assert "title" in res.get_json()["error"]


def test_rejects_non_json_body(client):
    res = client.post("/api/v1/tasks", data="not json", content_type="text/plain")
    assert res.status_code == 400


def test_rejects_unknown_fields(client):
    res = _create(client, id=5)
    assert res.status_code == 400
    assert "unknown fields" in res.get_json()["error"]


def test_rejects_bad_types(client):
    assert _create(client, done="yes").status_code == 400
    assert _create(client, title="").status_code == 400
    assert _create(client, title="x" * 201).status_code == 400
    assert _create(client, description=5).status_code == 400


def test_rejects_empty_update(client):
    task = _create(client).get_json()
    assert client.put(f"/api/v1/tasks/{task['id']}", json={}).status_code == 400


def test_rejects_bad_query_params(client):
    assert client.get("/api/v1/tasks?done=maybe").status_code == 400
    assert client.get("/api/v1/tasks?limit=abc").status_code == 400
    assert client.get("/api/v1/tasks?limit=500").status_code == 400


def test_rejects_oversized_body(client):
    res = client.post("/api/v1/tasks", json={"title": "x", "description": "y" * 20000})
    assert res.status_code == 413


def test_unknown_route_and_method(client):
    assert client.get("/nope").status_code == 404
    assert client.patch("/health").status_code == 405


# ---- Security -------------------------------------------------------------

def test_sql_injection_is_stored_as_plain_text(client):
    payload = "x'); DROP TABLE tasks; --"
    task = _create(client, title=payload).get_json()
    assert task["title"] == payload
    # The table still exists and holds the row.
    assert len(client.get("/api/v1/tasks").get_json()["items"]) == 1
