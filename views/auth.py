"""
views/auth.py

Authentication endpoints for the Forepay Construction Payroll App.

Endpoints:
  POST /auth/register       – register a new foreman account
  POST /auth/login          – login → receive JWT access token
  POST /auth/verify-otp     – verify email OTP → confirm account / 2FA
  POST /auth/resend-otp     – resend OTP to registered email
  GET  /auth/me             – return current authenticated foreman's profile
  POST /auth/logout         – client-side token invalidation (stateless note)

Auth flow:
  1. Foreman registers (POST /auth/register) → OTP sent to email
  2. Foreman verifies OTP (POST /auth/verify-otp) → account activated
  3. Foreman logs in (POST /auth/login) → receives JWT
  4. All protected routes require: Authorization: Bearer <token>
"""

from datetime import datetime, timedelta
import os
import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db          # your DB session dependency
from models import User              # SQLAlchemy User model
from utils.email import send_otp_email  # your email utility

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Security config ───────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", 10))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Kamau",
                "email": "john@example.com",
                "phone": "0712345678",
                "password": "StrongPass123"
            }
        }


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str


class ResendOTPRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    foreman: dict


class ForemanProfile(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode JWT and return payload. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_foreman(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency injected into protected routes.
    Decodes the JWT and returns the authenticated User object.
    """
    payload = decode_token(token)
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")
    return user


def get_admin_only(current_user: User = Depends(get_current_foreman)) -> User:
    """Dependency for admin-only routes."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Register a new foreman account.

    - Validates that email and phone are not already taken.
    - Hashes the password with bcrypt.
    - Generates a 6-digit OTP and emails it to the foreman.
    - Account is inactive until OTP is verified.

    Returns: confirmation message + masked email.
    """
    # Duplicate checks
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email is already registered.")
    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status_code=409, detail="Phone number is already registered.")

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    # Determine role — first user becomes admin, rest are foremen
    role = "admin" if db.query(User).count() == 0 else "foreman"

    # Generate OTP
    otp = generate_otp()
    otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

    user = User(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=False,          # activated after OTP verification
        otp_code=otp,
        otp_expires_at=otp_expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Send OTP email
    try:
        send_otp_email(payload.email, payload.name, otp)
    except Exception as e:
        db.delete(user)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")

    local, domain = payload.email.split("@")
    masked = f"{local[0]}***@{domain}"

    return {
        "message": "Account created. Check your email for the OTP to activate your account.",
        "email": masked,
        "role": role,
    }


@router.post("/verify-otp")
def verify_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Verify the OTP sent during registration or 2FA login.

    - Checks OTP validity and expiry.
    - Activates the account on success.
    - Returns a JWT access token so the foreman is immediately logged in.

    Returns: { access_token, token_type, foreman }
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")

    if not user.otp_code or not user.otp_expires_at:
        raise HTTPException(status_code=400, detail="No OTP was requested for this account.")

    if datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    if user.otp_code != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    # Activate account and clear OTP
    user.is_active = True
    user.otp_code = None
    user.otp_expires_at = None
    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token({"user_id": user.id, "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "foreman": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
        },
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Log in with email and password.

    - Validates credentials.
    - Enforces account lockout after 5 failed attempts (15-minute cooldown).
    - On success, returns JWT access token directly (no OTP step post-registration).

    Returns: { access_token, token_type, foreman }
    """
    user = db.query(User).filter(User.email == payload.email).first()

    # Generic error to avoid user enumeration
    invalid_err = HTTPException(status_code=401, detail="Invalid email or password.")

    if not user:
        raise invalid_err

    # Account lockout check
    if user.locked_until and datetime.utcnow() < user.locked_until:
        raise HTTPException(
            status_code=429,
            detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is not activated. Please verify your email OTP.")

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db.commit()
        remaining = max(5 - user.failed_login_attempts, 0)
        raise HTTPException(
            status_code=401,
            detail=f"Invalid email or password. {remaining} attempt(s) left before account is locked.",
        )

    # Reset failed attempts on success
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token({"user_id": user.id, "role": user.role})

    return {
        "access_token": token,
        "token_type": "bearer",
        "foreman": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
        },
    }


@router.post("/resend-otp")
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    """
    Resend a fresh OTP to the foreman's registered email.

    - Works for both new accounts (not yet activated) and locked/expired OTPs.
    - Always returns a vague success message to prevent user enumeration.

    Returns: { message }
    """
    user = db.query(User).filter(User.email == payload.email).first()

    # Vague response regardless of whether user exists
    success_msg = {"message": "If that email is registered, a new OTP has been sent."}

    if not user:
        return success_msg

    otp = generate_otp()
    user.otp_code = otp
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    db.commit()

    try:
        send_otp_email(user.email, user.name, otp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP: {str(e)}")

    return success_msg


@router.get("/me", response_model=ForemanProfile)
def get_me(current_user: User = Depends(get_current_foreman)):
    """
    Return the profile of the currently authenticated foreman.

    Requires: Authorization: Bearer <token>
    Returns: ForemanProfile
    """
    return ForemanProfile(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )


@router.post("/logout")
def logout():
    """
    Logout endpoint (stateless).

    JWTs are stateless — the client must discard the token on their side.
    For full server-side invalidation, implement a token blacklist using
    Redis or a DB table of revoked JTIs (JWT IDs).

    Returns: { message }
    """
    return {"message": "Logged out successfully. Please discard your token on the client."}