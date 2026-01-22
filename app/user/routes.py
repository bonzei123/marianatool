from flask import render_template, redirect, url_for, flash, request, Blueprint, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.extensions import db
from datetime import datetime
from app.models import User, Permission, Inspection, InspectionLog
from app.auth.forms import UpdateAccountForm
from app.utils import send_reset_email
from app.decorators import permission_required
from app.user import bp

# ==============================================================================
# SELF SERVICE (Mein Profil)
# ==============================================================================

@bp.route('/profile', methods=['GET'])
@login_required
def profile_view():
    """Zeigt das eigene Profil an."""
    form = UpdateAccountForm()
    form.username.data = current_user.username
    form.email.data = current_user.email
    return render_template('auth/profile.html', form=form)


@bp.route('/profile', methods=['POST'])
@login_required
def profile_update():
    """Aktualisiert das eigene Profil."""
    form = UpdateAccountForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Dein Profil wurde aktualisiert!', 'success')
        return redirect(url_for('user.profile_view'))

    return render_template('auth/profile.html', form=form)


# ==============================================================================
# USER MANAGEMENT (Für Admins/Manager)
# ==============================================================================

@bp.route('/manage', methods=['GET'])
@login_required
@permission_required('view_users')
def list_users():
    """Zeigt Liste aller User (Admin-View)."""

    # 1. Merken
    last_visit = current_user.last_users_visit

    # 2. Aktualisieren
    current_user.last_users_visit = datetime.utcnow()
    db.session.commit()

    # last_visit übergeben
    return render_template('admin/users.html',
                           users=User.query.all(),
                           all_permissions=Permission.query.all(),
                           last_visit=last_visit)


@bp.route('/manage/create', methods=['POST'])
@login_required
@permission_required('view_users')
def create_user():
    """Legt einen neuen User an."""
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form

    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash('User oder E-Mail existiert bereits', 'danger')
    else:
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password),
                        is_admin=is_admin)
        for s_id in request.form.getlist('permissions'):
            s = db.session.get(Permission, int(s_id))
            if s: new_user.permissions.append(s)
        db.session.add(new_user)
        db.session.commit()
        flash('User angelegt', 'success')
    return redirect(url_for('user.list_users'))


@bp.route('/manage/<int:user_id>/update', methods=['POST'])
@login_required
@permission_required('view_users')
def update_user(user_id):
    """Bearbeitet einen anderen User."""
    user = db.session.get(User, user_id)
    if not user:
        flash('User nicht gefunden', 'danger')
        return redirect(url_for('user.list_users'))

    # 1. Basisdaten
    user.is_admin = 'is_admin' in request.form

    # 2. Email Update
    new_email = request.form.get('email')
    if new_email and new_email != user.email:
        if not User.query.filter_by(email=new_email).first():
            user.email = new_email
        else:
            flash(f'E-Mail {new_email} ist schon vergeben!', 'warning')
            return redirect(url_for('user.list_users'))

    # 3. Permissions
    user.permissions = []
    for s_id in request.form.getlist('permissions'):
        s = db.session.get(Permission, int(s_id))
        if s: user.permissions.append(s)

    db.session.commit()
    flash(f'{user.username} aktualisiert', 'success')
    return redirect(url_for('user.list_users'))


@bp.route('/manage/<int:user_id>/delete', methods=['POST'])
@login_required
@permission_required('view_users')
def delete_user(user_id):
    """Löscht einen User, überträgt Projekte an Admin und schreibt Logs."""
    user = db.session.get(User, user_id)

    if user:
        # 1. Selbst-Löschung verhindern
        if user.id == current_user.id:
            flash('Du kannst dich nicht selbst löschen!', 'danger')
            return redirect(url_for('user.list_users'))

        # 2. Projekte retten (Reassign & Log)
        user_inspections = Inspection.query.filter_by(user_id=user.id).all()

        if user_inspections:
            count = len(user_inspections)
            for inspection in user_inspections:
                # LOG SCHREIBEN: Bevor wir den Besitzer ändern
                log = InspectionLog(
                    inspection_id=inspection.id,
                    user_id=current_user.id,  # Du (Admin) führst die Änderung durch
                    action='owner_change',
                    details=f"Besitzer gewechselt von '{user.username}' zu '{current_user.username}' (User gelöscht)."
                )
                db.session.add(log)

                # BESITZER ÄNDERN
                inspection.user_id = current_user.id

            flash(f'{count} Projekte wurden von {user.username} auf dich übertragen.', 'info')

        # 3. User löschen
        username_cache = user.username  # Name merken für Flash-Message
        db.session.delete(user)
        db.session.commit()

        flash(f'User "{username_cache}" wurde erfolgreich gelöscht.', 'success')

    else:
        flash('User nicht gefunden', 'warning')

    return redirect(url_for('user.list_users'))


@bp.route('/manage/<int:user_id>/reset-mail', methods=['POST'])
@login_required
@permission_required('view_users')
def trigger_reset(user_id):
    """Löst Passwort-Reset-Mail aus."""
    user = db.session.get(User, user_id)
    if user:
        send_reset_email(user)
        return jsonify({"success": True, "message": f"Reset-Link an {user.email} gesendet."})
    return jsonify({"success": False, "message": "User nicht gefunden"}), 404