import os
# NEU: secure_filename importieren
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, request, flash, current_app, Blueprint
from flask_login import login_required
from app.extensions import db
from app.models import Permission, ImmoSetting, DashboardTile
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

    # Tiles laden und sortieren
    all_permissions = Permission.query.order_by(Permission.id).all()
    all_tiles = DashboardTile.query.order_by(DashboardTile.order).all()

    return render_template('admin/settings.html',
                           email=email,
                           background_files=bg_files,
                           permissions=all_permissions,
                           tiles=all_tiles)


@bp.route('/settings', methods=['POST'])
@login_required
@permission_required('view_settings')
def global_settings_save():
    """Speichert NUR NOCH die Basis-Einstellungen (E-Mail)."""

    # 1. E-Mail Receiver
    if 'email_receiver' in request.form:
        s = db.session.get(ImmoSetting, 'email_receiver') or ImmoSetting(key='email_receiver')
        s.value = request.form['email_receiver']
        db.session.add(s)

    # HIER WURDE DER HINTERGRUND-CODE ENTFERNT (jetzt in save_backgrounds)

    db.session.commit()
    flash("Basiseinstellungen gespeichert.", "success")
    return redirect(url_for('admin.global_settings_view'))


# --- NEU: HINTERGRÜNDE & DESIGN SPEICHERN ---

@bp.route('/settings/backgrounds/save', methods=['POST'])
@login_required
@permission_required('view_settings')
def save_backgrounds():
    """Speichert Hintergrundbilder (Upload & Zuweisung)."""
    bg_folder = os.path.join(current_app.root_path, 'static', 'img', 'backgrounds')

    # 1. Neuer Upload?
    if 'background_image' in request.files:
        f = request.files['background_image']
        if f and f.filename:
            filename = secure_filename(f.filename)
            f.save(os.path.join(bg_folder, filename))
            flash(f"Bild '{filename}' erfolgreich hochgeladen.", "success")

    # 2. Zuweisungen zu Permissions speichern
    permissions = Permission.query.all()
    for perm in permissions:
        # Der Name des Select-Felds im Modal ist permission_{id}_bg
        field_name = f"permission_{perm.id}_bg"

        if field_name in request.form:
            selected_bg = request.form.get(field_name)
            # Wenn "Standard" gewählt ist (leer), setzen wir es auf None
            if selected_bg == "":
                perm.background_image = None
            else:
                perm.background_image = selected_bg

    db.session.commit()
    flash("Design-Einstellungen aktualisiert.", "success")
    return redirect(url_for('admin.global_settings_view'))


# --- TILES SPEICHERN ---

@bp.route('/settings/tiles/save', methods=['POST'])
@login_required
@permission_required('view_settings')
def save_tiles():
    """Speichert Änderungen an den Dashboard Kacheln."""
    tiles = DashboardTile.query.all()

    for tile in tiles:
        prefix = f"tile_{tile.id}_"

        # Daten aus Formular holen
        if f"{prefix}title" in request.form:
            tile.title = request.form.get(f"{prefix}title")
            tile.icon = request.form.get(f"{prefix}icon")
            tile.color_hex = request.form.get(f"{prefix}color")
            tile.route_name = request.form.get(f"{prefix}route")

            # Reihenfolge (Integer)
            try:
                tile.order = int(request.form.get(f"{prefix}order", 0))
            except ValueError:
                pass

            # Permission Zuweisung
            perm_id_str = request.form.get(f"{prefix}perm")
            if perm_id_str and perm_id_str != "None":
                tile.required_permission_id = int(perm_id_str)
            else:
                tile.required_permission_id = None

    db.session.commit()
    flash("Dashboard-Kacheln aktualisiert.", "success")
    return redirect(url_for('admin.global_settings_view'))


# --- PERMISSIONS SPEICHERN ---

@bp.route('/settings/permissions/save', methods=['POST'])
@login_required
@permission_required('view_settings')
def save_permissions():
    """Speichert kosmetische Änderungen an den Permissions."""
    permissions = Permission.query.all()

    for perm in permissions:
        prefix = f"perm_{perm.id}_"

        if f"{prefix}name" in request.form:
            perm.name = request.form.get(f"{prefix}name")
            perm.description = request.form.get(f"{prefix}description")
            perm.icon = request.form.get(f"{prefix}icon")
            # Slug ändern wir NICHT, da der Code darauf basiert!

    db.session.commit()
    flash("Berechtigungs-Texte aktualisiert.", "success")
    return redirect(url_for('admin.global_settings_view'))