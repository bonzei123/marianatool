import os
import bleach
import markdown
from flask import Flask
from config import Config
from app.extensions import db, login_manager, migrate, mail


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ordner erstellen
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Extensions init
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_view'
    migrate.init_app(app, db, render_as_batch=True)
    mail.init_app(app)

    # --- BLUEPRINTS REGISTRIEREN ---

    # 1. Main (Root / Dashboard)
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    # 2. Auth (Login, Register) -> /auth
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # 3. User (Profile, Self-Mgmt) -> /user
    from app.user import bp as user_bp
    app.register_blueprint(user_bp, url_prefix='/user')

    # 4. Projects (Workflow, Uploads) -> /projects
    from app.projects import bp as projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')

    # 5. Formbuilder (Editor) -> /formbuilder
    from app.formbuilder import bp as builder_bp
    app.register_blueprint(builder_bp, url_prefix='/formbuilder')

    # 6. Admin (User Mgmt, Global Settings) -> /admin
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    # 7. Roadmap -> /roadmap
    from app.roadmap import bp as roadmap_bp
    app.register_blueprint(roadmap_bp, url_prefix='/roadmap')

    # --- CONTEXT PROCESSORS & FILTERS ---

    @app.context_processor
    def inject_roadmap_meta():
        from app.models import SiteContent
        meta = db.session.get(SiteContent, 'roadmap')
        return dict(roadmap_meta=meta)

    @app.template_filter('markdown')
    def markdown_filter(text):
        if not text: return ""
        allowed_tags = list(bleach.sanitizer.ALLOWED_TAGS) + [
            'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'pre', 'code', 'table', 'thead',
            'tbody', 'tr', 'th', 'td', 'blockquote', 'hr',
            'strong', 'em', 'a', 'img'
        ]
        allowed_attrs = {'*': ['class'], 'a': ['href', 'rel'], 'img': ['src', 'alt', 'style']}
        html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
        return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)

    @app.context_processor
    def inject_globals():
        from flask import request
        from app.models import SiteContent, Permission

        # 1. Globales Bild
        global_bg_meta = db.session.get(SiteContent, 'background')
        current_bg = global_bg_meta.content if (global_bg_meta and global_bg_meta.content) else 'background.png'

        # 2. Blueprint-spezifisches Bild (Logik angepasst auf neue Namen)
        if request.blueprint:
            # Mapping Blueprint -> Permission Slug Prefix
            # projects -> immo_tool (altes naming in DB)
            # formbuilder -> immo_admin (altes naming in DB)
            lookup_slug = request.blueprint

            # Manuelles Mapping für historische Slugs in der DB
            if request.blueprint == 'projects': lookup_slug = 'immo'
            if request.blueprint == 'formbuilder': lookup_slug = 'immo_admin'

            # A. Versuch: Exakter Match oder B. Fuzzy Match
            svc = Permission.query.filter(Permission.slug.contains(lookup_slug)).first()

            if svc and svc.background_image:
                current_bg = svc.background_image

        roadmap = db.session.get(SiteContent, 'roadmap')
        return dict(roadmap_meta=roadmap, current_background_image=current_bg)

    from app.commands import cmd_bp
    app.register_blueprint(cmd_bp)

    import click
    @app.cli.command("import-questions")
    def import_questions_command():
        """Importiert Fragen aus static/questions.json in die Datenbank."""
        # Wir müssen den Import hier machen, um Zirkelbezüge zu vermeiden
        # oder wir importieren die Funktion aus admin.routes
        from app.admin.routes import perform_question_import

        click.echo("Starte Import...")
        success, msg = perform_question_import()

        if success:
            click.secho(f"SUCCESS: {msg}", fg="green")
        else:
            click.secho(f"ERROR: {msg}", fg="red")

    return app