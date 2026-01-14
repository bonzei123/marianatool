import os
import json
import markdown
import bleach
from flask import Flask
from werkzeug.security import generate_password_hash
from config import Config
from app.extensions import db, login_manager
from app.utils import import_json_data
from app.extensions import db, login_manager, migrate, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ordner erstellen
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Extensions init
    db.init_app(app)
    login_manager.init_app(app)

    migrate.init_app(app, db, render_as_batch=True)
    mail.init_app(app)

    # Blueprints registrieren
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.immo import bp as immo_bp
    app.register_blueprint(immo_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.roadmap import bp as roadmap_bp
    app.register_blueprint(roadmap_bp, url_prefix='/roadmap')

    # Datenbank & Erstdaten beim ersten Request (oder CLI)
    with app.app_context():
        db.create_all()
        init_db_data(app)

    @app.context_processor
    def inject_roadmap_meta():
        from app.models import SiteContent
        from app.extensions import db
        # Wir holen die Info, falls sie existiert
        meta = db.session.get(SiteContent, 'roadmap')
        return dict(roadmap_meta=meta)

    @app.template_filter('markdown')
    def markdown_filter(text):
        if not text:
            return ""
        html = markdown.markdown(text, extensions=['fenced_code', 'tables'])

        # --- HIER IST DER FIX ---
        # Wir müssen list() um bleach.sanitizer.ALLOWED_TAGS setzen!
        allowed_tags = list(bleach.sanitizer.ALLOWED_TAGS) + [
            'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'pre', 'code', 'table', 'thead',
            'tbody', 'tr', 'th', 'td', 'blockquote', 'hr',
            'strong', 'em', 'a', 'img'
        ]

        allowed_attrs = {'*': ['class'], 'a': ['href', 'rel'], 'img': ['src', 'alt', 'style']}
        return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)

    @app.context_processor
    def inject_globals():
        from app.models import SiteContent
        # Roadmap UND Background laden
        roadmap = db.session.get(SiteContent, 'roadmap')
        bg = db.session.get(SiteContent, 'background')

        # Beide Variablen stehen nun in ALLEN Templates zur Verfügung
        return dict(roadmap_meta=roadmap, background_meta=bg)


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
        db.session.add(User(username="admin", password_hash=generate_password_hash("admin123"), is_admin=True,
                            email="admin@admin.admin"))
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
