from typing import Optional, List
from flask import current_app
from sqlalchemy.exc import IntegrityError
from database import db
from models.user import User   # adjust import path
from models.profile import Profile
from datetime import datetime


class ProfileService:
    """
    Service class to handle profile-related operations.
    """

    # ---------------------------------------------------------
    # SERIALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def serialize_one(profile: Profile) -> dict:
        """
        Serialize a profile safely.
        """
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "bio": profile.bio,
            "address": profile.address,
            "city": profile.city,
            "country": profile.country,
            "date_of_birth": profile.date_of_birth,
            "website": profile.website,
            "linkedin_url": profile.linkedin_url,
            "twitter_handle": profile.twitter_handle,
            "is_public": profile.is_public,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }

    def serialize_many(self, profiles: List[Profile]) -> List[dict]:
        return [self.serialize_one(profile) for profile in profiles]

    # ---------------------------------------------------------
    # CREATE PROFILE
    # ---------------------------------------------------------

    def create_profile(self, user_id: int, **kwargs) -> dict:
        """
        Create profile for a user (1-to-1).
        """

        # Ensure user exists
        user = User.query.get(user_id)
        if not user:
            return {"error": "User not found"}

        # Ensure profile does not already exist
        existing = Profile.query.filter_by(user_id=user_id).first()
        if existing:
            return {"error": "Profile already exists for this user"}

        try:
            profile = Profile(
                user_id=user_id,
                bio=kwargs.get("bio"),
                address=kwargs.get("address"),
                city=kwargs.get("city"),
                country=kwargs.get("country"),
                date_of_birth=kwargs.get("date_of_birth"),
                website=kwargs.get("website"),
                linkedin_url=kwargs.get("linkedin_url"),
                twitter_handle=kwargs.get("twitter_handle"),
                is_public=kwargs.get("is_public", True),
            )

            db.session.add(profile)
            db.session.commit()

            return self.serialize_one(profile)

        except IntegrityError:
            db.session.rollback()
            return {"error": "Profile already exists"}

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[CreateProfile] {str(e)}")
            return {"error": "Failed to create profile"}

    # ---------------------------------------------------------
    # GET PROFILE
    # ---------------------------------------------------------

    def get_by_id(self, profile_id: int) -> Optional[dict]:
        profile = Profile.query.get(profile_id)
        if not profile:
            return None
        return self.serialize_one(profile)

    def get_by_user_id(self, user_id: int, public_only: bool = False) -> Optional[dict]:
        """
        Retrieve profile by user ID.
        If public_only=True → only return if profile.is_public is True.
        """
        profile = Profile.query.filter_by(user_id=user_id).first()

        if not profile:
            return None

        if public_only and not profile.is_public:
            return None

        return self.serialize_one(profile)

    def get_all_profiles(self, public_only: bool = False) -> List[dict]:
        query = Profile.query

        if public_only:
            query = query.filter_by(is_public=True)

        profiles = query.order_by(Profile.created_at.desc()).all()
        return self.serialize_many(profiles)

    # ---------------------------------------------------------
    # UPDATE PROFILE
    # ---------------------------------------------------------

    def update_profile(self, user_id: int, **kwargs) -> dict:
        """
        Update profile using user_id.
        """
        profile = Profile.query.filter_by(user_id=user_id).first()

        if not profile:
            return {"error": "Profile not found"}

        try:
            allowed_fields = [
                "bio", "address", "city", "country",
                "date_of_birth", "website",
                "linkedin_url", "twitter_handle",
                "is_public"
            ]

            for field in allowed_fields:
                if field in kwargs:
                    setattr(profile, field, kwargs[field])

            profile.updated_at = datetime.utcnow()

            db.session.commit()

            return self.serialize_one(profile)

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[UpdateProfile] {str(e)}")
            return {"error": "Failed to update profile"}

    # ---------------------------------------------------------
    # DELETE PROFILE
    # ---------------------------------------------------------

    def delete_profile(self, user_id: int) -> dict:
        profile = Profile.query.filter_by(user_id=user_id).first()

        if not profile:
            return {"error": "Profile not found"}

        try:
            db.session.delete(profile)
            db.session.commit()
            return {"message": "Profile deleted successfully"}

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[DeleteProfile] {str(e)}")
            return {"error": "Failed to delete profile"}

    # ---------------------------------------------------------
    # TOGGLE PUBLIC VISIBILITY
    # ---------------------------------------------------------

    def toggle_public_status(self, user_id: int, is_public: bool) -> dict:
        profile = Profile.query.filter_by(user_id=user_id).first()

        if not profile:
            return {"error": "Profile not found"}

        try:
            profile.is_public = is_public
            profile.updated_at = datetime.utcnow()
            db.session.commit()

            return {
                "user_id": user_id,
                "is_public": profile.is_public,
                "message": f"Profile visibility set to {'Public' if is_public else 'Private'}"
            }

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"[ToggleProfileVisibility] {str(e)}")
            return {"error": "Failed to update visibility"}
