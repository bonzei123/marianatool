import json
import threading
from flask import url_for, current_app
from flask_mail import Message
from app.extensions import db, mail
from app.models import ImmoSection, ImmoQuestion


def import_json_data(data):
    """
    Importiert JSON Struktur in die DB (Formular-Builder).
    Löscht alle existierenden Fragen/Sektionen und legt sie neu an (Full Overwrite).
    """
    try:
        # Alte Daten löschen
        ImmoQuestion.query.delete()
        ImmoSection.query.delete()

        # Neue Daten iterieren
        for i, sec_data in enumerate(data):
            sec_id = sec_data.get('id')
            if not sec_id:
                sec_id = f'autogen_sec_{i}'

            section = ImmoSection(
                id=sec_id,
                title=sec_data.get('title', 'Unbenannt'),
                order=i,
                is_expanded=sec_data.get('is_expanded', True)
            )
            db.session.add(section)

            for j, q_data in enumerate(sec_data.get('content', [])):
                q_id = q_data.get('id')
                if not q_id:
                    q_id = f'autogen_q_{i}_{j}'

                q = ImmoQuestion(
                    id=q_id,
                    section_id=section.id,
                    label=q_data.get('label', ''),
                    type=q_data.get('type', 'text'),
                    width=q_data.get('width', 'half'),
                    tooltip=q_data.get('tooltip', ''),
                    options_json=json.dumps(q_data.get('options', [])),
                    types_json=json.dumps(q_data.get('types', [])),
                    order=j
                )
                db.session.add(q)

        db.session.commit()
        print("✅ Import erfolgreich.")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Fehler beim Import: {e}")
        # Re-raise damit der Caller (Route) den Fehler 500 werfen kann
        raise e


def send_async_email(app, msg):
    """Hilfsfunktion für Threading."""
    with app.app_context():
        try:
            with mail.connect() as conn:
                conn.send(msg)
            print(f"✅ E-Mail an {msg.recipients} versendet.")
        except Exception as e:
            print(f"❌ Fehler beim E-Mail Versand: {e}")


def send_reset_email(user):
    """Generiert Token und sendet Reset-Mail via Auth-Blueprint."""
    token = user.get_reset_token()

    # Verweist auf auth.reset_token -> /auth/reset_password/<token>
    reset_url = url_for('auth.reset_token', token=token, _external=True)

    msg = Message('Passwort zurücksetzen - Vereins-Portal',
                  recipients=[user.email])

    msg.body = f'''Hallo {user.username},

Um dein Passwort zurückzusetzen, klicke bitte auf den folgenden Link:
{reset_url}

Dieser Link ist 30 Minuten gültig.
Wenn du dies nicht angefordert hast, ignoriere diese E-Mail einfach.
'''

    # Asynchron senden
    app = current_app._get_current_object()
    threading.Thread(target=send_async_email, args=(app, msg)).start()