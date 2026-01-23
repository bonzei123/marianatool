from app import create_app
from app.extensions import db
from app.models import DashboardTile

app = create_app()


def update_db():
    with app.app_context():
        print("🔧 Starte Sprint 1 DB Update...")

        # 1. Kachel "Neue Besichtigung" entfernen
        tile_to_delete = DashboardTile.query.filter_by(route_name="projects.create_view").first()
        if tile_to_delete:
            db.session.delete(tile_to_delete)
            print("   - [Gelöscht] Kachel 'Neue Besichtigung'")

        # 2. Kachel "Markt-Daten" umbenennen
        tile_to_rename = DashboardTile.query.filter_by(route_name="stats.index").first()
        if tile_to_rename:
            tile_to_rename.title = "Marktanalyse"
            print("   - [Umbenannt] Kachel zu 'Marktanalyse'")

        db.session.commit()
        print("✅ Datenbank erfolgreich aktualisiert.")


if __name__ == "__main__":
    update_db()