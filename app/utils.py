import json
from app.extensions import db
from app.models import ImmoSection, ImmoQuestion, User
from flask_mail import Message
from flask import current_app


def import_json_data(data):
    """
    Nimmt eine Liste von Sektionen (JSON-Struktur) entgegen und
    aktualisiert die Datenbank (ImmoSection & ImmoQuestion).
    """
    try:
        # Wir zählen mit, um die Reihenfolge (Order) sauber zu setzen
        for sec_idx, sec_data in enumerate(data):
            sec_id = sec_data.get('id')
            if not sec_id:
                continue  # Ohne ID überspringen wir

            # 1. Section holen oder erstellen
            section = db.session.get(ImmoSection, sec_id)
            if not section:
                section = ImmoSection(id=sec_id)
                db.session.add(section)

            # Werte aktualisieren
            section.title = sec_data.get('title', 'Unbenannt')
            section.is_expanded = sec_data.get('is_expanded', True)
            section.order = sec_idx

            # 2. Fragen verarbeiten
            if 'content' in sec_data:
                for q_idx, q_data in enumerate(sec_data['content']):
                    q_id = q_data.get('id')
                    if not q_id:
                        continue

                    question = db.session.get(ImmoQuestion, q_id)
                    if not question:
                        question = ImmoQuestion(id=q_id)
                        db.session.add(question)

                    # Basis-Felder mappen
                    question.section_id = sec_id
                    question.label = q_data.get('label', '')
                    question.type = q_data.get('type', 'text')
                    question.width = q_data.get('width', 'half')
                    question.tooltip = q_data.get('tooltip', '')
                    question.order = q_idx

                    # --- NEU: Validierung & Metadaten ---
                    # Das JavaScript sendet "is_required", die questions.json oft nur "required"
                    # Wir prüfen beides, um sicher zu sein.
                    question.is_required = q_data.get('is_required') or q_data.get('required') or False
                    question.is_metadata = q_data.get('is_metadata') or q_data.get('metadata') or False

                    val_print = q_data.get('is_print')
                    if val_print is None:
                        val_print = q_data.get('print', True)  # Fallback für alte JSONs
                    question.is_print = val_print

                    # Listen (Options/Types) zu JSON String konvertieren
                    opts = q_data.get('options', [])
                    types = q_data.get('types', [])

                    # Sicherheitscheck: Falls es keine Liste ist, leer machen
                    if not isinstance(opts, list): opts = []
                    if not isinstance(types, list): types = []

                    question.options_json = json.dumps(opts)
                    question.types_json = json.dumps(types)

        db.session.commit()
        return True

    except Exception as e:
        db.session.rollback()
        print(f"ERROR in import_json_data: {e}")
        raise e  # Fehler weiterreichen


def send_reset_email(user):
    """
    Sendet eine Passwort-Reset-Mail an den User.
    (Hier als Platzhalter, falls noch nicht implementiert)
    """
    token = user.get_reset_token()
    # Hier müsste deine Mail-Logik hin, z.B.:
    # msg = Message('Passwort zurücksetzen', sender='noreply@demo.com', recipients=[user.email])
    # ...
    print(f"Simuliere Mail an {user.email} mit Token: {token}")