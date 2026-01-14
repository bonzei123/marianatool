import os
import json
import shutil
from datetime import datetime
from flask import Flask, render_template, flash, redirect, url_for, request, jsonify, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from forms import LoginForm, RegisterForm

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = 'dein_geheimer_key_123'
custom_db_path = os.environ.get('DB_PATH')
if custom_db_path:
    # FALL: DOCKER / SERVER
    # Wir nutzen den Pfad, der im Docker definiert wurde
    print(f"--> Starte im Docker-Modus. Nutze Datenbank: {custom_db_path}")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{custom_db_path}'
else:
    # FALL: LOKAL / PYCHARM
    # Keine Variable da, also nutzen wir die lokale Datei
    print("--> Starte im Lokalen Modus. Nutze lokale site.db")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELLE ---

user_services = db.Table('user_services',
                         db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                         db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True)
                         )


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    url = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), default="bi-box")
    color_class = db.Column(db.String(50), default="border-primary")
    slug = db.Column(db.String(50), unique=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    services = db.relationship('Service', secondary=user_services, lazy='subquery',
                               backref=db.backref('users', lazy=True))

    def has_service(self, slug_name):
        return any(s.slug == slug_name for s in self.services) or self.is_admin


class ImmoSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)


class ImmoSection(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200))
    order = db.Column(db.Integer)
    is_expanded = db.Column(db.Boolean, default=True)
    questions = db.relationship('ImmoQuestion', backref='section', cascade="all, delete-orphan",
                                order_by='ImmoQuestion.order')


class ImmoQuestion(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    section_id = db.Column(db.String(50), db.ForeignKey('immo_section.id'))
    label = db.Column(db.Text)
    type = db.Column(db.String(50))
    width = db.Column(db.String(20))
    tooltip = db.Column(db.String(255))
    options_json = db.Column(db.Text)
    types_json = db.Column(db.Text)
    order = db.Column(db.Integer)


class ImmoBackup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(100))
    data_json = db.Column(db.Text)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- HILFSMITTEL & IMPORT LOGIK ---

def get_setting(key, default=""):
    s = db.session.get(ImmoSetting, key)
    return s.value if s else default


def create_services():
    if Service.query.count() == 0:
        s1 = Service(name="Immo Check", slug="immo_user", description="Besichtigungs-Formular", url="/immo",
                     icon="bi-house-check", color_class="border-success")
        s2 = Service(name="Immo Admin", slug="immo_admin", description="Builder & Dateien", url="/immo/admin",
                     icon="bi-tools", color_class="border-danger")
        db.session.add_all([s1, s2])
        db.session.commit()


def init_questions_from_json():
    """Laedt static/questions.json in die DB, wenn keine Sections da sind."""
    if ImmoSection.query.first(): return  # DB ist nicht leer

    json_path = os.path.join(STATIC_FOLDER, 'questions.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                import_json_data(data)
                print("✅ questions.json erfolgreich importiert.")
        except Exception as e:
            print(f"❌ Fehler beim Laden von questions.json: {e}")


def import_json_data(data):
    """Kern-Logik zum Importieren von JSON Struktur (löscht alte Daten!)"""
    # 1. Alte Daten löschen
    try:
        ImmoQuestion.query.delete()
        ImmoSection.query.delete()

        # 2. Neu anlegen
        for i, sec_data in enumerate(data):
            # ID Prüfung für Section
            sec_id = sec_data.get('id')
            if not sec_id:  # Fängt None UND leere Strings "" ab
                sec_id = f'autogen_sec_{i}'

            section = ImmoSection(
                id=sec_id,
                title=sec_data.get('title', 'Unbenannt'),
                order=i,
                is_expanded=sec_data.get('is_expanded', True)
            )
            db.session.add(section)

            for j, q_data in enumerate(sec_data.get('content', [])):
                # ID Prüfung für Question (DAS WAR DER FEHLER)
                q_id = q_data.get('id')
                if not q_id:  # Fängt None UND leere Strings "" ab
                    q_id = f'autogen_q_{i}_{j}'

                q = ImmoQuestion(
                    id=q_id,
                    section_id=section.id,
                    label=q_data.get('label', ''),
                    type=q_data.get('type', 'text'),
                    width=q_data.get('width', 'half'),
                    tooltip=q_data.get('tooltip', ''),
                    options_json=json.dumps(q_data.get('options', [])),
                    types_json=json.dumps(q_data.get('types', [])),
                    order=j
                )
                db.session.add(q)

        db.session.commit()
        print("✅ Import erfolgreich (leere IDs wurden generiert).")
    except Exception as e:
        db.session.rollback()
        print(f"❌ DB Fehler beim Import: {e}")
        raise e  # Fehler weiterwerfen, damit das Frontend ihn sieht


# --- ROUTES ---

@app.route('/', methods=["GET", "POST"])
@login_required
def home():
    return render_template('main.html', services=current_user.services, is_admin=current_user.is_admin)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)
            if not user.services and not user.is_admin:  # Auto-Assign falls leer
                user.services = Service.query.all()
                db.session.commit()
            return redirect(url_for('home'))
        else:
            flash("Login fehlgeschlagen.", "danger")
    return render_template("login.html", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('home'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Benutzername vergeben.', 'danger')
            return render_template("register.html", form=form)
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account erstellt!', 'success')
        return redirect(url_for('login'))
    return render_template("register.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Ausgeloggt.', 'info')
    return redirect(url_for('login'))


# --- IMMO ROUTES ---

@app.route('/immo')
@login_required
def immo_form():
    if not current_user.has_service('immo_user'): return redirect(url_for('home'))
    return render_template('immo_form.html')


@app.route('/api/config')
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


# --- ADMIN ROUTES ---

@app.route('/immo/admin')
@login_required
def immo_admin_dashboard():
    if not current_user.has_service('immo_admin'): return redirect(url_for('home'))
    return render_template('immo_admin.html')


@app.route('/immo/admin/save', methods=['POST'])
@login_required
def immo_save_config():
    if not current_user.has_service('immo_admin'): return jsonify({"error": "No permission"}), 403
    try:
        new_data = request.json
        # Backup
        backup_name = f"AutoSave {datetime.now().strftime('%d.%m. %H:%M')}"
        backup = ImmoBackup(name=backup_name, data_json=json.dumps(new_data))
        db.session.add(backup)
        # Import
        import_json_data(new_data)  # Nutzt die robuste Funktion von oben
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/immo/admin/backups')
@login_required
def get_backups():
    if not current_user.has_service('immo_admin'): return jsonify([])
    backups = ImmoBackup.query.order_by(ImmoBackup.created_at.desc()).limit(20).all()
    return jsonify([{"id": b.id, "name": b.name, "data": json.loads(b.data_json)} for b in backups])


@app.route('/immo/admin/files')
@login_required
def immo_admin_files():
    if not current_user.has_service('immo_admin'): return redirect(url_for('home'))
    projects = []
    if os.path.exists(UPLOAD_FOLDER):
        items = os.listdir(UPLOAD_FOLDER)
        items.sort(key=lambda x: os.path.getmtime(os.path.join(UPLOAD_FOLDER, x)), reverse=True)
        for name in items:
            path = os.path.join(UPLOAD_FOLDER, name)
            if os.path.isdir(path):
                files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                size_mb = sum(os.path.getsize(os.path.join(path, f)) for f in files) / (1024 * 1024)
                projects.append({"name": name, "count": len(files), "size": round(size_mb, 2),
                                 "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime('%d.%m.%Y %H:%M')})
    return render_template('immo_files.html', projects=projects)


@app.route('/immo/admin/files/<project_name>')
@login_required
def immo_view_project(project_name):
    if not current_user.has_service('immo_admin'): return redirect(url_for('home'))
    safe_name = secure_filename(project_name)
    target_dir = os.path.join(UPLOAD_FOLDER, safe_name)
    files = []
    if os.path.exists(target_dir):
        for f in os.listdir(target_dir):
            fp = os.path.join(target_dir, f)
            if os.path.isfile(fp):
                is_img = f.lower().endswith(('.png', '.jpg', '.jpeg'))
                is_vid = f.lower().endswith(('.mp4', '.mov'))
                files.append({"name": f, "size": round(os.path.getsize(fp) / 1024 / 1024, 2), "is_img": is_img,
                              "is_vid": is_vid})
    return render_template('immo_project_view.html', project=safe_name, files=files)


@app.route('/uploads/<project>/<filename>')
@login_required
def uploaded_file(project, filename):
    return send_from_directory(os.path.join(UPLOAD_FOLDER, project), filename)


# --- SETTINGS & RESTORE ---
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def settings_page():
    if not current_user.is_admin: return redirect(url_for('home'))

    if request.method == 'POST':
        # 1. Email speichern
        if 'email_receiver' in request.form:
            s = ImmoSetting.query.get('email_receiver') or ImmoSetting(key='email_receiver')
            s.value = request.form['email_receiver']
            db.session.add(s)

        # 2. Hintergrundbild
        if 'background_image' in request.files:
            f = request.files['background_image']
            if f.filename: f.save(os.path.join(STATIC_FOLDER, 'background.jpg'))

        # 3. JSON Restore (Backup einspielen)
        if 'backup_file' in request.files:
            f = request.files['backup_file']
            if f.filename.endswith('.json'):
                try:
                    data = json.load(f)
                    import_json_data(data)  # Import Logik
                    flash("Backup erfolgreich wiederhergestellt!", "success")
                except Exception as e:
                    flash(f"Fehler beim Import: {e}", "danger")

        db.session.commit()
        if 'email_receiver' in request.form and 'backup_file' not in request.files:
            flash("Einstellungen gespeichert.", "success")

    s = ImmoSetting.query.get('email_receiver')
    email = s.value if s else ""
    return render_template('settings.html', email=email)


# --- USER MANAGEMENT ---
@app.route('/admin/users')
@login_required
def user_management():
    if not current_user.is_admin: return redirect(url_for('home'))
    users = User.query.all()
    all_services = Service.query.all()  # Services für das Modal
    return render_template('users.html', users=users, all_services=all_services)


@app.route('/admin/users/create', methods=['POST'])
@login_required
def create_user():
    if not current_user.is_admin: return redirect(url_for('home'))
    username = request.form.get('username')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form
    if User.query.filter_by(username=username).first():
        flash('User existiert bereits', 'danger')
    else:
        new_user = User(username=username, password_hash=generate_password_hash(password), is_admin=is_admin)
        # Services zuweisen
        selected_services = request.form.getlist('services')
        for s_id in selected_services:
            s = db.session.get(Service, int(s_id))
            if s: new_user.services.append(s)

        db.session.add(new_user)
        db.session.commit()
        flash('User angelegt', 'success')
    return redirect(url_for('user_management'))


@app.route('/admin/users/update/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if not current_user.is_admin: return jsonify({"error": "Forbidden"}), 403
    user = db.session.get(User, user_id)
    if not user: return jsonify({"error": "User not found"}), 404

    # 1. Admin Status
    user.is_admin = 'is_admin' in request.form

    # 2. Passwort Reset (nur wenn ausgefüllt)
    new_pw = request.form.get('password')
    if new_pw and new_pw.strip():
        user.password_hash = generate_password_hash(new_pw)

    # 3. Services (Rechte) aktualisieren
    user.services = []  # Erstmal leeren
    selected_services = request.form.getlist('services')
    for s_id in selected_services:
        s = db.session.get(Service, int(s_id))
        if s: user.services.append(s)

    db.session.commit()
    flash(f'User {user.username} aktualisiert', 'success')
    return redirect(url_for('user_management'))


@app.route('/admin/users/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_admin: return redirect(url_for('home'))
    user = db.session.get(User, user_id)
    if user:
        if user.id == current_user.id:
            flash("Du kannst dich nicht selbst löschen!", "warning")
        else:
            db.session.delete(user)
            db.session.commit()
            flash('User gelöscht', 'success')
    return redirect(url_for('user_management'))


# --- UPLOAD APIS ---
@app.route('/api/upload/init', methods=['POST'])
@login_required
def upload_init():
    data = request.json
    folder_name = secure_filename(data.get('folder_name'))
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(target_dir, exist_ok=True)
    return jsonify({"success": True, "path": folder_name})


@app.route('/api/upload/chunk', methods=['POST'])
@login_required
def upload_chunk():
    try:
        file = request.files['file']
        folder_name = secure_filename(request.form['folder'])
        filename = secure_filename(request.form['filename'])
        chunk_index = int(request.form['chunkIndex'])
        target_dir = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
        mode = 'wb' if chunk_index == 0 else 'ab'
        with open(os.path.join(target_dir, filename), mode) as f:
            f.write(file.read())
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/upload/complete', methods=['POST'])
@login_required
def upload_complete():
    # Email Versand Logik hier (gekürzt für Übersicht)
    return jsonify({"success": True, "mail_sent": False})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_services()
        init_questions_from_json()  # <--- WICHTIG: Laedt questions.json beim Start
        if not User.query.first():
            db.session.add(User(username="admin", password_hash=generate_password_hash("admin123"), is_admin=True))
            db.session.commit()
    app.run(host='0.0.0.0', port=3000, debug=True)