import os
import json
from datetime import datetime
from flask import render_template, redirect, url_for, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.immo import bp
from app.models import ImmoSection, Inspection
from app.decorators import permission_required
from app.extensions import db


# ==============================================================================
# VIEW ROUTES (GET)
# ==============================================================================

@bp.route('/immo')
@login_required
@permission_required('immo_user')
def immo_form():
    """Das Hauptformular."""
    return render_template('immo/immo_form.html')


@bp.route('/immo/overview', methods=['GET'])
@login_required
@permission_required('immo_user')
def overview():
    """Listenansicht aller Besichtigungen."""
    if current_user.has_permission('view_users') or current_user.is_admin:
        inspections = Inspection.query.order_by(Inspection.created_at.desc()).all()
    else:
        inspections = Inspection.query.filter_by(user_id=current_user.id).order_by(Inspection.created_at.desc()).all()

    return render_template('/immo/immo_overview.html', inspections=inspections)


@bp.route('/immo/files/<path:project>/<path:filename>')
@login_required
@permission_required('immo_user')
def uploaded_file(project, filename):
    """Sicherer Dateizugriff für Bilder/PDFs."""
    uploads = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(os.path.join(uploads, project), filename)


# ==============================================================================
# DATA / CONFIG ROUTES (GET)
# ==============================================================================

@bp.route('/immo/config')
@login_required
@permission_required('immo_user')
def get_config():
    """Lädt die Formular-Konfiguration (Fragen etc.)."""
    sections = ImmoSection.query.order_by(ImmoSection.order).all()
    data = []
    for sec in sections:
        questions = []
        for q in sec.questions:
            questions.append({
                "id": q.id,
                "label": q.label,
                "type": q.type,
                "width": q.width,
                "tooltip": q.tooltip,
                "options": json.loads(q.options_json) if q.options_json else [],
                "types": json.loads(q.types_json) if q.types_json else []
            })
        data.append({"id": sec.id, "title": sec.title, "is_expanded": sec.is_expanded, "content": questions})
    return jsonify(data)


# ==============================================================================
# ACTION ROUTES (POST)
# ==============================================================================

@bp.route('/immo/status/update', methods=['POST'])
@login_required
def update_status():
    """Ändert den Status (Ampel). Nur Admins/Manager."""
    # Expliziter Check, da permission_required decorator nur redirect macht,
    # wir hier aber JSON zurückgeben wollen bei Fehler.
    if not (current_user.is_admin or current_user.has_permission('immo_files_access')):
        return jsonify({'success': False, 'error': 'Keine Berechtigung'}), 403

    data = request.json
    inspection_id = data.get('id')
    new_status = data.get('status')

    inspection = db.session.get(Inspection, inspection_id)
    if not inspection:
        return jsonify({'success': False, 'error': 'Eintrag nicht gefunden'}), 404

    valid_statuses = [
        Inspection.STATUS_DRAFT, Inspection.STATUS_SUBMITTED,
        Inspection.STATUS_REVIEW, Inspection.STATUS_DONE,
        Inspection.STATUS_REJECTED
    ]

    if new_status not in valid_statuses:
        return jsonify({'success': False, 'error': 'Ungültiger Status'}), 400

    inspection.status = new_status
    db.session.commit()

    return jsonify({
        'success': True,
        'new_label': inspection.status_label,
        'new_color': inspection.status_color
    })


# ==============================================================================
# UPLOAD ROUTES (POST)
# ==============================================================================

@bp.route('/immo/upload/init', methods=['POST'])
@login_required
@permission_required('immo_user')
def upload_init():
    """Erstellt den Upload-Ordner."""
    data = request.json
    folder_name = secure_filename(data.get('folder_name'))
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(target_dir, exist_ok=True)
    return jsonify({"success": True, "path": folder_name})


@bp.route('/immo/upload/chunk', methods=['POST'])
@login_required
@permission_required('immo_user')
def upload_chunk():
    """Lädt einen Teil einer Datei hoch."""
    try:
        file = request.files['file']
        folder_name = secure_filename(request.form['folder'])
        filename = secure_filename(request.form['filename'])
        chunk_index = int(request.form['chunkIndex'])
        target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)

        mode = 'wb' if chunk_index == 0 else 'ab'
        with open(os.path.join(target_dir, filename), mode) as f:
            f.write(file.read())

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/immo/upload/complete', methods=['POST'])
@login_required
@permission_required('immo_user')
def upload_complete():
    """
    Finalisiert den Upload:
    - Speichert alle Metadaten & Antworten als JSON in der DB.
    - Setzt Status auf 'submitted'.
    """
    try:
        data = request.json

        # 1. Daten aus Frontend
        filename_pdf = secure_filename(data.get('filename'))
        folder_name = secure_filename(data.get('folder'))
        csc_name = data.get('csc_name', 'Unbekannt')
        immo_type = data.get('immo_type', 'einzel')
        form_responses = data.get('form_data', {})

        # 2. Dateisystem Scan: Was liegt wirklich im Ordner?
        upload_folder = current_app.config['UPLOAD_FOLDER']
        full_folder_path = os.path.join(upload_folder, folder_name)

        attached_files = []
        if os.path.exists(full_folder_path):
            attached_files = [f for f in os.listdir(full_folder_path)
                              if os.path.isfile(os.path.join(full_folder_path, f))]

        # 3. JSON Datensatz bauen (Source of Truth)
        full_json_record = {
            "meta": {
                "csc": csc_name,
                "type": immo_type,
                "date": datetime.utcnow().isoformat(),
                "uploaded_by": current_user.username
            },
            "form_responses": form_responses,
            "attachments": attached_files
        }

        # 4. DB Eintrag
        relative_path = os.path.join(folder_name, filename_pdf)

        inspection = Inspection(
            user_id=current_user.id,
            csc_name=csc_name,
            inspection_type=immo_type,
            status=Inspection.STATUS_SUBMITTED,
            pdf_path=relative_path,
            data_json=json.dumps(full_json_record)
        )

        db.session.add(inspection)
        db.session.commit()

        return jsonify({"success": True, "id": inspection.id})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Upload Save Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500