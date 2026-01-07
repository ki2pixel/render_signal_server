from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, login_user, logout_user, current_user

# Phase 3: Utiliser AuthService au lieu de auth.user
from services import AuthService, ConfigService, MagicLinkService

bp = Blueprint("dashboard", __name__)

# Phase 3: Initialiser AuthService pour ce module
_config_service = ConfigService()
_auth_service = AuthService(_config_service)
_magic_link_service = MagicLinkService.get_instance()


def _complete_login(username: str, next_page: str | None):
    user_obj = _auth_service.create_user(username)
    login_user(user_obj)
    return redirect(next_page or url_for("dashboard.serve_dashboard_main"))


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

    error_message = request.args.get("error")

    if request.method == "POST":
        magic_token = request.form.get("magic_token")
        if magic_token:
            success, message = _magic_link_service.consume_token(magic_token.strip())
            if success:
                next_page = request.args.get("next")
                return _complete_login(message, next_page)
            error_message = message or "Token invalide."
        else:
            username = request.form.get("username")
            password = request.form.get("password")
            user_obj = _auth_service.create_user_from_credentials(username, password)
            if user_obj is not None:
                next_page = request.args.get("next")
                return _complete_login(user_obj.id, next_page)
            error_message = "Identifiants invalides."

    return render_template("login.html", url_for=url_for, error=error_message)


@bp.route("/login/magic/<token>", methods=["GET"])
def consume_magic_link_token(token: str):
    success, message = _magic_link_service.consume_token(token)
    if not success:
        return redirect(url_for("dashboard.login", error=message))
    next_page = request.args.get("next")
    return _complete_login(message, next_page)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("dashboard.login"))
