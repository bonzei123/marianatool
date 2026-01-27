import json
import uuid  # <--- NEU: Für ID Generierung
from datetime import datetime
from flask import render_template, request, jsonify, Blueprint
from flask_login import login_required
from app.extensions import db
from app.models import ImmoBackup, ImmoSection, ImmoQuestion
from app.utils import import_json_data
from app.decorators import permission_required
from app.formbuilder import bp


@bp.route('/', methods=['GET'])
@login_required
@permission_required('immo_admin')
def builder_view():
    """Zeigt das Editor GUI."""
    return render_template('admin/immo_admin.html')


@bp.route('/save', methods=['POST'])
@login_required
@permission_required('immo_admin')
def builder_save():
    """Speichert neue Konfiguration und legt Backup an."""
    try:
        new_data = request.json
        # Automatisches Backup vor dem Speichern
        backup_name = f"AutoSave {datetime.now().strftime('%d.%m. %H:%M')}"
        backup = ImmoBackup(name=backup_name, data_json=json.dumps(new_data))
        db.session.add(backup)

        # Helper Funktion aus utils.py zum Importieren der Fragen
        import_json_data(new_data)

        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route('/backups', methods=['GET'])
@login_required
@permission_required('immo_admin')
def list_backups():
    """Listet verfügbare JSON Backups für das Frontend."""
    backups = ImmoBackup.query.order_by(ImmoBackup.created_at.desc()).limit(20).all()
    return jsonify([
        {
            "id": b.id,
            "name": b.name,
            "data": json.loads(b.data_json)
        }
        for b in backups
    ])


@bp.route('/onboarding', methods=['GET'])
@login_required
@permission_required('immo_admin')
def onboarding_builder_view():
    """Zeigt den Editor speziell für das Onboarding."""
    return render_template('admin/onboarding_builder.html')


@bp.route('/onboarding/config', methods=['GET'])
@login_required
def get_onboarding_config():
    """Lädt NUR Sektionen mit category='onboarding'."""
    sections = ImmoSection.query.filter_by(category='onboarding').order_by(ImmoSection.order).all()
    data = []
    for sec in sections:
        questions = []
        for q in sec.questions:
            questions.append({
                "id": q.id, "label": q.label, "type": q.type,
                "width": q.width, "width_tablet": q.width_tablet, "width_mobile": q.width_mobile,
                "tooltip": q.tooltip, "is_required": q.is_required,
                "is_metadata": q.is_metadata, "is_print": q.is_print,
                "options": json.loads(q.options_json) if q.options_json else [],
                "types": json.loads(q.types_json) if q.types_json else []
            })
        data.append({"id": sec.id, "title": sec.title, "is_expanded": sec.is_expanded, "content": questions})
    return jsonify(data)


@bp.route('/onboarding/save', methods=['POST'])
@login_required
@permission_required('immo_admin')
def save_onboarding_config():
    """Speichert NUR Onboarding Sektionen."""
    try:
        new_data = request.json

        # 1. Alte Onboarding-Daten bereinigen
        old_sections = ImmoSection.query.filter_by(category='onboarding').all()
        for old_sec in old_sections:
            db.session.delete(old_sec)

        db.session.flush()

        # 2. Neue Daten explizit anlegen
        for sec_idx, sec_data in enumerate(new_data):

            # WICHTIG: ID generieren, da String-PK nicht automatisch erstellt wird
            new_sec_id = str(uuid.uuid4())

            new_sec = ImmoSection(
                id=new_sec_id,  # <--- FIX: ID explizit setzen
                title=sec_data.get('title', 'Neue Sektion'),
                is_expanded=sec_data.get('is_expanded', True),
                order=sec_idx,
                category='onboarding'
            )
            db.session.add(new_sec)

            # Fragen zur Section hinzufügen
            for q_idx, q_data in enumerate(sec_data.get('content', [])):
                # WICHTIG: Auch für Fragen eine ID generieren
                new_q_id = str(uuid.uuid4())

                new_q = ImmoQuestion(
                    id=new_q_id,  # <--- FIX: ID explizit setzen
                    section_id=new_sec_id,  # Beziehung über die generierte ID
                    label=q_data.get('label', ''),
                    type=q_data.get('type', 'text'),
                    order=q_idx,
                    width=q_data.get('width', 'half'),
                    width_tablet=q_data.get('width_tablet', 'default'),
                    width_mobile=q_data.get('width_mobile', 'default'),
                    tooltip=q_data.get('tooltip', ''),
                    is_required=q_data.get('is_required', False),
                    is_metadata=q_data.get('is_metadata', False),
                    is_print=q_data.get('is_print', True),
                    options_json=json.dumps(q_data.get('options', [])),
                    types_json=json.dumps(q_data.get('types', ['einzel']))
                )
                db.session.add(new_q)

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        print(f"Error saving onboarding: {e}")
        # Gibt den genauen Fehler an das Frontend zurück, damit du siehst was los ist
        return jsonify({"error": str(e)}), 500