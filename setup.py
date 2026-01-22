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
        # 2. Permissions anlegen oder aktualisieren
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
            (8, 'analytics_access', 'Auswertungen sehen', 'Darf Statistiken und Exporte aufrufen', 'bi-graph-up-arrow'),
            (9, 'stats_access', 'Marktdaten lesen', 'Darf bundesweite Statistiken einsehen', 'bi-bar-chart-line'),
        ]

        print("... Prüfe Permissions")
        for p_id, slug, name, desc, icon in permissions_data:
            perm = db.session.get(Permission, p_id)
            if not perm:
                perm = Permission(id=p_id)
                db.session.add(perm)

            # Werte setzen / aktualisieren (auch bei bestehenden)
            perm.slug = slug
            perm.name = name
            perm.description = desc
            perm.icon = icon

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
            # Dem Admin alle Rechte geben
            for p in Permission.query.all():
                admin.permissions.append(p)
            db.session.add(admin)
            db.session.commit()

        # ---------------------------------------------------------
        # 4. Dashboard Kacheln anlegen oder aktualisieren
        # ---------------------------------------------------------
        # (Titel, Description, Route, Icon, Color, Order, Required Permission Slug)
        tiles_data = [
            ("Neue Besichtigung", "Starten Sie hier die Erfassung einer neuen Immobilie.", "projects.create_view",
             "bi-plus-circle-dotted", "#2ecc71", 1, "immo_user"),
            (
            "Meine Übersicht", "Status und Details Ihrer laufenden Projekte prüfen.", "projects.overview", "bi-list-ul",
            "#3498db", 2, "immo_user"),
            ("Datei Browser", "Zugriff auf alle Projektordner und Uploads.", "projects.files_overview",
             "bi-folder2-open", "#e67e22", 3, "immo_files_access"),
            ("Formular Editor", "Fragenkatalog und Formularstruktur anpassen.", "formbuilder.builder_view",
             "bi-ui-checks", "#34495e", 4, "immo_admin"),
            ("User Verwaltung", "Benutzer, Rollen und Berechtigungen steuern.", "user.list_users", "bi-people-fill",
             "#e74c3c", 5, "view_users"),
            ("Einstellungen", "Design, E-Mail und System-Konfiguration.", "admin.global_settings_view", "bi-sliders",
             "#95a5a6", 6, "view_settings"),
            ("Projekt Roadmap", "Aktueller Entwicklungsstand und geplante Features.", "roadmap.view_roadmap",
             "bi-signpost-split", "#9b59b6", 7, "roadmap_access"),
            ("Auswertung", "Projekt-Statistiken und Excel-Export.", "projects.analytics_view",
             "bi-pie-chart-fill", "#6610f2", 8, "analytics_access"),
            ("Markt-Daten", "Bundesweite Antrags- und Genehmigungszahlen.", "stats.index",
             "bi-graph-up", "#fd7e14", 9, "stats_access"),
        ]

        print("... Erstelle/Aktualisiere Dashboard Kacheln")

        for title, desc, route, icon, color, order, perm_slug in tiles_data:
            # Permission Objekt suchen
            perm = Permission.query.filter_by(slug=perm_slug).first()

            # Prüfen ob Tile existiert (anhand der Route)
            tile = DashboardTile.query.filter_by(route_name=route).first()

            if not tile:
                tile = DashboardTile(route_name=route)
                db.session.add(tile)

            # Attribute aktualisieren (damit Änderungen in der Liste übernommen werden)
            tile.title = title
            tile.description = desc  # <--- Hier fehlte vorher die Zuweisung
            tile.icon = icon
            tile.color_hex = color
            tile.order = order
            tile.required_permission = perm

        db.session.commit()
        print("✅ Fertig! Datenbank wurde befüllt und aktualisiert.")


if __name__ == "__main__":
    seed()