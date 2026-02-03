from app import create_app
from app.extensions import db
from app.models import StatusDefinition

app = create_app()


def seed():
    with app.app_context():
        print("Starte Seeding der Status-Definitionen...")

        defaults = {
            StatusDefinition.CONTEXT_VEREIN: [
                'Gegründet', 'Vorstand Kandidat', 'Vorstand gewählt',
                'e.V. beantragt', 'e.V. eingetragen', 'PrävB geschult',
                'Lizenzfähig', 'Lizenz beantragt', 'Lizenz erteilt',
                'Anbau gestartet', 'Ausgabe gestartet'
            ],
            StatusDefinition.CONTEXT_ANBAU: [
                'Planung', 'Bauphase', 'Abnahme ausstehend', 'Betriebsbereit', 'In Betrieb', 'Wartung'
            ],
            StatusDefinition.CONTEXT_AUSGABE: [
                'Standortsuche', 'Mietvertrag', 'Umbau', 'Abnahme', 'Eröffnet'
            ]
        }

        counter = 0
        for context, names in defaults.items():
            # Prüfen, ob für diesen Kontext schon was existiert
            if StatusDefinition.query.filter_by(context=context).first():
                print(f"Skipping {context} (Daten vorhanden)")
                continue

            for idx, name in enumerate(names):
                s = StatusDefinition(name=name, context=context, position=idx)
                db.session.add(s)
                counter += 1

        db.session.commit()
        print(f"Fertig! {counter} Status-Einträge erstellt.")


if __name__ == "__main__":
    seed()