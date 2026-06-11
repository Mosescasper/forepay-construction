"""
authy.py — Authentication blueprint.

This file provides the logout endpoint and is the place to add
shared auth API routes for the app.
"""

from flask import Blueprint, session, redirect, url_for

authy_bp = Blueprint("authy", __name__, url_prefix="/authy")


@authy_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))
