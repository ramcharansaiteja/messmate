"""Production WSGI entry point for Gunicorn and other WSGI servers."""

from app import app, ensure_meal_qr_column
from models import db


with app.app_context():
    db.create_all()
    ensure_meal_qr_column()
