import os
import json
from flask import Flask
from werkzeug.security import generate_password_hash
from config import Config
from app.extensions import db, login_manager
from app.utils import import_json_data


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ordner erstellen
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Extensions init
    db.init_app(app)
    login_manager.init_app(app)

    # Blueprints registrieren
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.immo import bp as immo_bp
    app.register_blueprint(immo_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    # Datenbank & Erstdaten beim ersten Request (oder CLI)
    with app.app_context():
        db.create_all()
        init_db_data(app)

    return app


def init_db_data(app):
    from app.models import User, Service, ImmoSection

    # 1. Services
    if Service.query.count() == 0:
        s1 = Service(name="Immo Check", slug="immo_user", description="Besichtigungs-Formular", url="/immo",
                     icon="bi-house-check", color_class="border-success")
        s2 = Service(name="Immo Admin", slug="immo_admin", description="Builder & Dateien", url="/immo/admin",
                     icon="bi-tools", color_class="border-danger")
        db.session.add_all([s1, s2])
        db.session.commit()

    # 2. Admin User
    if not User.query.first():
        db.session.add(User(username="admin", password_hash=generate_password_hash("admin123"), is_admin=True))
        db.session.commit()

    # 3. Questions aus JSON laden (einmalig)
    if not ImmoSection.query.first():
        json_path = os.path.join(app.config['STATIC_FOLDER'], 'questions.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    import_json_data(json.load(f))
            except Exception as e:
                print(f"Init Import Error: {e}")