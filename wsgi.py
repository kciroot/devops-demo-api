"""Entry point used by gunicorn (`gunicorn wsgi:app`) and for local runs."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Local development only. In containers gunicorn serves the app.
    app.run(host="127.0.0.1", port=8000)
