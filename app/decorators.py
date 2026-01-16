from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def permission_required(permission_slug):
    """
    Prüft, ob der aktuelle User die nötige Berechtigung (permission-Slug) hat.
    Falls nicht -> Redirect zur Home-Seite mit Fehler.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Eingeloggt?
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))

            # 2. Hat Permission? (Nutzt deine Logik aus User.has_permission)
            if not current_user.has_permission(permission_slug):
                flash("Zugriff verweigert! Dir fehlt die Berechtigung.", "danger")
                return redirect(url_for('main.home'))

            return f(*args, **kwargs)

        return decorated_function

    return decorator