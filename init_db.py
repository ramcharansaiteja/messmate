"""
init_db.py - Initialize MessMate SQLite database with schema and sample seed data.
Idempotent: Safe to run repeatedly; won't duplicate data if records already exist.
Usage:
    python init_db.py          # creates tables and seeds if empty
    python init_db.py --reset  # drops all tables and re-seeds fresh data
"""

import sys
import secrets
from datetime import datetime, timedelta

from app import app
from models import db, User, MealCard


def seed_database(reset=False):
    with app.app_context():
        if reset:
            print("Resetting database (dropping existing tables)...")
            db.drop_all()

        print("Creating database tables...")
        db.create_all()

        # Check if users already exist (Idempotency)
        existing_user_count = User.query.count()
        if existing_user_count > 0:
            print(f"Database already populated ({existing_user_count} users found). Skipping seed insertion.")
            return

        print("Seeding sample users...")
        users = [
            User(
                name="Rahul Sharma",
                email="rahul@messmate.edu"
            ),
            User(
                name="Priya Patel",
                email="priya@messmate.edu"
            ),
            User(
                name="Amit Verma",
                email="amit@messmate.edu"
            )
        ]

        # Set default password for all sample users
        for u in users:
            u.set_password("password123")
            db.session.add(u)

        db.session.commit()
        print("Sample users created successfully (password: password123):")
        for u in users:
            print(f"  - {u.name} ({u.email}) [ID: {u.id}]")

        print("Seeding sample meal cards...")
        now = datetime.utcnow()

        cards = [
            MealCard(
                title="South Indian Thali & 4 Rotis",
                description="Fresh thali with dal tadka, aloo gobi, steamed rice, and 4 fresh rotis packed neatly.",
                meal_type="lunch",
                pickup_location="Hostel Block B, Room 204",
                quantity=2,
                expiry_time=now + timedelta(hours=4),
                status="available",
                posted_by=users[0].id,
                claim_token=secrets.token_urlsafe(32),
                created_at=now - timedelta(minutes=45)
            ),
            MealCard(
                title="Paneer Butter Masala & Naan Combo",
                description="Rich paneer butter masala with 2 garlic naans and jeera rice from North Mess.",
                meal_type="dinner",
                pickup_location="Girls Hostel 1, Ground Floor Lobby",
                quantity=1,
                expiry_time=now + timedelta(hours=6),
                status="available",
                posted_by=users[1].id,
                claim_token=secrets.token_urlsafe(32),
                created_at=now - timedelta(minutes=20)
            ),
            MealCard(
                title="Crispy Samosas & Masala Chai Flask",
                description="3 hot samosas with sweet tamarind and mint chutneys, plus insulated flask of masala chai.",
                meal_type="snack",
                pickup_location="Library Lawn, Bench #4",
                quantity=3,
                expiry_time=now + timedelta(hours=2),
                status="available",
                posted_by=users[2].id,
                claim_token=secrets.token_urlsafe(32),
                created_at=now - timedelta(minutes=15)
            ),
            MealCard(
                title="Masala Dosa with Medu Vada & Sambar",
                description="Crispy masala dosa with aloo filling, 2 medu vadas, coconut chutney, and hot sambar.",
                meal_type="breakfast",
                pickup_location="Hostel Block A, Mess Front Desk",
                quantity=1,
                expiry_time=now + timedelta(hours=1),
                status="claimed",
                posted_by=users[0].id,
                claimed_by=users[1].id,
                claim_token="sample_token_claimed_breakfast_001",
                created_at=now - timedelta(hours=2),
                claimed_at=now - timedelta(minutes=30)
            ),
            MealCard(
                title="Hyderabadi Veg Dum Biryani & Raita",
                description="Fragrant aromatic basmati dum biryani with vegetable salan and cucumber mint raita.",
                meal_type="dinner",
                pickup_location="Hostel Block C, TV Room",
                quantity=2,
                expiry_time=now - timedelta(days=1),
                status="completed",
                posted_by=users[1].id,
                claimed_by=users[2].id,
                claim_token="sample_token_completed_dinner_002",
                created_at=now - timedelta(days=1, hours=4),
                claimed_at=now - timedelta(days=1, hours=2),
                completed_at=now - timedelta(days=1, hours=1)
            ),
            MealCard(
                title="Indori Poha & Boiled Eggs Pack",
                description="Mildly spiced light poha with roasted peanuts, sev, and 2 fresh boiled eggs.",
                meal_type="breakfast",
                pickup_location="Central Dining Hall Counter 3",
                quantity=1,
                expiry_time=now - timedelta(hours=5),
                status="expired",
                posted_by=users[2].id,
                claim_token=secrets.token_urlsafe(32),
                created_at=now - timedelta(hours=8)
            )
        ]

        for card in cards:
            db.session.add(card)

        db.session.commit()
        print("Sample meal cards created successfully:")
        for c in cards:
            print(f"  - [{c.status.upper()}] {c.title} ({c.meal_type}) by User {c.posted_by}")

        print("Database initialization and seed complete!")


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    seed_database(reset=reset_flag)
