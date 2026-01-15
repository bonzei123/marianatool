import os
import json
from flask import render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.immo import bp
from app.models import ImmoSection

@bp.route('/immo')
@login_required
def immo_form():
    if not current_user.has_permission('immo_user'): return redirect(url_for('main.home'))
    return render_template('immo/immo_form.html')

@bp.route('/api/config')
@login_required
def get_config():
    sections = ImmoSection.query.order_by(ImmoSection.order).all()
    data = []
    for sec in sections:
        questions = []
        for q in sec.questions:
            questions.append({
                "id": q.id, "label": q.label, "type": q.type, "width": q.width, "tooltip": q.tooltip,
                "options": json.loads(q.options_json) if q.options_json else [],
                "types": json.loads(q.types_json) if q.types_json else []
            })
        data.append({"id": sec.id, "title": sec.title, "is_expanded": sec.is_expanded, "content": questions})
    return jsonify(data)

# UPLOAD API
@bp.route('/api/upload/init', methods=['POST'])
@login_required
def upload_init():
    data = request.json
    folder_name = secure_filename(data.get('folder_name'))
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(target_dir, exist_ok=True)
    return jsonify({"success": True, "path": folder_name})

@bp.route('/api/upload/chunk', methods=['POST'])
@login_required
def upload_chunk():
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
    except Exception as e: return jsonify({"error": str(e)}), 500

@bp.route('/api/upload/complete', methods=['POST'])
@login_required
def upload_complete():
    return jsonify({"success": True})