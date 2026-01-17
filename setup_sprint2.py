from app import create_app
from app.extensions import db
from app.models import DashboardTile, Permission  # <--- KORRIGIERT: Kein Service mehr

app = create_app()


def run_update():
    with app.app_context():
        print("🔧 Starte Sprint 2 Fixes (Korrigiert)...")

        # --- 1. BUGFIX: Kachel "Datei Manager" reparieren ---
        # Wir suchen die Kachel anhand des Titels
        file_tile = DashboardTile.query.filter_by(title="Datei Manager").first()
        if file_tile:
            # Der Fehler "BuildError" deutet darauf hin, dass der Blueprint-Präfix fehlte.
            # Wir ändern es auf den korrekten Endpunkt im Admin-Blueprint.
            file_tile.route_name = "admin.immo_admin_files"
            print("   ✅ Kachel 'Datei Manager' Route auf 'admin.immo_admin_files' korrigiert.")
        else:
            print("   ⚠️ Kachel 'Datei Manager' nicht gefunden.")

        # --- 2. NEUE PERMISSION: Übersicht ansehen ---
        slug = "view_inspections"
        perm = Permission.query.filter_by(slug=slug).first()
        if not perm:
            perm = Permission(
                name="Besichtigungen ansehen",
                slug=slug,
                icon="bi-list-check",
                description="Darf die Übersicht aller/eigener Besichtigungen sehen"
            )
            db.session.add(perm)
            print(f"   ✅ Permission '{slug}' erstellt.")
        else:
            print(f"   ℹ️ Permission '{slug}' existiert schon.")

        # --- 3. NEUE KACHEL: Übersicht ---
        overview_tile = DashboardTile.query.filter_by(route_name="immo.overview").first()

        # Wir müssen sicherstellen, dass wir das Permission-Objekt haben (für die ID)
        perm = Permission.query.filter_by(slug=slug).first()

        if not overview_tile:
            overview_tile = DashboardTile(
                title="Meine Besichtigungen",
                description="Status & Verlauf einsehen.",
                icon="bi-clipboard-data",
                color_hex="#0d6efd",  # Bootstrap Primary Blue
                route_name="immo.overview",
                order=15,
                required_permission_id=perm.id  # <--- WICHTIG: Nutzt jetzt permission_id
            )
            db.session.add(overview_tile)
            print("   ✅ Kachel 'Meine Besichtigungen' erstellt.")
        else:
            print("   ℹ️ Kachel 'Meine Besichtigungen' existiert schon.")

        db.session.commit()
        print("🚀 Update fertig! Bitte App neu starten.")


if __name__ == "__main__":
    run_update()