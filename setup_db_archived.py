import sqlite3
from app import create_app, db
from app.models import Inspection

app = create_app()


def migrate():
    with app.app_context():
        # 1. Spalte hinzufügen (Try/Except falls schon da)
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("ALTER TABLE inspection ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
                conn.commit()
            print("✅ Spalte 'is_archived' hinzugefügt.")
        except Exception as e:
            print(f"Info: Spalte existiert wohl schon ({e}).")

        # 2. Daten migrieren (Alten Status 'archived' fixen)
        inspections = Inspection.query.filter_by(status='archived').all()
        count = 0
        for i in inspections:
            i.is_archived = True
            i.status = 'done'  # Fallback, da wir den alten Status nicht mehr wissen
            count += 1

        db.session.commit()
        print(f"✅ {count} alte archivierte Projekte migriert.")


if __name__ == "__main__":
    migrate()