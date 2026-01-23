import os
import json
import csv
import io
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

@bp.route('/new', methods=['GET'])
@login_required
@permission_required('immo_user')
def create_view():
    """Zeigt das leere Erfassungsformular."""
    # Template Pfad bleibt vorerst gleich, bis wir Templates verschieben
    return render_template('immo/immo_form.html')


@bp.route('/', methods=['GET'])
@login_required
@permission_required('immo_user')
def overview():
    """Liste der Projekte/Besichtigungen."""

    # 1. Merken, wann der User ZULETZT da war (für die "Neu"-Markierung)
    last_visit = current_user.last_projects_visit

    # 2. Zeitstempel aktualisieren (fürs nächste Mal / Dashboard Reset)
    current_user.last_projects_visit = datetime.utcnow()
    db.session.commit()

    # Daten laden
    if current_user.has_permission('view_users') or current_user.is_admin:
        inspections = Inspection.query.order_by(Inspection.created_at.desc()).all()
    else:
        inspections = Inspection.query.filter_by(user_id=current_user.id).order_by(Inspection.created_at.desc()).all()

    # WICHTIG: last_visit an das Template übergeben!
    return render_template('immo/immo_overview.html',
                           inspections=inspections,
                           last_visit=last_visit)


# --- EHEMALS ADMIN FILES ROUTEN ---

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


@bp.route('/submit', methods=['POST'])
@login_required
@permission_required('immo_user')
def submit_inspection():
    """Speichert die Besichtigung (DB + JSON). KEIN PDF UPLOAD MEHR ERFORDERLICH."""
    try:
        data = request.json
        # filename_pdf wird jetzt ignoriert oder ist null
        folder_name = secure_filename(data.get('folder'))
        csc_name = data.get('csc_name', 'Unbekannt')
        immo_type = data.get('immo_type', 'einzel')
        form_responses = data.get('form_data', {})

        upload_folder = current_app.config['UPLOAD_FOLDER']
        full_folder_path = os.path.join(upload_folder, folder_name)

        attached_files = []
        if os.path.exists(full_folder_path):
            attached_files = [f for f in os.listdir(full_folder_path) if
                              os.path.isfile(os.path.join(full_folder_path, f))]

        full_json_record = {
            "meta": {"csc": csc_name, "type": immo_type, "date": datetime.utcnow().isoformat(),
                     "uploaded_by": current_user.username},
            "form_responses": form_responses,
            "attachments": attached_files
        }

        # Wir setzen pdf_path vorerst leer, es wird beim ersten Klick generiert
        # Oder wir setzen einen Platzhalter-Ordnerpfad

        inspection = Inspection(
            user_id=current_user.id,
            csc_name=csc_name,
            inspection_type=immo_type,
            status=Inspection.STATUS_SUBMITTED,
            pdf_path=os.path.join(folder_name, ""),  # Nur Ordner merken erstmal (Trick)
            data_json=json.dumps(full_json_record)
        )
        db.session.add(inspection)
        db.session.commit()

        # OPTIONAL: PDF Direkt generieren lassen (Server-Side)
        # Damit es direkt da ist:
        try:
            # Config laden
            sections = ImmoSection.query.order_by(ImmoSection.order).all()
            gen = PdfGenerator(sections, inspection, current_app.config['UPLOAD_FOLDER'])
            rel_path = gen.create()
            inspection.pdf_path = rel_path
            db.session.commit()
        except Exception as e:
            print(f"Auto-PDF Error: {e}")

        return jsonify({"success": True, "id": inspection.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<int:inspection_id>/generate_pdf', methods=['GET'])
@login_required
def generate_and_download_pdf(inspection_id):
    """
    Generiert das PDF aus den DB-Daten neu, speichert es und sendet es an den User.
    """
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection:
        return render_template('errors/404.html'), 404

    if not (current_user.is_admin or current_user.has_permission(
            'immo_files_access') or inspection.user_id == current_user.id):
        return render_template('errors/403.html'), 403

    try:
        # 1. Config laden (inklusive Questions)
        sections = ImmoSection.query.order_by(ImmoSection.order).all()

        # 2. Generator aufrufen
        gen = PdfGenerator(sections, inspection, current_app.config['UPLOAD_FOLDER'])
        rel_path = gen.create()  # Gibt z.B. "Ordner/File.pdf" zurück

        # 3. Pfad in DB aktualisieren
        inspection.pdf_path = rel_path
        db.session.commit()

        # 4. Datei senden
        folder, filename = os.path.split(rel_path)
        return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], folder), filename,
                                   as_attachment=True)

    except Exception as e:
        current_app.logger.error(f"PDF Gen Error: {e}")
        flash(f"Fehler bei PDF Generierung: {e}", "danger")
        return redirect(url_for('projects.overview'))


@bp.route('/status', methods=['POST'])
@login_required
def status_update():
    """Status-Update (Ampel). Ehemals Admin, jetzt Workflow."""
    data = request.json
    inspection = db.session.get(Inspection, data.get('id'))

    if not inspection:
        return jsonify({'success': False, 'error': 'Eintrag fehlt'}), 404

    new_status = data.get('status')

    # --- BERECHTIGUNGSPRÜFUNG ---
    # 1. Manager/Admins dürfen alles (Files Access = Leitung)
    is_manager = current_user.is_admin or current_user.has_permission('immo_files_access')

    # 2. Owner darf NUR von Draft -> Submitted wechseln
    is_owner = inspection.user_id == current_user.id
    allow_submit = (
                is_owner and inspection.status == Inspection.STATUS_DRAFT and new_status == Inspection.STATUS_SUBMITTED)

    if not (is_manager or allow_submit):
        return jsonify({'success': False, 'error': 'Keine Berechtigung für diesen Statuswechsel'}), 403

    # Validierung der Status-Strings aus dem Model
    valid_statuses = [
        Inspection.STATUS_DRAFT, Inspection.STATUS_SUBMITTED,
        Inspection.STATUS_REVIEW, Inspection.STATUS_DONE,
        Inspection.STATUS_REJECTED
    ]

    if new_status in valid_statuses:
        old_status = inspection.status
        inspection.status = new_status

        # Best Practice: Statusänderung loggen
        if old_status != new_status:
            log = InspectionLog(
                inspection_id=inspection.id,
                user_id=current_user.id,
                action='status_change',
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
    """
    Hauptansicht für ein Projekt.
    """
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection:
        return render_template('errors/404.html'), 404

    # Rechte prüfen
    if not (current_user.is_admin or current_user.has_permission(
            'immo_files_access') or inspection.user_id == current_user.id):
        return render_template('errors/403.html'), 403

    # 1. Daten aus JSON laden
    import json
    parsed_data = {}
    form_responses = {}
    if inspection.data_json:
        try:
            parsed_data = json.loads(inspection.data_json)
            form_responses = parsed_data.get('form_responses', {})
        except:
            pass

    # 2. Metadaten-Fragen laden und Antworten mappen
    # Wir holen alle Fragen, die is_metadata=True haben, sortiert nach Section und Order
    meta_questions = db.session.query(ImmoQuestion) \
        .join(ImmoSection) \
        .filter(ImmoQuestion.is_metadata == True) \
        .order_by(ImmoSection.order, ImmoQuestion.order) \
        .all()

    meta_fields = []
    for q in meta_questions:
        # Wert aus den Antworten holen (Key ist die Question ID)
        val = form_responses.get(q.id)

        # Formatierung (Checkboxen sind True/False -> Ja/Nein)
        if val is True: val = "Ja"
        if val is False: val = "Nein"
        if val is None or val == "": val = "-"

        # Einheiten anhängen? (Könnte man im Tooltip oder Label parsen, hier simpel:)
        # if q.type == 'number' and 'm²' in q.label: val = f"{val} m²"

        meta_fields.append({
            'label': q.label,
            'value': val
        })

    # 3. Dateien Logik
    # Falls pdf_path leer ist, versuchen wir den CSC-Namen als Fallback für den Ordner
    folder_name = ""
    if inspection.pdf_path:
        folder_name = os.path.dirname(inspection.pdf_path)

    # Fallback: Wenn pdf_path leer ist (alte Daten), versuchen wir csc_name
    # (Aber Vorsicht: Umlaute/Sonderzeichen müssen wie beim Upload behandelt werden)
    if not folder_name and inspection.csc_name:
        # Hier müssten wir eigentlich wissen, wie der Ordner genau hieß beim Upload.
        # Da wir das in 'pdf_path' oder 'folder' im JSON speichern sollten, schauen wir dort nach:
        if parsed_data.get('attachments'):
            # Wenn wir Attachments haben, liegt der Ordner dort
            pass  # Logik müsste robuster sein, aber für jetzt okay.

        # Simpler Fallback: Name bereinigen
        folder_name = secure_filename(inspection.csc_name.replace(" ", "_"))
        # ACHTUNG: Das ist unsicher, besser wäre es, den Ordnernamen in der DB zu haben.
        # Da wir in 'submit' pdf_path = "Ordnername/" setzen, sollte es passen.

    files = []
    if folder_name:
        target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
        if os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                fp = os.path.join(target_dir, f)
                if os.path.isfile(fp):
                    is_img = f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                    is_vid = f.lower().endswith(('.mp4', '.mov', '.avi'))
                    # Größe berechnen
                    size_mb = round(os.path.getsize(fp) / (1024 * 1024), 2)

                    files.append({
                        "name": f,
                        "size": size_mb,
                        "is_img": is_img,
                        "is_vid": is_vid,
                        "folder": folder_name
                    })

    return render_template('immo/immo_details.html',  # Template Name angepasst an deine Datei
                           inspection=inspection,
                           files=files,
                           folder_name=folder_name,
                           form_responses=form_responses,
                           meta_fields=meta_fields)  # <--- NEU übergeben


@bp.route('/<int:inspection_id>/update_data', methods=['POST'])
@login_required
@permission_required('immo_user')
def update_inspection_data(inspection_id):
    """Speichert Änderungen am Formular (Reiter 2)."""
    inspection = db.session.get(Inspection, inspection_id)
    if not inspection:
        return jsonify({'error': 'Nicht gefunden'}), 404

    # Check Rechte (Nur Ersteller oder Admin/Manager darf editieren)
    if not (current_user.is_admin or current_user.has_permission(
            'immo_files_access') or inspection.user_id == current_user.id):
        return jsonify({'error': 'Keine Berechtigung'}), 403

    try:
        new_data = request.json.get('form_data', {})

        # Bestehendes JSON laden und aktualisieren
        current_json = json.loads(inspection.data_json) if inspection.data_json else {}

        # Wir speichern die alten Werte für das Log (Diff wäre cool, aber Text reicht erstmal)
        old_form = current_json.get('form_responses', {})
        current_json['form_responses'] = new_data

        inspection.data_json = json.dumps(current_json)
        inspection.updated_at = datetime.utcnow()

        # Log schreiben
        log = InspectionLog(
            inspection_id=inspection.id,
            user_id=current_user.id,
            action='data_update',
            details=f"Formular bearbeitet."
        )
        db.session.add(log)
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