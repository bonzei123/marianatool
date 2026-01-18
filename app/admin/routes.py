import os
from flask import render_template, redirect, url_for, request, flash, current_app, Blueprint
from flask_login import login_required
from app.extensions import db
from app.models import Permission, ImmoSetting
from app.decorators import permission_required
from app.admin import bp


def get_setting(key, default=""):
    s = db.session.get(ImmoSetting, key)
    return s.value if s else default


# --- GLOBAL SETTINGS ---

@bp.route('/settings', methods=['GET'])
@login_required
@permission_required('view_settings')
def global_settings_view():
    """Zeigt die globalen Einstellungen an."""
    bg_folder = os.path.join(current_app.root_path, 'static', 'img', 'backgrounds')
    if not os.path.exists(bg_folder):
        os.makedirs(bg_folder)

    email = get_setting('email_receiver', 'test@test.de')
    bg_files = [f for f in os.listdir(bg_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    all_permissions = Permission.query.order_by(Permission.name).all()

    return render_template('admin/settings.html',
                           email=email,
                           background_files=bg_files,
                           permissions=all_permissions)


@bp.route('/settings', methods=['POST'])
@login_required
@permission_required('view_settings')
def global_settings_save():
    """Speichert globale Einstellungen."""
    bg_folder = os.path.join(current_app.root_path, 'static', 'img', 'backgrounds')

    # 1. E-Mail Receiver
    if 'email_receiver' in request.form:
        s = db.session.get(ImmoSetting, 'email_receiver') or ImmoSetting(key='email_receiver')
        s.value = request.form['email_receiver']
        db.session.add(s)

    # 2. Globales Hintergrundbild Upload
    if 'background_image' in request.files:
        f = request.files['background_image']
        if f.filename:
            f.save(os.path.join(bg_folder, f.filename))
            flash("Globales Hintergrundbild hochgeladen.", "success")

    # 3. Permission Backgrounds Zuweisung
    counter = 0
    for key, value in request.form.items():
        if key.startswith('permission_') and key.endswith('_bg'):
            try:
                s_id = int(key.split('_')[1])
                permission = db.session.get(Permission, s_id)
                if permission:
                    permission.background_image = value if value else None
                    db.session.add(permission)
                    counter += 1
            except ValueError:
                continue

    db.session.commit()
    flash("Einstellungen gespeichert.", "success")
    return redirect(url_for('admin.global_settings_view'))