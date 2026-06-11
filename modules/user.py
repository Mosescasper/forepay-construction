from typing import List, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from flask import current_app
from database import db
from models.user import User  # adjust import path if needed
from datetime import datetime
from PIL import Image
from io import BytesIO


class UserService:
    """
    Service class to handle user-related operations.
    """

    # ---------------------------------------------------------
    # SERIALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def serialize_one(user: User) -> dict:
        """
        Serialize a single user safely (exclude password_hash).
        """
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "avatar": user.avatar,
            "phone": user.phone,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login": user.last_login,
            "email_verified": user.email_verified,
        }

    def serialize_many(self, users: List[User]) -> List[dict]:
        return [self.serialize_one(user) for user in users]

    # ---------------------------------------------------------
    # CREATE USER
    # ---------------------------------------------------------

    def create_user(self, **kwargs) -> dict:
        """
        Create a new user with hashed password.
        """
        try:
            password = kwargs.pop("password", None)
            if not password:
                return {"error": "Password is required"}

            user = User(
                name=kwargs.get("name"),
                email=kwargs.get("email"),
                password_hash=generate_password_hash(password),
                role=kwargs.get("role", "user"),
                status=kwargs.get("status", "active"),
                avatar=kwargs.get("avatar"),
                phone=kwargs.get("phone"),
            )

            db.session.add(user)
            db.session.commit()

            return self.serialize_one(user)

        except IntegrityError:
            db.session.rollback()
            return {"error": "Email already exists"}

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[CreateUser] {str(e)}")
            return {"error": "Failed to create user"}

    # ---------------------------------------------------------
    # GET USER
    # ---------------------------------------------------------

    def get_by_id(self, user_id: int) -> Optional[dict]:
        user = User.query.get(user_id)
        if not user:
            return None
        return self.serialize_one(user)

    def get_by_email(self, email: str) -> Optional[User]:
        return User.query.filter_by(email=email).first()

    def get_all_users(self) -> List[dict]:
        users = User.query.order_by(User.created_at.desc()).all()
        return self.serialize_many(users)

    # ---------------------------------------------------------
    # UPDATE USER
    # ---------------------------------------------------------

    def update_user(self, user_id: int, **kwargs) -> dict:
        user = User.query.get(user_id)

        if not user:
            return {"error": "User not found"}

        try:
            if "name" in kwargs:
                user.name = kwargs["name"]

            if "email" in kwargs:
                user.email = kwargs["email"]

            if "role" in kwargs:
                user.role = kwargs["role"]

            if "phone" in kwargs:
                user.phone = kwargs["phone"]

            if "avatar" in kwargs:
                user.avatar = kwargs["avatar"]

            if "password" in kwargs and kwargs["password"]:
                user.password_hash = generate_password_hash(kwargs["password"])

            user.updated_at = datetime.utcnow()

            db.session.commit()

            return self.serialize_one(user)

        except IntegrityError:
            db.session.rollback()
            return {"error": "Email already exists"}

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[UpdateUser] {str(e)}")
            return {"error": "Failed to update user"}

    # ---------------------------------------------------------
    # UPDATE STATUS
    # ---------------------------------------------------------

    def update_status(self, user_id: int, status: str) -> dict:
        """
        Update user status (active / inactive / suspended).
        """
        user = User.query.get(user_id)

        if not user:
            return {"error": "User not found"}

        try:
            user.status = status
            user.updated_at = datetime.utcnow()
            db.session.commit()

            return {
                "id": user.id,
                "status": user.status,
                "message": f"User status updated to {status}"
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[UpdateUserStatus] {str(e)}")
            return {"error": "Failed to update status"}

    # ---------------------------------------------------------
    # AUTHENTICATION HELPERS
    # ---------------------------------------------------------

    def verify_password(self, email: str, password: str) -> bool:
        """
        Validate login credentials.
        """
        user = self.get_by_email(email)
        if not user:
            return False

        if check_password_hash(user.password_hash, password):
            user.last_login = datetime.utcnow()
            db.session.commit()
            return True

        return False

    # ---------------------------------------------------------
    # DELETE USER (Optional Soft Delete)
    # ---------------------------------------------------------

    def deactivate_user(self, user_id: int) -> dict:
        """
        Soft delete (mark as inactive).
        """
        return self.update_status(user_id, "inactive")

    # ---------------------------------------------------------
    # IMAGE RESIZE (Avatar)
    # ---------------------------------------------------------

    @staticmethod
    def resize_avatar_if_needed(image_file, max_size=(300, 300)):
        """
        Resize avatar to fit within max_size.
        """
        image = Image.open(image_file)
        image.thumbnail(max_size, Image.LANCZOS)

        buffer = BytesIO()
        image_format = image.format or "JPEG"
        image.save(buffer, format=image_format)
        buffer.seek(0)

        image_file.stream = buffer
        image_file.stream.seek(0)
