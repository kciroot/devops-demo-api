import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE_PATH": str(tmp_path / "test.db"), "APP_VERSION": "test"})


@pytest.fixture()
def client(app):
    return app.test_client()
