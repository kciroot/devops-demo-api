"""Database access layer (SQLite).

Every query uses parameters (`?`), never string concatenation,
so user input can't turn into SQL (prevents SQL injection).
"""

import os
import sqlite3
from datetime import UTC, datetime

from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    done        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
"""

COLUMNS = "id, title, description, done, created_at, updated_at"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE_PATH"])
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


def init_app(app: Flask) -> None:
    init_db(app.config["DATABASE_PATH"])
    app.teardown_appcontext(close_db)


def _to_dict(row: sqlite3.Row) -> dict:
    task = dict(row)
    task["done"] = bool(task["done"])
    return task


def ping() -> bool:
    get_db().execute("SELECT 1")
    return True


def list_tasks(done: bool | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    sql = f"SELECT {COLUMNS} FROM tasks"
    params: list = []
    if done is not None:
        sql += " WHERE done = ?"
        params.append(int(done))
    sql += " ORDER BY id LIMIT ? OFFSET ?"
    params += [limit, offset]
    return [_to_dict(r) for r in get_db().execute(sql, params).fetchall()]


def get_task(task_id: int) -> dict | None:
    row = get_db().execute(f"SELECT {COLUMNS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _to_dict(row) if row else None


def create_task(title: str, description: str = "", done: bool = False) -> dict:
    now = _now()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (title, description, done, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, description, int(done), now, now),
    )
    conn.commit()
    return get_task(cur.lastrowid)


def update_task(task_id: int, fields: dict) -> dict | None:
    if get_task(task_id) is None:
        return None
    allowed = {"title", "description", "done"}
    sets, params = [], []
    for key in ("title", "description", "done"):  # fixed order, whitelisted names
        if key in fields and key in allowed:
            sets.append(f"{key} = ?")
            params.append(int(fields[key]) if key == "done" else fields[key])
    sets.append("updated_at = ?")
    params += [_now(), task_id]
    conn = get_db()
    conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    conn = get_db()
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return cur.rowcount > 0
