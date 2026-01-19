import os
import json
from werkzeug.utils import secure_filename
from flask import render_template, redirect, url_for, request, flash, current_app, Blueprint
from flask_login import login_required
from app.extensions import db
from app.models import Permission, ImmoSetting, DashboardTile, ImmoQuestion
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


def perform_question_import():
    """
    Liest static/questions.json und aktualisiert die DB.
    Gibt (Success_Bool, Message_String) zurück.
    """
    json_path = os.path.join(current_app.root_path, 'static', 'questions.json')

    if not os.path.exists(json_path):
        return False, "Datei questions.json nicht gefunden!"

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Optional: Alles löschen vor Import?
        # db.session.query(ImmoQuestion).delete()
        # db.session.query(ImmoSection).delete()
        # Besser: Update or Create (Upsert)

        section_count = 0
        question_count = 0

        for sec_idx, sec_data in enumerate(data):
            # 1. Sektion anlegen/updaten
            # Falls ID leer ist, generieren wir eine (sollte im JSON aber da sein)
            sec_id = sec_data.get('id', f"sec_{sec_idx}")

            section = db.session.get(ImmoSection, sec_id)
            if not section:
                section = ImmoSection(id=sec_id)
                db.session.add(section)

            section.title = sec_data.get('title', 'Unbenannt')
            section.order = sec_idx  # Reihenfolge aus JSON übernehmen

            section_count += 1

            # 2. Fragen der Sektion verarbeiten
            if 'content' in sec_data:
                for q_idx, q_data in enumerate(sec_data['content']):
                    q_id = q_data.get('id')

                    # Überspringe Fragen ohne ID (oder generiere eine, falls nötig)
                    if not q_id:
                        # Fallback für Header/Infos ohne ID in deinem JSON
                        q_id = f"{sec_id}_q_{q_idx}"

                    question = db.session.get(ImmoQuestion, q_id)
                    if not question:
                        question = ImmoQuestion(id=q_id)
                        db.session.add(question)

                    # Felder mappen
                    question.section_id = sec_id
                    question.label = q_data.get('label')
                    question.type = q_data.get('type')
                    question.width = q_data.get('width', 'full')
                    question.tooltip = q_data.get('tooltip', '')
                    question.order = q_idx
                    question.is_required = q_data.get('required', False)
                    question.is_metadata = q_data.get('metadata', False)

                    # JSON Listen konvertieren
                    # options -> options_json
                    options_list = q_data.get('options', [])
                    question.options_json = json.dumps(options_list) if options_list else None

                    # types -> types_json
                    types_list = q_data.get('types', [])
                    question.types_json = json.dumps(types_list) if types_list else None

                    question_count += 1

        db.session.commit()
        return True, f"Import erfolgreich: {section_count} Sektionen, {question_count} Fragen."

    except Exception as e:
        db.session.rollback()
        return False, f"Fehler beim Import: {str(e)}"


# --- ROUTE FÜR DEN BUTTON ---
@bp.route('/settings/questions/import', methods=['POST'])
@login_required
@permission_required('view_settings')
def import_questions_route():
    """Trigger für den Import via Admin-Panel."""
    success, message = perform_question_import()

    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for('admin.global_settings_view'))
