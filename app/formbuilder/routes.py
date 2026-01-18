import json
from datetime import datetime
from flask import render_template, request, jsonify, Blueprint
from flask_login import login_required
from app.extensions import db
from app.models import ImmoBackup
from app.utils import import_json_data
from app.decorators import permission_required
from app.formbuilder import bp


@bp.route('/', methods=['GET'])
@login_required
@permission_required('immo_admin')
def builder_view():
    """Zeigt das Editor GUI."""
    # Wir nutzen vorerst das bestehende Template weiter
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
    # Wir geben nur die notwendigen Daten zurück
    return jsonify([
        {
            "id": b.id,
            "name": b.name,
            "data": json.loads(b.data_json)
        }
        for b in backups
    ])