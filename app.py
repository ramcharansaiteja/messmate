import os
import io
import re
import base64
import secrets
from io import BytesIO
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, abort, session, send_from_directory
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
import qrcode
from PIL import Image, ImageFilter, UnidentifiedImageError
from sqlalchemy import inspect, text

from config import Config
from models import db, User, MealCard


app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(Config)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

QR_UPLOAD_FOLDER = os.path.join(app.instance_path, "meal_qrs")
MAX_QR_IMAGE_BYTES = 5 * 1024 * 1024
MAX_QR_IMAGE_PIXELS = 24_000_000
os.makedirs(QR_UPLOAD_FOLDER, exist_ok=True)

# Initialize extensions
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None


# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------

def generate_qr_code(data):
    """Generate a base64 encoded PNG data URI for a given URL or text."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64_data}"
    except Exception as e:
        app.logger.error(f"Error generating QR code: {e}")
        return None


def save_qr_image(upload):
    """Validate and save a meal QR image and its blurred public preview."""
    contents = upload.read(MAX_QR_IMAGE_BYTES + 1)
    if not contents:
        raise ValueError("Please upload a QR screenshot.")
    if len(contents) > MAX_QR_IMAGE_BYTES:
        raise ValueError("The QR screenshot must be 5 MB or smaller.")

    try:
        image = Image.open(BytesIO(contents))
        if image.format not in {"PNG", "JPEG", "WEBP"}:
            raise ValueError("Upload a PNG, JPG, or WebP QR screenshot.")
        if image.width * image.height > MAX_QR_IMAGE_PIXELS:
            raise ValueError("The QR screenshot dimensions are too large.")
        image.load()
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("That file is not a valid PNG, JPG, or WebP image.")

    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    image_id = uuid4().hex
    filename = f"{image_id}.png"
    image.save(os.path.join(QR_UPLOAD_FOLDER, filename), format="PNG", optimize=True)

    blurred = image.convert("RGB").filter(ImageFilter.GaussianBlur(radius=32))
    blurred.thumbnail((480, 480))
    blurred.save(os.path.join(QR_UPLOAD_FOLDER, f"{image_id}.blur.png"), format="PNG", optimize=True)
    return filename


def ensure_meal_qr_column():
    """Add the optional QR filename field to existing SQLite databases."""
    columns = {column["name"] for column in inspect(db.engine).get_columns("meal_card")}
    if "qr_image_filename" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE meal_card ADD COLUMN qr_image_filename VARCHAR(255)"))


def expire_overdue_cards():
    """Automatically update the status of available cards whose expiry has passed."""
    now = datetime.utcnow()
    expired_cards = MealCard.query.filter(
        MealCard.status == 'available',
        MealCard.expiry_time <= now
    ).all()
    if expired_cards:
        for card in expired_cards:
            card.status = 'expired'
        db.session.commit()


@app.before_request
def before_request_hook():
    """Ensure CSRF token exists in session and trigger auto-expiration check."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    expire_overdue_cards()


@app.context_processor
def inject_globals():
    """Inject global variables into all Jinja templates."""
    return {
        'csrf_token': session.get('csrf_token', ''),
        'now': datetime.utcnow()
    }


def validate_csrf():
    """Check CSRF token on POST requests if present in form or headers."""
    expected = session.get('csrf_token')
    token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
    if expected and token and token != expected:
        return False
    return True


# -------------------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------------------

@app.route("/")
def home():
    """Landing page route."""
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid security token. Please try again.", "danger")
            return redirect(url_for("login"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html", email=email), 400

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email), 401

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.name}!", "success")

        next_page = request.args.get("next")
        if not next_page or urlparse(next_page).netloc != "":
            next_page = url_for("dashboard")
        return redirect(next_page)

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration route."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid security token. Please try again.", "danger")
            return redirect(url_for("register"))

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Form Validation
        if not name or len(name) < 2 or len(name) > 100:
            flash("Name must be between 2 and 100 characters.", "danger")
            return render_template("register.html", name=name, email=email), 400

        email_regex = r"^[^@]+@[^@]+\.[^@]+$"
        if not email or not re.match(email_regex, email):
            flash("Please enter a valid email address.", "danger")
            return render_template("register.html", name=name, email=email), 400

        if not password or len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html", name=name, email=email), 400

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", name=name, email=email), 400

        # Check existing user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for("login"))

        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    """Log the current user out."""
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# -------------------------------------------------------------------------
# Core Meal Card Routes
# -------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard displaying available meal cards with filtering."""
    expire_overdue_cards()

    meal_type = request.args.get("meal_type", "").strip().lower()
    search = request.args.get("search", "").strip()

    query = MealCard.query.filter(MealCard.status.in_(["available", "claimed"]))

    if meal_type and meal_type in ["breakfast", "lunch", "dinner", "snack"]:
        query = query.filter_by(meal_type=meal_type)

    if search:
        query = query.filter(
            (MealCard.title.ilike(f"%{search}%")) |
            (MealCard.description.ilike(f"%{search}%")) |
            (MealCard.pickup_location.ilike(f"%{search}%"))
        )

    cards = query.order_by(MealCard.expiry_time.asc()).all()

    # Calculate statistics for the dashboard banner
    stats = {
        'available': MealCard.query.filter_by(status='available').count(),
        'claimed': MealCard.query.filter_by(status='claimed').count(),
        'completed': MealCard.query.filter_by(status='completed').count()
    }

    return render_template(
        "dashboard.html",
        cards=cards,
        current_meal_type=meal_type,
        search=search,
        stats=stats
    )


@app.route("/post-card", methods=["GET", "POST"])
@login_required
def post_card():
    """Post a new meal card form and submission."""
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid security token. Please try again.", "danger")
            return redirect(url_for("post_card"))

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        meal_type = request.form.get("meal_type", "").strip().lower()
        pickup_location = request.form.get("pickup_location", "").strip()
        quantity_val = request.form.get("quantity", "1").strip()
        expiry_val = request.form.get("expiry_time", "").strip()
        expiry_hours_val = request.form.get("expiry_hours", "").strip()

        # Validation
        if not title or len(title) < 3 or len(title) > 150:
            flash("Title must be between 3 and 150 characters.", "danger")
            return render_template("post_card.html", form=request.form), 400

        if meal_type not in ["breakfast", "lunch", "dinner", "snack"]:
            flash("Please choose a valid meal type (breakfast, lunch, dinner, snack).", "danger")
            return render_template("post_card.html", form=request.form), 400

        if not pickup_location or len(pickup_location) < 3 or len(pickup_location) > 200:
            flash("Pickup location must be between 3 and 200 characters.", "danger")
            return render_template("post_card.html", form=request.form), 400

        try:
            quantity = int(quantity_val)
            if quantity < 1:
                raise ValueError()
        except (ValueError, TypeError):
            flash("Quantity must be a positive integer.", "danger")
            return render_template("post_card.html", form=request.form), 400

        # Parse expiry datetime
        expiry_time = None
        if expiry_val:
            for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    expiry_time = datetime.strptime(expiry_val, fmt)
                    break
                except ValueError:
                    pass
        elif expiry_hours_val:
            try:
                hours = float(expiry_hours_val)
                if hours > 0:
                    expiry_time = datetime.utcnow() + timedelta(hours=hours)
            except ValueError:
                pass

        if not expiry_time:
            flash("Please provide a valid expiry date & time or duration.", "danger")
            return render_template("post_card.html", form=request.form), 400

        if expiry_time <= datetime.utcnow():
            flash("Expiry time must be in the future.", "danger")
            return render_template("post_card.html", form=request.form), 400

        qr_upload = request.files.get("qr_image")
        if not qr_upload or not qr_upload.filename:
            flash("Please upload a QR screenshot for this meal.", "danger")
            return render_template("post_card.html", form=request.form), 400

        try:
            qr_image_filename = save_qr_image(qr_upload)
        except ValueError as error:
            flash(str(error), "danger")
            return render_template("post_card.html", form=request.form), 400

        # Unique token for verification & QR generation
        claim_token = secrets.token_urlsafe(32)

        card = MealCard(
            title=title,
            description=description,
            meal_type=meal_type,
            pickup_location=pickup_location,
            quantity=quantity,
            expiry_time=expiry_time,
            status="available",
            posted_by=current_user.id,
            claim_token=claim_token,
            qr_image_filename=qr_image_filename
        )
        db.session.add(card)
        db.session.commit()

        flash("Meal card posted successfully!", "success")
        return redirect(url_for("dashboard"))

    return render_template("post_card.html")


@app.route("/my-cards")
@login_required
def my_cards():
    """Display cards posted and cards claimed by current user."""
    expire_overdue_cards()

    posted_cards = MealCard.query.filter_by(
        posted_by=current_user.id
    ).order_by(MealCard.created_at.desc()).all()

    claimed_cards = MealCard.query.filter_by(
        claimed_by=current_user.id
    ).order_by(MealCard.claimed_at.desc()).all()

    return render_template(
        "my_cards.html",
        posted_cards=posted_cards,
        claimed_cards=claimed_cards
    )


@app.route("/claim/<int:card_id>", methods=["POST"])
@login_required
def claim_card(card_id):
    """Claim a meal card. Supports both AJAX and standard form requests."""
    expire_overdue_cards()

    is_ajax = (
        request.is_json
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )

    if not validate_csrf():
        msg = "Invalid security token. Please refresh and try again."
        if is_ajax:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("dashboard"))

    card = MealCard.query.get(card_id)
    if not card:
        msg = "Meal card not found."
        if is_ajax:
            return jsonify({"success": False, "error": msg}), 404
        flash(msg, "danger")
        return redirect(url_for("dashboard"))

    # Auto-expire check
    if card.is_expired() or card.status == "expired":
        db.session.commit()
        msg = "This meal card has expired and can no longer be claimed."
        if is_ajax:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "danger")
        return redirect(url_for("dashboard"))

    # Rule: Prevent claiming your own cards
    if card.posted_by == current_user.id:
        msg = "You cannot claim your own meal card."
        if is_ajax:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "warning")
        return redirect(url_for("dashboard"))

    # Rule: Prevent claiming already claimed or completed cards
    if card.status != "available":
        msg = f"This meal card is already {card.status}."
        if is_ajax:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "warning")
        return redirect(url_for("dashboard"))

    # Process claim
    card.claimed_by = current_user.id
    card.claimed_at = datetime.utcnow()
    card.status = "claimed"
    if not card.claim_token:
        card.claim_token = secrets.token_urlsafe(32)

    db.session.commit()

    success_msg = f"You successfully claimed '{card.title}'!"
    if is_ajax:
        return jsonify({
            "success": True,
            "message": success_msg,
            "card_id": card.id,
            "claim_token": card.claim_token,
            "redirect_url": url_for("card_detail", card_id=card.id)
        })

    flash(success_msg, "success")
    return redirect(url_for("card_detail", card_id=card.id))


@app.route("/card/<int:card_id>")
@login_required
def card_detail(card_id):
    """View details of a specific meal card, including QR verification code."""
    card = MealCard.query.get_or_404(card_id)

    # Check if expired
    if card.is_expired():
        db.session.commit()

    # Generate QR code encoding the verification link
    qr_code_uri = None
    if card.claim_token:
        verify_url = url_for("verify_claim", claim_token=card.claim_token, _external=True)
        qr_code_uri = generate_qr_code(verify_url)

    return render_template("card_detail.html", card=card, qr_code=qr_code_uri)


@app.route("/meal-qr/<int:card_id>")
@login_required
def meal_qr_image(card_id):
    """Serve the original QR only to participants and a blurred preview to others."""
    card = MealCard.query.get_or_404(card_id)
    if not card.qr_image_filename:
        abort(404)

    is_participant = current_user.id in (card.posted_by, card.claimed_by)
    if is_participant:
        filename = card.qr_image_filename
    else:
        filename = f"{os.path.splitext(card.qr_image_filename)[0]}.blur.png"

    response = send_from_directory(QR_UPLOAD_FOLDER, filename, conditional=True)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@app.route("/verify/<claim_token>", methods=["GET", "POST"])
def verify_claim(claim_token):
    """Verify and complete a meal card claim via claim_token."""
    card = MealCard.query.filter_by(claim_token=claim_token).first()
    if not card:
        flash("Invalid or expired verification link.", "danger")
        return render_template("verify.html", card=None, error="Invalid token"), 404

    # Check if expired
    if card.is_expired():
        db.session.commit()

    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid security token. Please try again.", "danger")
            return redirect(url_for("verify_claim", claim_token=claim_token))

        if card.status == "completed":
            flash("This meal claim has already been verified and completed.", "info")
            return redirect(url_for("verify_claim", claim_token=claim_token))

        if card.status == "expired":
            flash("This meal card has expired.", "danger")
            return redirect(url_for("verify_claim", claim_token=claim_token))

        if card.status != "claimed":
            flash(f"Cannot verify card with status '{card.status}'.", "warning")
            return redirect(url_for("verify_claim", claim_token=claim_token))

        # Complete the handover
        card.status = "completed"
        card.completed_at = datetime.utcnow()
        db.session.commit()

        flash("Claim verified successfully! The food handover is complete.", "success")
        return redirect(url_for("verify_claim", claim_token=claim_token))

    return render_template("verify.html", card=card)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile page and update handler."""
    if request.method == "POST":
        if not validate_csrf():
            flash("Invalid security token. Please try again.", "danger")
            return redirect(url_for("profile"))

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_new_password = request.form.get("confirm_new_password", "")

        if not name or len(name) < 2 or len(name) > 100:
            flash("Name must be between 2 and 100 characters.", "danger")
            return redirect(url_for("profile"))

        email_regex = r"^[^@]+@[^@]+\.[^@]+$"
        if not email or not re.match(email_regex, email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("profile"))

        # Email change check
        if email != current_user.email:
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash("This email address is already in use by another account.", "danger")
                return redirect(url_for("profile"))
            current_user.email = email

        # Password update check
        if new_password:
            if not current_password:
                flash("Current password is required to set a new password.", "danger")
                return redirect(url_for("profile"))

            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "danger")
                return redirect(url_for("profile"))

            if len(new_password) < 6:
                flash("New password must be at least 6 characters long.", "danger")
                return redirect(url_for("profile"))

            if new_password != confirm_new_password:
                flash("New passwords do not match.", "danger")
                return redirect(url_for("profile"))

            current_user.set_password(new_password)

        current_user.name = name
        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    # Compute statistics for current user
    posted_count = MealCard.query.filter_by(posted_by=current_user.id).count()
    claimed_count = MealCard.query.filter_by(claimed_by=current_user.id).count()
    completed_count = MealCard.query.filter(
        (MealCard.posted_by == current_user.id) | (MealCard.claimed_by == current_user.id),
        MealCard.status == "completed"
    ).count()

    return render_template(
        "profile.html",
        user=current_user,
        posted_count=posted_count,
        claimed_count=claimed_count,
        completed_count=completed_count
    )


@app.route("/delete-card/<int:card_id>", methods=["POST"])
@login_required
def delete_card(card_id):
    """Delete a card (only allowed for the original poster)."""
    if not validate_csrf():
        flash("Invalid security token. Please try again.", "danger")
        return redirect(url_for("my_cards"))

    card = MealCard.query.get_or_404(card_id)

    if card.posted_by != current_user.id:
        abort(403)

    if card.status == "claimed":
        flash("Cannot delete a card that has already been claimed.", "warning")
    else:
        qr_filename = card.qr_image_filename
        db.session.delete(card)
        db.session.commit()
        if qr_filename:
            qr_stem = os.path.splitext(qr_filename)[0]
            for filename in (qr_filename, f"{qr_stem}.blur.png"):
                try:
                    os.remove(os.path.join(QR_UPLOAD_FOLDER, filename))
                except FileNotFoundError:
                    pass
        flash("Meal card deleted successfully.", "success")

    return redirect(request.referrer or url_for("my_cards"))


@app.route("/api/cards")
@login_required
def api_cards():
    """JSON API endpoint returning cards for dynamic client-side filtering."""
    expire_overdue_cards()

    status_filter = request.args.get("status", "available").strip().lower()
    meal_type = request.args.get("meal_type", "").strip().lower()
    search = request.args.get("search", "").strip()

    query = MealCard.query

    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    if meal_type and meal_type in ["breakfast", "lunch", "dinner", "snack"]:
        query = query.filter_by(meal_type=meal_type)

    if search:
        query = query.filter(
            (MealCard.title.ilike(f"%{search}%")) |
            (MealCard.description.ilike(f"%{search}%")) |
            (MealCard.pickup_location.ilike(f"%{search}%"))
        )

    cards = query.order_by(MealCard.expiry_time.asc()).all()
    return jsonify({
        "success": True,
        "count": len(cards),
        "cards": [c.to_dict() for c in cards]
    })


# -------------------------------------------------------------------------
# Error Handlers
# -------------------------------------------------------------------------

@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden_error(error):
    flash("You do not have permission to access that resource.", "danger")
    return redirect(url_for("dashboard"))


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("500.html"), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_meal_qr_column()
    app.run(debug=True)
