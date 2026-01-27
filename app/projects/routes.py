import os
import json
import csv
import io
import shutil
from flask import make_response
from datetime import datetime
from flask import render_template, request, jsonify, current_app, url_for, send_from_directory, Blueprint, flash, \
    redirect
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models import ImmoSection, Inspection, InspectionLog, ImmoQuestion
from app.decorators import permission_required
from app.projects import bp
from app.pdf_generator import PdfGenerator


# ==============================================================================
# VIEW ROUTES (GET)
# ==============================================================================

@bp.route('/', methods=['GET'])
@login_required
@permission_required('immo_user')
def overview():
    """Liste der AKTIVEN Projekte (is_archived = False)."""
    last_visit = current_user.last_projects_visit
    current_user.last_projects_visit = datetime.utcnow()
    db.session.commit()

    query = Inspection.query

    if not (current_user.has_permission('view_users') or current_user.is_admin):
        query = query.filter_by(user_id=current_user.id)

    # NEUER FILTER:
    query = query.filter_by(is_archived=False)

    inspections = query.order_by(Inspection.created_at.desc()).all()

    return render_template('immo/immo_overview.html',
                           inspections=inspections,
                           last_visit=last_visit,
                           view_type='active')


@bp.route('/archive', methods=['GET'])
@login_required
@permission_required('immo_user')
def archive_view():
    """Liste der ARCHIVIERTEN Projekte (is_archived = True)."""
    query = Inspection.query

    if not (current_user.has_permission('view_users') or current_user.is_admin):
        query = query.filter_by(user_id=current_user.id)

    # NEUER FILTER:
    query = query.filter_by(is_archived=True)

    inspections = query.order_by(Inspection.updated_at.desc()).all()

    return render_template('immo/immo_overview.html',
                           inspections=inspections,
                           last_visit=None,
                           view_type='archive')


# --- FILES ROUTEN ---

@bp.route('/files', methods=['GET'])
@login_required
@permission_required('immo_files_access')
def files_overview():
    """Übersicht aller Projekt-Ordner (ehemals Admin)."""
    projects = []
    up_folder = current_app.config['UPLOAD_FOLDER']
    if os.path.exists(up_folder):
        items = os.listdir(up_folder)
        items.sort(key=lambda x: os.path.getmtime(os.path.join(up_folder, x)), reverse=True)
        for name in items:
            path = os.path.join(up_folder, name)
            if os.path.isdir(path):
                files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                size = sum(os.path.getsize(os.path.join(path, f)) for f in files) / (1024 * 1024)
                projects.append({
                    "name": name,
                    "count": len(files),
                    "size": round(size, 2),
                    "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d.%m.%Y %H:%M')
                })
    return render_template('immo/immo_files.html', projects=projects)


@bp.route('/files/<path:project_name>', methods=['GET'])
@login_required
@permission_required('immo_files_access')
def file_browser(project_name):
    """Inhalt eines spezifischen Projektordners anzeigen."""
    safe_name = secure_filename(project_name)
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_name)
    files = []
    if os.path.exists(target_dir):
        for f in os.listdir(target_dir):
            fp = os.path.join(target_dir, f)
            if os.path.isfile(fp):
                is_img = f.lower().endswith(('.png', '.jpg', '.jpeg'))
                is_vid = f.lower().endswith(('.mp4', '.mov'))
                files.append({
                    "name": f,
                    "size": round(os.path.getsize(fp) / 1024 / 1024, 2),
                    "is_img": is_img,
                    "is_vid": is_vid
                })
    return render_template('immo/immo_project_view.html', project=safe_name, files=files)


@bp.route('/download/<path:project>/<path:filename>', methods=['GET'])
@login_required
@permission_required('immo_user')
def download_file(project, filename):
    """Sicherer Download/Anzeige von Dateien."""
    uploads = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(os.path.join(uploads, project), filename)


# ==============================================================================
# DATA / API ROUTES
# ==============================================================================

@bp.route('/config', methods=['GET'])
@login_required
@permission_required('immo_user')
def get_form_config():
    """Lädt die Formular-Struktur (JSON)."""
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
                "width_tablet": q.width_tablet,
                "width_mobile": q.width_mobile,
                "tooltip": q.tooltip,
                "is_required": q.is_required,
                "is_metadata": q.is_metadata,
                "is_print": q.is_print,
                "options": json.loads(q.options_json) if q.options_json else [],
                "types": json.loads(q.types_json) if q.types_json else []
            })
        data.append({"id": sec.id, "title": sec.title, "is_expanded": sec.is_expanded, "content": questions})
    return jsonify(data)


@bp.route('/upload/init', methods=['POST'])
@login_required
@permission_required('immo_user')
def upload_init():
    """Erstellt Ordner für Upload."""
    data = request.json
    folder_name = secure_filename(data.get('folder_name'))
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(target_dir, exist_ok=True)
    return jsonify({"success": True, "path": folder_name})


@bp.route('/upload/chunk', methods=['POST'])
@login_required
@permission_required('immo_user')
def upload_chunk():
    """Verarbeitet Datei-Chunks."""
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


@bp.route('/create_quick', methods=['POST'])
@login_required
@permission_required('immo_user')
def create_quick():
    # 1. Onboarding Check
    if not current_user.onboarding_confirmed_at:
        return jsonify({'success': False, 'error': 'REDIRECT_ONBOARDING', 'url': url_for('onboarding.start')}), 403
    try:
        data = request.json
        csc_name = data.get('csc_name', 'Unbekannt')
        immo_type = data.get('immo_type', 'einzel')

        # 1. Ordnernamen
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        safe_csc = secure_filename(csc_name.replace(" ", "_")) or "Project"
        folder_name = f"{safe_csc}_{ts}"

        upload_folder = current_app.config['UPLOAD_FOLDER']
        full_folder_path = os.path.join(upload_folder, folder_name)
        os.makedirs(full_folder_path, exist_ok=True)

        # 2. STRUKTUR SNAPSHOT ERSTELLEN (NEU!)
        # Wir frieren den aktuellen Stand des Formulars ein
        form_snapshot = get_current_form_structure_as_dict()

        full_json_record = {
            "meta": {
                "csc": csc_name,
                "type": immo_type,
                "date": datetime.utcnow().isoformat(),
                "uploaded_by": current_user.username
            },
            "form_config": form_snapshot,  # <--- HIER GESPEICHERT
            "form_responses": {},
            "attachments": []
        }

        inspection = Inspection(
            user_id=current_user.id,
            csc_name=csc_name,
            inspection_type=immo_type,
            status=Inspection.STATUS_DRAFT,
            pdf_path=os.path.join(folder_name, ""),
            data_json=json.dumps(full_json_record)
        )
        db.session.add(inspection)
        db.session.commit()

        return jsonify({"success": True, "id": inspection.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# VERALTET / ABGESÄGT
# @bp.route('/submit', methods=['POST'])
# ...


@bp.route('/<int:inspection_id>/generate_pdf', methods=['GET'])
@login_required
def generate_and_download_pdf(inspection_id):
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection: return render_template('errors/404.html'), 404

    # Rechte Check ... (hier gekürzt)
    if not (current_user.is_admin or current_user.has_permission(
            'immo_files_access') or inspection.user_id == current_user.id):
        return render_template('errors/403.html'), 403

    try:
        # ENTSCHEIDUNG: Snapshot oder Live?
        sections_data = []

        # 1. Snapshot prüfen
        if inspection.data_json:
            try:
                d = json.loads(inspection.data_json)
                if d.get('form_config'):
                    sections_data = d.get('form_config')
            except:
                pass

        # 2. Fallback: Live Daten holen und konvertieren
        if not sections_data:
            sections_data = get_current_form_structure_as_dict()

        # Generator aufrufen (Achtung: Der Generator muss jetzt Dictionaries verstehen!)
        gen = PdfGenerator(sections_data, inspection, current_app.config['UPLOAD_FOLDER'])
        rel_path = gen.create()

        inspection.pdf_path = rel_path
        db.session.commit()
        folder, filename = os.path.split(rel_path)
        return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], folder), filename,
                                   as_attachment=True)

    except Exception as e:
        current_app.logger.error(f"PDF Gen Error: {e}")
        flash(f"Fehler: {e}", "danger")
        return redirect(url_for('projects.overview'))


@bp.route('/status', methods=['POST'])
@login_required
def status_update():
    """Status-Update (Ampel)."""
    data = request.json
    inspection = db.session.get(Inspection, data.get('id'))

    if not inspection: return jsonify({'success': False, 'error': 'Eintrag fehlt'}), 404

    new_status = data.get('status')
    is_manager = current_user.is_admin or current_user.has_permission('immo_files_access')
    is_owner = inspection.user_id == current_user.id
    allow_submit = (
                is_owner and inspection.status == Inspection.STATUS_DRAFT and new_status == Inspection.STATUS_SUBMITTED)

    if not (is_manager or allow_submit):
        return jsonify({'success': False, 'error': 'Keine Berechtigung'}), 403

    valid_statuses = [
        Inspection.STATUS_DRAFT, Inspection.STATUS_SUBMITTED,
        Inspection.STATUS_REVIEW, Inspection.STATUS_DONE, Inspection.STATUS_REJECTED
    ]

    if new_status in valid_statuses:
        old_status = inspection.status
        inspection.status = new_status
        if old_status != new_status:
            log = InspectionLog(
                inspection_id=inspection.id, user_id=current_user.id, action='status_change',
                details=f"Status geändert: {old_status} -> {new_status}"
            )
            db.session.add(log)
        db.session.commit()
        return jsonify({'success': True, 'new_label': inspection.status_label, 'new_color': inspection.status_color})

    return jsonify({'success': False, 'error': 'Ungültiger Status'}), 400


# ==============================================================================
# DETAIL VIEW & EDITING
# ==============================================================================

@bp.route('/<int:inspection_id>/details', methods=['GET'])
@login_required
@permission_required('immo_user')
def detail_view(inspection_id):
    """Hauptansicht für ein Projekt."""
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection: return render_template('errors/404.html'), 404

    if not (current_user.is_admin or current_user.has_permission(
            'immo_files_access') or inspection.user_id == current_user.id):
        return render_template('errors/403.html'), 403

    import json
    parsed_data = {}
    form_responses = {}
    if inspection.data_json:
        try:
            parsed_data = json.loads(inspection.data_json)
            form_responses = parsed_data.get('form_responses', {})
        except:
            pass

    meta_questions = db.session.query(ImmoQuestion).join(ImmoSection).filter(ImmoQuestion.is_metadata == True).order_by(
        ImmoSection.order, ImmoQuestion.order).all()

    meta_fields = []
    for q in meta_questions:
        val = form_responses.get(q.id)
        if val is True: val = "Ja"
        if val is False: val = "Nein"
        if val is None or val == "": val = "-"
        meta_fields.append({'label': q.label, 'value': val})

    # Datei Logik (vereinfacht für Übersicht)
    folder_name = ""
    if inspection.pdf_path:
        folder_name = os.path.dirname(inspection.pdf_path)
    if not folder_name and inspection.csc_name:
        # Fallback (weniger sicher, aber besser als nichts)
        # Wir versuchen den Ordner anhand des Timestamp-Musters zu finden wenn möglich,
        # sonst nehmen wir den Namen.
        # Da create_quick nun Ordner mit TS erstellt, ist der Pfad in der DB (pdf_path) wichtig!
        pass

    files = []
    if folder_name:
        target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
        if os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                fp = os.path.join(target_dir, f)
                if os.path.isfile(fp):
                    is_img = f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                    is_vid = f.lower().endswith(('.mp4', '.mov', '.avi'))
                    size_mb = round(os.path.getsize(fp) / (1024 * 1024), 2)
                    files.append({
                        "name": f, "size": size_mb, "is_img": is_img, "is_vid": is_vid, "folder": folder_name
                    })

    return render_template('immo/immo_details.html', inspection=inspection, files=files,
                           folder_name=folder_name, form_responses=form_responses, meta_fields=meta_fields)


@bp.route('/<int:inspection_id>/update_data', methods=['POST'])
@login_required
@permission_required('immo_user')
def update_inspection_data(inspection_id):
    """Speichert Änderungen am Formular."""
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection: return jsonify({'error': 'Nicht gefunden'}), 404

    if not (current_user.is_admin or current_user.has_permission(
            'immo_files_access') or inspection.user_id == current_user.id):
        return jsonify({'error': 'Keine Berechtigung'}), 403

    try:
        new_data = request.json.get('form_data', {})
        current_json = json.loads(inspection.data_json) if inspection.data_json else {}

        # Merge Logik: Bestehende Daten behalten, neue überschreiben
        # (Wichtig, falls Requests sich überschneiden, aber hier einfach Replace)
        existing_responses = current_json.get('form_responses', {})
        existing_responses.update(new_data)

        current_json['form_responses'] = existing_responses
        inspection.data_json = json.dumps(current_json)
        inspection.updated_at = datetime.utcnow()

        # Log sparen wir uns bei jedem Autosave, sonst platzt die Tabelle.
        # Nur wenn explizit gewünscht oder bei Statuswechsel.
        # Hier optional:
        # log = InspectionLog(inspection_id=inspection.id, user_id=current_user.id, action='data_update', details="Auto-Save")
        # db.session.add(log)

        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@bp.route('/blank_pdf', methods=['GET'])
@login_required
@permission_required('immo_user')
def download_blank_pdf():
    """Generiert ein leeres PDF Formular zum Ausdrucken."""
    # Typ aus URL holen (einzel, cluster, ausgabe)
    target_type = request.args.get('type', 'einzel')

    try:
        sections = ImmoSection.query.order_by(ImmoSection.order).all()

        # Generator mit target_type aufrufen
        gen = PdfGenerator(
            sections,
            inspection=None,
            upload_folder=current_app.config['UPLOAD_FOLDER'],
            target_type=target_type  # <--- NEU
        )

        rel_path = gen.create()
        folder, filename = os.path.split(rel_path)
        return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], folder), filename,
                                   as_attachment=True)

    except Exception as e:
        current_app.logger.error(f"Blank PDF Error: {e}")
        flash(f"Fehler bei PDF Generierung: {e}", "danger")
        return redirect(url_for('projects.overview'))


@bp.route('/analytics', methods=['GET'])
@login_required
@permission_required('analytics_access')
def analytics_view():
    """Zeigt das Dashboard für Auswertungen."""

    # 1. Daten holen (Alle Projekte)
    all_inspections = Inspection.query.all()

    # 2. KPIs berechnen
    total_count = len(all_inspections)

    # Status Verteilung
    status_counts = {
        'draft': 0, 'submitted': 0, 'review': 0, 'done': 0, 'rejected': 0
    }

    # Typ Verteilung
    type_counts = {'einzel': 0, 'cluster': 0, 'ausgabe': 0}

    for i in all_inspections:
        # Status zählen
        s = i.status if i.status in status_counts else 'draft'
        status_counts[s] += 1

        # Typ zählen
        t = i.inspection_type if i.inspection_type in type_counts else 'einzel'
        type_counts[t] += 1

    # Daten für Chart.js vorbereiten (Labels & Values)
    # Wir übergeben einfache Listen an das Template

    return render_template('immo/analytics.html',
                           total_count=total_count,
                           status_counts=status_counts,
                           type_counts=type_counts)


@bp.route('/analytics/export_csv', methods=['GET'])
@login_required
@permission_required('analytics_access')
def export_csv():
    """Generiert eine CSV mit ALLEN Formulardaten."""

    # 1. Alle Fragen laden (als Spaltenüberschriften)
    questions = ImmoQuestion.query.order_by(ImmoQuestion.order).all()
    header = ['ID', 'Projekt (CSC)', 'Typ', 'Status', 'Ersteller', 'Datum', 'PDF Pfad']

    # Frage-Labels als Spalten hinzufügen
    q_map = {}  # ID -> Label Mapping
    for q in questions:
        header.append(q.label)
        q_map[q.id] = q.label

    # 2. CSV im Speicher bauen
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    # Header schreiben
    cw.writerow(header)

    # 3. Datenzeilen schreiben
    inspections = Inspection.query.all()

    for i in inspections:
        # Basisdaten
        row = [
            i.id,
            i.csc_name,
            i.inspection_type,
            i.status_label,
            i.user.username,
            i.created_at.strftime('%d.%m.%Y'),
            i.pdf_path or ''
        ]

        # JSON Daten parsen
        form_data = {}
        if i.data_json:
            try:
                data = json.loads(i.data_json)
                form_data = data.get('form_responses', {})
            except:
                pass

        # Für jede Frage den Wert holen
        for q in questions:
            val = form_data.get(q.id, '')
            # True/False in Ja/Nein wandeln
            if val is True: val = 'Ja'
            if val is False: val = 'Nein'
            if isinstance(val, list): val = ", ".join(val)  # Falls Multiple Choice

            # Zeilenumbrüche entfernen für saubere CSV
            val = str(val).replace('\n', ' ').replace('\r', '')
            row.append(val)

        cw.writerow(row)

    # 4. Response erstellen
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=export_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"

    # BOM für Excel hinzufügen (damit Umlaute gehen)
    output.data = b'\xef\xbb\xbf' + output.data

    return output


# ==============================================================================
# DELETE & ARCHIVE ACTIONS
# ==============================================================================

@bp.route('/<int:inspection_id>/delete', methods=['POST'])
@login_required
@permission_required('immo_user')
def delete_project(inspection_id):
    """Löscht ein Projekt (DB + Dateien)."""
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection:
        return jsonify({'success': False, 'error': 'Projekt nicht gefunden'}), 404

    # --- BERECHTIGUNGSPRÜFUNG ---
    # 1. Admin darf immer löschen
    is_admin = current_user.is_admin
    # 2. Owner darf nur löschen, wenn Status == Draft
    is_owner_draft = (inspection.user_id == current_user.id and inspection.status == Inspection.STATUS_DRAFT)

    if not (is_admin or is_owner_draft):
        return jsonify({'success': False, 'error': 'Keine Berechtigung zum Löschen'}), 403

    try:
        # 1. Ordner löschen (falls vorhanden)
        if inspection.pdf_path:
            folder_name = os.path.dirname(inspection.pdf_path)
        else:
            # Fallback Versuche, den Ordner zu erraten, sparen wir uns hier der Sicherheit halber,
            # oder wir löschen nur den DB Eintrag.
            # Wenn wir create_quick nutzen, ist pdf_path immer gesetzt (als "Folder/").
            folder_name = inspection.pdf_path.split('/')[0] if '/' in inspection.pdf_path else inspection.pdf_path

        if folder_name:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
            if os.path.exists(full_path):
                shutil.rmtree(full_path)  # Löscht Ordner samt Inhalt rekursiv

        # 2. DB Eintrag löschen
        db.session.delete(inspection)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:inspection_id>/archive', methods=['POST'])
@login_required
def archive_project(inspection_id):
    """Setzt is_archived auf True (Status bleibt erhalten!)."""
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection: return jsonify({'success': False, 'error': '404'}), 404

    if not (current_user.is_admin or current_user.has_permission('immo_files_access')):
        return jsonify({'success': False, 'error': '403'}), 403

    try:
        # NUR DAS FLAG SETZEN
        inspection.is_archived = True

        db.session.add(InspectionLog(
            inspection_id=inspection.id, user_id=current_user.id, action='archive',
            details=f"Archiviert (Status war: {inspection.status_label})"
        ))
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/<int:inspection_id>/unarchive', methods=['POST'])
@login_required
def unarchive_project(inspection_id):
    """Setzt is_archived auf False (Status bleibt erhalten!)."""
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection: return jsonify({'success': False, 'error': '404'}), 404

    if not (current_user.is_admin or current_user.has_permission('immo_files_access')):
        return jsonify({'success': False, 'error': '403'}), 403

    try:
        # NUR DAS FLAG ENTFERNEN
        inspection.is_archived = False

        db.session.add(InspectionLog(
            inspection_id=inspection.id, user_id=current_user.id, action='unarchive',
            details="Wiederhergestellt"
        ))
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# --- HELPER FUNKTION (Neu) ---
def get_current_form_structure_as_dict():
    """Lädt die aktuelle DB-Struktur und gibt sie als Liste von Dictionaries zurück."""
    sections_db = ImmoSection.query.filter_by(category='immo').order_by(ImmoSection.order).all()
    structure = []

    for sec in sections_db:
        sec_data = {
            "id": sec.id,
            "title": sec.title,
            "is_expanded": sec.is_expanded,
            "questions": []
        }
        for q in sec.questions:
            # Wir speichern ALLES, was für die Anzeige wichtig ist
            sec_data["questions"].append({
                "id": str(q.id),  # ID als String für JSON Konsistenz
                "label": q.label,
                "type": q.type,
                "width": q.width,
                "width_tablet": q.width_tablet,
                "width_mobile": q.width_mobile,
                "tooltip": q.tooltip,
                "is_required": q.is_required,
                "is_print": getattr(q, 'is_print', True),
                "options_json": q.options_json,  # Rohdaten speichern
                "types_json": q.types_json
            })
        structure.append(sec_data)
    return structure


@bp.route('/<int:inspection_id>/config_snapshot', methods=['GET'])
@login_required
def get_project_config(inspection_id):
    """
    Gibt die Konfiguration zurück, die für DIESES Projekt gilt.
    Entweder den Snapshot (falls vorhanden) oder Live-Daten (Fallback).
    """
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection: return jsonify({'error': 'Not found'}), 404

    # 1. Versuchen, Snapshot zu laden
    snapshot = None
    if inspection.data_json:
        try:
            data = json.loads(inspection.data_json)
            snapshot = data.get('form_config')
        except:
            pass

    # 2. Wenn Snapshot da ist -> formatieren für JS
    if snapshot:
        # Der Snapshot ist fast schon das Format, das das Frontend braucht,
        # aber das Frontend erwartet "content" statt "questions" und geparste Options.
        frontend_data = []
        for sec in snapshot:
            questions_processed = []
            for q in sec['questions']:
                # JSON Strings in echte Listen wandeln, falls nötig
                opts = []
                if q.get('options_json'):
                    opts = json.loads(q['options_json']) if isinstance(q['options_json'], str) else q['options_json']

                types = []
                if q.get('types_json'):
                    types = json.loads(q['types_json']) if isinstance(q['types_json'], str) else q['types_json']

                questions_processed.append({
                    "id": q['id'],
                    "label": q['label'],
                    "type": q['type'],
                    "width": q.get('width', 'full'),
                    "width_tablet": q.get('width_tablet', 'default'),
                    "width_mobile": q.get('width_mobile', 'default'),
                    "tooltip": q.get('tooltip', ''),
                    "is_required": q.get('is_required', False),
                    "options": opts,
                    "types": types
                })

            frontend_data.append({
                "id": sec['id'],
                "title": sec['title'],
                "is_expanded": sec['is_expanded'],
                "content": questions_processed
            })
        return jsonify(frontend_data)

    # 3. Fallback: Alte Logik (Live Daten)
    # Wir rufen einfach die existierende globale Config-Funktion auf
    return get_form_config()