"""
authy.py — Admin credential helper for ForePay.

This module loads admin credentials from .env and exposes helpers
for login validation and admin session routing.
"""

import os
import hmac
from dotenv import load_dotenv

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin User")


def is_admin_credentials(username: str, password: str) -> bool:
    """
    Return True when the submitted credentials match the .env admin account.
    """
    if not username or not password:
        return False

    return (
        hmac.compare_digest(username, ADMIN_USERNAME)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    )


def get_admin_principal() -> dict:
    """
    Return the admin principal metadata for session use.
    """
    return {
        "id": "admin",
        "username": ADMIN_USERNAME,
        "name": ADMIN_NAME,
        "role": "admin",
    }
