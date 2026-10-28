from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    posted_cards = db.relationship(
        'MealCard',
        foreign_keys='MealCard.posted_by',
        backref=db.backref('poster', lazy=True),
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    claimed_cards = db.relationship(
        'MealCard',
        foreign_keys='MealCard.claimed_by',
        backref=db.backref('claimer', lazy=True),
        lazy='dynamic'
    )

    def set_password(self, password):
        """Hash and store the user password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Serialize user object without sensitive information."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.email}>'


class MealCard(db.Model):
    __tablename__ = 'meal_card'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    meal_type = db.Column(db.String(50), nullable=False)  # breakfast, lunch, dinner, snack
    pickup_location = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    expiry_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available')  # available, claimed, completed, expired
    qr_image_filename = db.Column(db.String(255), nullable=True)

    # Foreign Keys
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    claimed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Token used to verify and complete a meal handover
    claim_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    claimed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    def is_expired(self):
        """Check whether the meal card has passed its expiry time and update status if applicable."""
        if self.status == 'expired':
            return True
        if self.expiry_time and datetime.utcnow() > self.expiry_time:
            if self.status == 'available':
                self.status = 'expired'
            return True
        return False

    def to_dict(self):
        """Serialize meal card object into a JSON-friendly dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'meal_type': self.meal_type,
            'pickup_location': self.pickup_location,
            'quantity': self.quantity,
            'expiry_time': self.expiry_time.isoformat() if self.expiry_time else None,
            'status': self.status,
            'posted_by': self.posted_by,
            'poster_name': self.poster.name if self.poster else None,
            'claimed_by': self.claimed_by,
            'claimer_name': self.claimer.name if self.claimer else None,
            'claim_token': self.claim_token,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'claimed_at': self.claimed_at.isoformat() if self.claimed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'is_expired': self.is_expired()
        }

    def __repr__(self):
        return f'<MealCard {self.id} - {self.title} ({self.status})>'
