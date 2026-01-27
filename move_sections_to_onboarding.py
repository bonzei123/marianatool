from app import create_app, db
from app.models import ImmoSection

app = create_app()


def move_sections():
    with app.app_context():
        print("🚚 Verschiebe Sektionen ins Onboarding...")

        # Wir holen die ersten 2 Sektionen anhand ihrer Sortierung (order)
        # Ändere das limit(2) auf die Anzahl der Sektionen, die du verschieben willst.
        sections_to_move = ImmoSection.query.order_by(ImmoSection.order).limit(2).all()

        if not sections_to_move:
            print("❌ Keine Sektionen gefunden.")
            return

        count = 0
        for sec in sections_to_move:
            print(f"   -> Verschiebe: '{sec.title}' (ID: {sec.id})")
            sec.category = 'onboarding'
            count += 1

        db.session.commit()
        print(f"✅ Fertig. {count} Sektionen sind nun im Onboarding.")
        print("   Hinweis: Diese Sektionen tauchen nun NICHT mehr im normalen Formular-Builder auf.")


if __name__ == "__main__":
    move_sections()