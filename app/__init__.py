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
        from flask import request
        from app.models import SiteContent, Service, User  # Imports hier drin, um Zirkelbezüge zu vermeiden
        from app.extensions import db

        global_bg_meta = db.session.get(SiteContent, 'background')

        if global_bg_meta and global_bg_meta.content:
            current_bg = global_bg_meta.content
        else:
            current_bg = 'background.png'

        # 2. Spezifisches Bild suchen basierend auf Blueprint
        if request.blueprint:
            # A. Versuch: Exakter Match (Blueprint Name == Service Slug)
            svc = Service.query.filter_by(slug=request.blueprint).first()

            # B. Versuch: Fuzzy Match (Blueprint 'immo' findet Service 'immo_tool')
            if not svc:
                svc = Service.query.filter(Service.slug.contains(request.blueprint)).first()

            # Wenn ein Service gefunden wurde UND ein Bild hat -> Überschreiben
            if svc and svc.background_image:
                current_bg = svc.background_image

            # 3. Roadmap Metadaten (für das Datum auf der Kachel)
        roadmap = db.session.get(SiteContent, 'roadmap')

        return dict(
            roadmap_meta=roadmap,
            current_background_image=current_bg
        )
    return app


def init_db_data(app):
    """
    Erstellt Standard-Daten, falls die DB leer ist.
    """
    from app.models import Service, User, SiteContent
    from werkzeug.security import generate_password_hash
    from sqlalchemy.exc import OperationalError  # <--- WICHTIG: Importieren

    try:
        # Wir versuchen, auf die DB zuzugreifen
        if Service.query.count() == 0:
            print("Initialisiere Datenbank mit Standard-Werten...")

            # ... (Dein Code zum Anlegen von Usern & Services) ...
            # Hier nichts ändern, nur einrücken!

            # Admin User (Falls keiner da ist)
            if User.query.count() == 0:
                admin = User(username='admin', email='admin@example.com', is_admin=True)
                admin.set_password('admin')
                db.session.add(admin)

            # Standard Services
            services = [
                Service(name="Immobilien Tool", slug="immo_tool", description="Besichtigungen und Protokolle",
                        icon="bi-house-check-fill", url="/immo"),
                Service(name="Roadmap Ansehen", slug="roadmap_access", description="Darf die Roadmap sehen",
                        icon="bi-eye", url="#"),
                Service(name="Roadmap Bearbeiten", slug="roadmap_edit", description="Darf die Roadmap bearbeiten",
                        icon="bi-pencil", url="#"),
                Service(name="Datei Manager", slug="immo_files_access", description="Zugriff auf Uploads",
                        icon="bi-folder2-open", url="/immo/admin/files")
            ]

            for s in services:
                # Prüfen ob es den Service schon gibt (vermeidet Duplikate beim Neustart)
                existing = Service.query.filter_by(slug=s.slug).first()
                if not existing:
                    db.session.add(s)

            db.session.commit()
            print("Fertig.")

    except OperationalError:
        # HIER IST DER RETTER:
        # Wenn die DB-Tabelle noch alt ist (Spalte fehlt), landen wir hier.
        # Wir machen einfach NICHTS (pass).
        # Dadurch stürzt die App nicht ab, und 'flask db upgrade' kann endlich laufen!
        print("Datenbank noch nicht bereit für Initialisierung (Migration steht aus). Überspringe...")
        pass
