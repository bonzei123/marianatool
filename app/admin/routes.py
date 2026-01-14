import os
import json
from datetime import datetime
from flask import render_template, redirect, url_for, request, jsonify, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from app.admin import bp
from app.extensions import db
from app.models import User, Service, ImmoSetting, ImmoBackup, ImmoQuestion, ImmoSection
from app.utils import import_json_data


# HELPER
def get_setting(key, default=""):
    s = db.session.get(ImmoSetting, key)
    return s.value if s else default


# --- BUILDER ---
@bp.route('/immo/admin')
@login_required
def immo_admin_dashboard():
    if not current_user.has_service('immo_admin'): return redirect(url_for('main.home'))
    return render_template('admin/immo_admin.html')


@bp.route('/immo/admin/save', methods=['POST'])
@login_required
def immo_save_config():
    if not current_user.has_service('immo_admin'): return jsonify({"error": "Forbidden"}), 403
    try:
        new_data = request.json
        # Backup
        backup_name = f"AutoSave {datetime.now().strftime('%d.%m. %H:%M')}"
        backup = ImmoBackup(name=backup_name, data_json=json.dumps(new_data))
        db.session.add(backup)
        # Import Logik nutzen
        import_json_data(new_data)
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route('/immo/admin/backups')
@login_required
def get_backups():
    if not current_user.has_service('immo_admin'): return jsonify([])
    backups = ImmoBackup.query.order_by(ImmoBackup.created_at.desc()).limit(20).all()
    return jsonify([{"id": b.id, "name": b.name, "data": json.loads(b.data_json)} for b in backups])


# --- DATEIEN ---
@bp.route('/immo/admin/files')
@login_required
def immo_admin_files():
    if not current_user.has_service('immo_admin'): return redirect(url_for('main.home'))
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
                projects.append({"name": name, "count": len(files), "size": round(size, 2),
                                 "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d.%m.%Y %H:%M')})
    return render_template('immo/immo_files.html', projects=projects)


@bp.route('/immo/admin/files/<project_name>')
@login_required
def immo_view_project(project_name):
    if not current_user.has_service('immo_admin'): return redirect(url_for('main.home'))
    safe_name = secure_filename(project_name)
    target_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_name)
    files = []
    if os.path.exists(target_dir):
        for f in os.listdir(target_dir):
            fp = os.path.join(target_dir, f)
            if os.path.isfile(fp):
                is_img = f.lower().endswith(('.png', '.jpg', '.jpeg'))
                is_vid = f.lower().endswith(('.mp4', '.mov'))
                files.append({"name": f, "size": round(os.path.getsize(fp) / 1024 / 1024, 2), "is_img": is_img,
                              "is_vid": is_vid})
    return render_template('immo/immo_project_view.html', project=safe_name, files=files)


@bp.route('/uploads/<project>/<filename>')
@login_required
def uploaded_file(project, filename):
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], project), filename)


# --- USER & SETTINGS ---
@bp.route('/admin/users')
@login_required
def user_management():
    if not current_user.is_admin: return redirect(url_for('main.home'))
    return render_template('admin/users.html', users=User.query.all(), all_services=Service.query.all())


@bp.route('/admin/users/create', methods=['POST'])
@login_required
def create_user():
    if not current_user.is_admin: return redirect(url_for('main.home'))
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form
    if User.query.filter_by(username=username).first():
        flash('User existiert bereits', 'danger')
    else:
        new_user = User(username=username, password_hash=generate_password_hash(password), is_admin=is_admin)
        for s_id in request.form.getlist('services'):
            s = db.session.get(Service, int(s_id))
            if s: new_user.services.append(s)
        db.session.add(new_user)
        db.session.commit()
        flash('User angelegt', 'success')
    return redirect(url_for('admin.user_management'))


@bp.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if not current_user.is_admin: return jsonify({"error": "Forbidden"}), 403
    user = db.session.get(User, user_id)
    if user:
        user.is_admin = 'is_admin' in request.form
        pw = request.form.get('password')
        if pw and pw.strip(): user.password_hash = generate_password_hash(pw)
        user.services = []
        for s_id in request.form.getlist('services'):
            s = db.session.get(Service, int(s_id))
            if s: user.services.append(s)
        db.session.commit()
        flash(f'{user.username} aktualisiert', 'success')
    return redirect(url_for('admin.user_management'))


@bp.route('/admin/users/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_admin: return redirect(url_for('main.home'))
    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('User gelöscht', 'success')
    return redirect(url_for('admin.user_management'))


@bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    if not current_user.is_admin: return redirect(url_for('main.home'))
    if request.method == 'POST':
        if 'email_receiver' in request.form:
            s = ImmoSetting.query.get('email_receiver') or ImmoSetting(key='email_receiver')
            s.value = request.form['email_receiver']
            db.session.add(s)
        if 'background_image' in request.files:
            f = request.files['background_image']
            if f.filename: f.save(os.path.join(current_app.config['STATIC_FOLDER'], 'background.jpg'))
        if 'backup_file' in request.files:
            f = request.files['backup_file']
            if f.filename.endswith('.json'):
                try:
                    import_json_data(json.load(f))
                    flash("Backup wiederhergestellt!", "success")
                except Exception as e:
                    flash(f"Import Fehler: {e}", "danger")
        db.session.commit()
        if 'email_receiver' in request.form: flash("Einstellungen gespeichert.", "success")

    email = get_setting('email_receiver', 'test@test.de')
    return render_template('admin/settings.html', email=email)