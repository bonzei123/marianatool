# setup_dashboard.py
import sys
from app import create_app
from app.extensions import db
from app.models import Service, DashboardTile

app = create_app()


def run_seed():
    with app.app_context():
        print("🚀 Starte Dashboard Setup...")

        # --- 1. PERMISSIONS (SERVICES) ANLEGEN ---
        # Format: (Name, Slug, Icon, Beschreibung)
        permissions = [
            # User Permissions
            ("Immo Tool Zugriff", "immo_user", "bi-house-check", "Darf Besichtigungen machen"),
            ("Roadmap Ansehen", "roadmap_access", "bi-map", "Darf Roadmap sehen"),

            # Admin / Power-User Permissions
            ("Roadmap Bearbeiten", "roadmap_edit", "bi-pencil-square", "Darf Roadmap editieren"),
            ("Formular Builder", "immo_admin", "bi-tools", "Darf Fragen bearbeiten"),
            ("Datei Manager", "immo_files_access", "bi-folder2-open", "Darf Uploads verwalten"),
            ("User Verwaltung", "view_users", "bi-people", "Darf Nutzer verwalten"),
            ("Einstellungen", "view_settings", "bi-gear", "Darf System konfigurieren"),
        ]

        print(f"📦 Prüfe {len(permissions)} Berechtigungen...")

        for name, slug, icon, desc in permissions:
            # Prüfen ob Service schon existiert
            svc = Service.query.filter_by(slug=slug).first()
            if not svc:
                svc = Service(name=name, slug=slug, icon=icon, description=desc)
                db.session.add(svc)
                print(f"   [+] Erstellt: {slug}")
            else:
                # Update existierender Services (falls Icon/Name geändert wurde)
                svc.name = name
                svc.icon = icon
                svc.description = desc
                # print(f"   [=] Existiert: {slug}")

        db.session.commit()
        print("✅ Berechtigungen aktuell.")

        # --- 2. KACHELN (TILES) ANLEGEN ---
        # Wir löschen alle alten Kacheln, um eine saubere Reihenfolge zu garantieren
        # (Da Kacheln Config-Objekte sind, ist das meist okay)
        db.session.query(DashboardTile).delete()

        # Format: (Titel, Description, Icon, HexColor, Route, RequiredPermissionSlug, Order)
        tiles_data = [
            # USER BEREICH
            ("Immobilien Check", "Besichtigungen durchführen.", "bi-house-check-fill", "#19835A", "immo.immo_form",
             "immo_user", 10),
            ("Roadmap", "Projektstatus & Updates.", "bi-map-fill", "#8e44ad", "roadmap.index", "roadmap_access", 20),

            # ADMIN BEREICH
            ("Formular Builder", "Fragen & Layout anpassen.", "bi-tools", "#e74c3c", "admin.immo_admin_dashboard",
             "immo_admin", 80),
            ("Datei Manager", "Uploads verwalten.", "bi-folder2-open", "#f1c40f", "admin.immo_admin_files",
             "immo_files_access", 85),
            (
            "User Verwaltung", "Benutzer & Rechte.", "bi-people-fill", "#3498db", "admin.user_management", "view_users",
            90),
            ("Einstellungen", "Konfiguration & Design.", "bi-gear-fill", "#34495e", "admin.settings_page",
             "view_settings", 100),
        ]

        print(f"puzzle_piece Erstelle {len(tiles_data)} Dashboard-Kacheln...")

        for title, desc, icon, color, route, perm_slug, order in tiles_data:
            # Wir müssen den Service (Permission) erst aus der DB holen um ihn zu verknüpfen
            perm = Service.query.filter_by(slug=perm_slug).first()

            # Falls permission noch nicht existiert (sollte nicht passieren durch Schritt 1),
            # legen wir Kachel ohne Schutz an oder skippen. Hier: Warnung.
            perm_id = perm.id if perm else None

            tile = DashboardTile(
                title=title,
                description=desc,
                icon=icon,
                color_hex=color,
                route_name=route,
                order=order,
                required_service_id=perm_id
            )
            db.session.add(tile)

        db.session.commit()
        print("✅ Dashboard Kacheln neu angelegt.")
        print("🎉 Setup fertig!")


if __name__ == "__main__":
    try:
        run_seed()
    except Exception as e:
        print(f"\n❌ FEHLER: {e}")
        print("Tipp: Hast du 'flask db upgrade' ausgeführt?")