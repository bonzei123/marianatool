# app/admin/routes.py
import os
import json
from datetime import datetime
from flask import render_template, redirect, url_for, request, jsonify, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from app.admin import bp
from app.extensions import db
from app.models import User, Permission, ImmoSetting, ImmoBackup, ImmoQuestion, ImmoSection
from app.utils import import_json_data, send_reset_email
from app.decorators import permission_required


# HELPER
def get_setting(key, default=""):
    s = db.session.get(ImmoSetting, key)
    return s.value if s else default


# --- BUILDER ---
@bp.route('/immo/admin')
@login_required
@permission_required('immo_admin')
def immo_admin_dashboard():
    return render_template('admin/immo_admin.html')


@bp.route('/immo/admin/save', methods=['POST'])
@login_required
@permission_required('immo_admin')
def immo_save_config():
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
@permission_required('immo_admin')
def get_backups():
    backups = ImmoBackup.query.order_by(ImmoBackup.created_at.desc()).limit(20).all()
    return jsonify([{"id": b.id, "name": b.name, "data": json.loads(b.data_json)} for b in backups])


# --- DATEIEN ---
@bp.route('/immo/admin/files')
@login_required
@permission_required('immo_admin')
def immo_admin_files():
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
@permission_required('immo_admin')
def immo_view_project(project_name):
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
@permission_required('immo_admin')
def uploaded_file(project, filename):
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], project), filename)


# --- USER & SETTINGS ---
@bp.route('/admin/users')
@login_required
@permission_required('view_users')
def user_management():
    return render_template('admin/users.html', users=User.query.all(), all_permissions=Permission.query.all())


@bp.route('/admin/users/create', methods=['POST'])
@login_required
@permission_required('view_users')
def create_user():

    username = request.form.get('username')
    email = request.form.get('email')  # <--- NEU
    password = request.form.get('password')  # Initialpasswort beim Anlegen ist okay
    is_admin = 'is_admin' in request.form

    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash('User oder E-Mail existiert bereits', 'danger')
    else:
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password),
                        is_admin=is_admin)
        for s_id in request.form.getlist('permissions'):
            s = db.session.get(Permission, int(s_id))
            if s: new_user.permissions.append(s)
        db.session.add(new_user)
        db.session.commit()
        flash('User angelegt', 'success')
    return redirect(url_for('admin.user_management'))


@bp.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required
@permission_required('view_users')
def update_user(user_id):

    user = db.session.get(User, user_id)
    if user:
        # 1. Basisdaten
        user.is_admin = 'is_admin' in request.form

        # 2. Email Update (Prüfung auf Duplikate wäre hier gut)
        new_email = request.form.get('email')
        if new_email and new_email != user.email:
            if not User.query.filter_by(email=new_email).first():
                user.email = new_email
            else:
                flash(f'E-Mail {new_email} ist schon vergeben!', 'warning')
                return redirect(url_for('admin.user_management'))

        # 3. Permissions
        user.permissions = []
        for s_id in request.form.getlist('permissions'):
            s = db.session.get(Permission, int(s_id))
            if s: user.permissions.append(s)

        db.session.commit()
        flash(f'{user.username} aktualisiert', 'success')
    return redirect(url_for('admin.user_management'))


# --- NEUE ROUTE FÜR DEN BUTTON ---
@bp.route('/admin/users/trigger_reset/<int:user_id>', methods=['POST'])
@login_required
@permission_required('view_users')
def trigger_user_reset(user_id):

    user = db.session.get(User, user_id)
    if user:
        send_reset_email(user)  # Nutzt die Funktion aus utils.py
        return jsonify({"success": True, "message": f"Reset-Link an {user.email} gesendet."})
    return jsonify({"success": False, "message": "User nicht gefunden"}), 404


@bp.route('/admin/users/delete/<int:user_id>')
@login_required
@permission_required('view_users')
def delete_user(user_id):

    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('User gelöscht', 'success')
    return redirect(url_for('admin.user_management'))


@bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@permission_required('view_settings')
def settings_page():

    bg_folder = os.path.join(current_app.root_path, 'static', 'img', 'backgrounds')

    # Sicherstellen, dass der Background-Ordner existiert
    if not os.path.exists(bg_folder):
        os.makedirs(bg_folder)

    if request.method == 'POST':
        # 1. E-Mail Einstellung
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

        # 3. Backup Upload
        if 'backup_file' in request.files:
            f = request.files['backup_file']
            if f.filename.endswith('.json'):
                try:
                    import_json_data(json.load(f))
                    flash("Backup wiederhergestellt!", "success")
                except Exception as e:
                    flash(f"Import Fehler: {e}", "danger")

        # 4. NEU: Permission Hintergründe Zuweisung
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

        if 'email_receiver' in request.form:
            flash("Einstellungen gespeichert.", "success")
        elif counter > 0:
            flash(f"{counter} Hintergründe zugewiesen.", "info")

        # Redirect um erneutes Senden zu verhindern
        return redirect(url_for('admin.settings_page'))

    # Daten laden für GET-Request
    email = get_setting('email_receiver', 'test@test.de')

    # Bilder und Permissions für das Modal laden
    bg_files = [f for f in os.listdir(bg_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    all_permissions = Permission.query.order_by(Permission.name).all()

    return render_template('admin/settings.html',
                           email=email,
                           background_files=bg_files,
                           permissions=all_permissions)