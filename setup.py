from app import create_app
from app.extensions import db
from app.models import Permission, DashboardTile, User
from werkzeug.security import generate_password_hash

app = create_app()


def seed():
    with app.app_context():
        print("🌱 Starte Seeding der Datenbank...")

        # 1. Datenbank Tabellen anlegen (falls noch nicht da)
        db.create_all()

        # ---------------------------------------------------------
        # 2. Permissions anlegen
        # ---------------------------------------------------------
        permissions_data = [
            # ID, Slug, Name, Description, Icon
            (1, 'immo_user', 'Darf Projekte erfassen', 'Kann neue Besichtigungen anlegen', 'bi-house-add'),
            (2, 'view_users', 'User Verwaltung', 'Darf User sehen, anlegen und bearbeiten', 'bi-people'),
            (3, 'view_settings', 'System Einstellungen', 'Zugriff auf globale Konfigurationen', 'bi-gear'),
            (4, 'immo_admin', 'Formular Editor', 'Darf den Fragebogen bearbeiten', 'bi-pencil-square'),
            (5, 'immo_files_access', 'Datei Zugriff', 'Darf alle Projekt-Dateien sehen', 'bi-folder'),
            (6, 'roadmap_access', 'Roadmap lesen', 'Darf die Roadmap sehen', 'bi-map'),
            (7, 'roadmap_edit', 'Roadmap schreiben', 'Darf die Roadmap bearbeiten', 'bi-pen'),
        ]

        print("... Prüfe Permissions")
        for p_id, slug, name, desc, icon in permissions_data:
            perm = db.session.get(Permission, p_id)
            if not perm:
                perm = Permission(id=p_id, slug=slug, name=name, description=desc, icon=icon)
                db.session.add(perm)

        db.session.commit()

        # ---------------------------------------------------------
        # 3. Admin User anlegen (Falls keiner existiert)
        # ---------------------------------------------------------
        if not User.query.first():
            print("... Erstelle Default Admin (admin / passwort)")
            admin = User(
                username='admin',
                email='admin@local.test',
                password_hash=generate_password_hash('passwort'),
                is_admin=True
            )
            # Dem Admin alle Rechte geben (optional, da is_admin=True meist eh alles darf)
            # Aber für die Anzeige gut:
            for p in Permission.query.all():
                admin.permissions.append(p)
            db.session.add(admin)
            db.session.commit()

        # ---------------------------------------------------------
        # 4. Dashboard Kacheln anlegen
        # ---------------------------------------------------------
        # (Titel, Route, Icon, Color, Order, Required Permission Slug)
        tiles_data = [
            ("Neue Besichtigung", "projects.create_view", "bi-plus-circle-dotted", "#2ecc71", 1, "immo_user"),
            ("Meine Übersicht", "projects.overview", "bi-list-ul", "#3498db", 2, "immo_user"),
            ("Datei Browser", "projects.files_overview", "bi-folder2-open", "#e67e22", 3, "immo_files_access"),
            ("Formular Editor", "formbuilder.builder_view", "bi-ui-checks", "#34495e", 4, "immo_admin"),
            ("User Verwaltung", "user.list_users", "bi-people-fill", "#e74c3c", 5, "view_users"),
            ("Einstellungen", "admin.global_settings_view", "bi-sliders", "#95a5a6", 6, "view_settings"),
            ("Projekt Roadmap", "roadmap.view_roadmap", "bi-signpost-split", "#9b59b6", 7, "roadmap_access"),
        ]

        print("... Erstelle Kacheln")
        # Alte Kacheln löschen, um Duplikate zu vermeiden?
        # Besser: Checken ob Route existiert.

        # Da DB leer ist, einfach rein damit:
        for title, route, icon, color, order, perm_slug in tiles_data:
            # Check ob Kachel mit dieser Route schon existiert
            exists = DashboardTile.query.filter_by(route_name=route).first()
            if not exists:
                # Permission Objekt holen
                perm = Permission.query.filter_by(slug=perm_slug).first()
                tile = DashboardTile(
                    title=title,
                    route_name=route,
                    icon=icon,
                    color_hex=color,
                    order=order,
                    required_permission=perm  # Verknüpfung!
                )
                db.session.add(tile)

        db.session.commit()
        print("✅ Fertig! Datenbank wurde befüllt.")


if __name__ == "__main__":
    seed()