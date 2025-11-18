from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, login_user, logout_user, current_user

# Phase 3: Utiliser AuthService au lieu de auth.user
from services import AuthService, ConfigService

bp = Blueprint("dashboard", __name__)

# Phase 3: Initialiser AuthService pour ce module
_config_service = ConfigService()
_auth_service = AuthService(_config_service)


@bp.route("/")
@login_required
def serve_dashboard_main():
    # Keep same template rendering as legacy
    return render_template("dashboard.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    # If already authenticated, go to dashboard
    if current_user and getattr(current_user, "is_authenticated", False):
        return redirect(url_for("dashboard.serve_dashboard_main"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Phase 3: Utiliser AuthService
        user_obj = _auth_service.create_user_from_credentials(username, password)
        if user_obj is not None:
            login_user(user_obj)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.serve_dashboard_main"))
        return render_template("login.html", error="Identifiants invalides.")

    return render_template("login.html", url_for=url_for)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("dashboard.login"))
