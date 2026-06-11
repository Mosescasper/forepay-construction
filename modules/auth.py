"""
auth_module.py — ForePay Authentication Core
=============================================
Pure logic layer: environment loading, token helpers,
password hashing, admin detection, and route decorators.

NO Flask routes live here — import this into auth_api.py
(or any other module) to access authentication primitives.

Dependencies
------------
    pip install python-dotenv PyJWT bcrypt sqlalchemy
"""

import os
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional

from dotenv import load_dotenv
from flask import request, jsonify, session
from sqlalchemy.orm import Session

# ─────────────────────────────────────────────────────────────────────────────
# Environment
# ─────────────────────────────────────────────────────────────────────────────

load_dotenv()

ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
ADMIN_NAME:     str = os.getenv("ADMIN_NAME", "Admin User")
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "super-secret-key")

JWT_ALGORITHM    = "HS256"
JWT_EXPIRY_HOURS = 8   # default token lifetime


# ─────────────────────────────────────────────────────────────────────────────
# Password helpers
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """
    Hash a plain-text password with bcrypt.

    Usage (registration)
    --------------------
        hashed = hash_password("mySecret123")
        # store `hashed` in DB

    Returns
    -------
    str – bcrypt hash string, safe to store in the database.
    """
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Parameters
    ----------
    plain  : str – The raw password the user typed.
    hashed : str – The bcrypt hash stored in the database.

    Returns
    -------
    bool – True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ─────────────────────────────────────────────────────────────────────────────
# JWT helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_token(payload: dict, expires_in_hours: int = JWT_EXPIRY_HOURS) -> str:
    """
    Create a signed JWT token embedding *payload*.

    Parameters
    ----------
    payload          : dict – Claims to embed (e.g. id, username, role).
    expires_in_hours : int  – Token lifetime in hours (default 8).

    Returns
    -------
    str – Encoded JWT string.

    Example
    -------
        token = create_token({"id": 1, "role": "admin"})
    """
    data = payload.copy()
    data["iat"] = datetime.utcnow()
    data["exp"] = datetime.utcnow() + timedelta(hours=expires_in_hours)
    return jwt.encode(data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Parameters
    ----------
    token : str – The JWT string to decode.

    Returns
    -------
    dict – The decoded payload.

    Raises
    ------
    jwt.ExpiredSignatureError – Token has passed its expiry time.
    jwt.InvalidTokenError     – Token is malformed or tampered with.
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])


def extract_token_from_request() -> Optional[str]:
    """
    Pull a JWT from the current Flask request.

    Checks (in order):
      1. Authorization header  → 'Bearer <token>'
      2. Flask session         → session['access_token']
      3. Query parameter       → ?token=<token>

    Returns
    -------
    str | None – The raw token string, or None if not found.
    """
    # 1. Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]

    # 2. Session (server-side / cookie-based flows)
    if "access_token" in session:
        return session["access_token"]

    # 3. Query string (less secure, avoid in production)
    if request.args.get("token"):
        return request.args.get("token")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Admin detection
# ─────────────────────────────────────────────────────────────────────────────

def is_admin_credentials(username: str, password: str) -> bool:
    """
    Compare *username* and *password* against the .env admin account.

    Uses constant-time string comparison via `hmac.compare_digest`
    to guard against timing attacks.

    Parameters
    ----------
    username : str – Submitted email / username.
    password : str – Submitted plain-text password.

    Returns
    -------
    bool – True only if both match the .env admin values exactly.
    """
    import hmac
    user_match = hmac.compare_digest(username, ADMIN_USERNAME)
    pass_match = hmac.compare_digest(password, ADMIN_PASSWORD)
    return user_match and pass_match


# ─────────────────────────────────────────────────────────────────────────────
# Core authenticate function
# ─────────────────────────────────────────────────────────────────────────────

def authenticate_user(
    username: str,
    password: str,
    db: Optional[Session] = None,
) -> Optional[dict]:
    """
    Authenticate a user against the admin .env account or the database.

    Flow
    ----
    1. Check .env admin credentials (no DB hit needed).
    2. If a SQLAlchemy Session is provided, look up the user by email
       and verify the bcrypt password hash.
    3. Return a principal dict on success, None on failure.

    Parameters
    ----------
    username : str            – Email / username submitted.
    password : str            – Plain-text password submitted.
    db       : Session | None – SQLAlchemy session for DB users.

    Returns
    -------
    dict | None
        On success: {'id', 'username', 'name', 'role'}
        On failure: None

    Example
    -------
        principal = authenticate_user("admin@example.com", "secret", db)
        if principal:
            token = create_token(principal)
    """
    # ── Step 1: Admin (.env) ──────────────────────────────────────────────────
    if is_admin_credentials(username, password):
        return {
            "id":       "admin",
            "username": ADMIN_USERNAME,
            "name":     ADMIN_NAME,
            "role":     "admin",
        }

    # ── Step 2: Database users ────────────────────────────────────────────────
    if db is not None:
        try:
            from models import User  # adjust to your actual model path

            user: Optional[User] = (
                db.query(User).filter(User.email == username).first()
            )
            if user and verify_password(password, user.password_hash):
                return {
                    "id":       user.id,
                    "username": user.email,
                    "name":     getattr(user, "full_name", user.email),
                    "role":     getattr(user, "role", "user"),
                }
        except ImportError:
            pass  # models.py not available in this context

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Route decorators
# ─────────────────────────────────────────────────────────────────────────────

def token_required(f):
    """
    Decorator – protect a Flask route with JWT authentication.

    Attaches the decoded payload to `request.current_user`.
    Returns 401 if the token is missing, expired, or invalid.

    Usage
    -----
        @app.route("/profile")
        @token_required
        def profile():
            return jsonify(request.current_user)
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token_from_request()

        if not token:
            return jsonify({"error": "Authentication token is missing"}), 401

        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired, please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        request.current_user = payload
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    """
    Decorator – restrict a route to admin users only.

    Must be stacked BELOW @token_required so that
    `request.current_user` is already populated.

    Usage
    -----
        @app.route("/admin/users")
        @token_required
        @admin_required
        def list_users():
            ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(request, "current_user", {})
        if user.get("role") != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        return f(*args, **kwargs)

    return decorated


def get_db_session() -> Optional[Session]:
    """
    Attempt to obtain a SQLAlchemy DB session from the Flask app extensions.
    Returns None silently if extensions are not configured.

    Adjust the import path to match your project's `extensions.py`.
    """
    try:
        from extensions import db
        return db.session
    except ImportError:
        return None