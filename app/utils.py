import os
import json
from app.extensions import db
from app.models import ImmoSection, ImmoQuestion


def import_json_data(data):
    """Importiert JSON Struktur in die DB (löscht alte Daten!)"""
    try:
        ImmoQuestion.query.delete()
        ImmoSection.query.delete()

        for i, sec_data in enumerate(data):
            sec_id = sec_data.get('id')
            if not sec_id: sec_id = f'autogen_sec_{i}'

            section = ImmoSection(
                id=sec_id,
                title=sec_data.get('title', 'Unbenannt'),
                order=i,
                is_expanded=sec_data.get('is_expanded', True)
            )
            db.session.add(section)

            for j, q_data in enumerate(sec_data.get('content', [])):
                q_id = q_data.get('id')
                if not q_id: q_id = f'autogen_q_{i}_{j}'

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
        raise e