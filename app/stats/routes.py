import csv
import io
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from flask import render_template, redirect, url_for, flash, jsonify, request
from flask import jsonify, request, make_response
from flask_login import login_required
from app.extensions import db
from app.models import MarketStat
from app.decorators import permission_required
from app.stats import bp

URL_SOURCE = "https://anbauverband.de/antrags-und-genehmigungszahlen/"


@bp.route('/', methods=['GET'])
def index():
    """Zeigt das Dashboard an."""
    stats = MarketStat.query.all()

    # Sortierung: Deutschlandweit (Summe) + Alphabetisch
    # Wir bauen das JSON für das Frontend direkt hier oder im Template.
    # Wir übergeben die Stats einfach an Jinja.

    # Prüfen, ob überhaupt Daten da sind
    has_data = len(stats) > 0
    last_update = stats[0].last_scraped if has_data else None

    return render_template('stats/index.html', stats=stats, has_data=has_data, last_update=last_update)


@bp.route('/sync', methods=['POST'])
@login_required
@permission_required('stats_access')
def sync_data():
    """Liest die Daten von anbauverband.de ein."""
    try:
        response = requests.get(URL_SOURCE, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Tabelle finden (meistens die erste oder einzige Table)
        table = soup.find('table')
        if not table:
            raise Exception("Keine Tabelle auf der Zielseite gefunden.")

        rows = table.find_all('tr')

        # Wir gehen davon aus, dass die erste Zeile der Header ist.
        # Wir starten ab Zeile 1 (Index 0 ist Header).
        # Manchmal ist der Header in <thead>, Body in <tbody>.
        # Wir iterieren einfach und prüfen auf Inhalt.

        count = 0
        for row in rows:
            cols = row.find_all('td')
            if not cols: continue  # Header Zeile mit <th> überspringen

            # Sicherheitscheck: Erwartet werden mind. 6 Spalten
            if len(cols) < 6: continue

            # Helper um Text zu Zahl zu wandeln (entfernt Punkte etc.)
            def parse_int(col):
                txt = col.get_text(strip=True).replace('.', '')
                if not txt or txt == '-': return 0
                if not txt.isnumeric(): return 0
                return int(txt)

            state_name = cols[0].get_text(strip=True)

            # Wir wollen "Summe" oder "Gesamt" oft ausschließen,
            # aber du wolltest es berechnen. Falls die Webseite eine Summenzeile hat,
            # ignorieren wir sie lieber und rechnen selbst, um Konsistenz zu wahren.
            if "Summe" in state_name or "Gesamt" in state_name:
                continue

            # Datenbank Update oder Insert (Upsert)
            stat = MarketStat.query.filter_by(state_name=state_name).first()
            if not stat:
                stat = MarketStat(state_name=state_name)
                db.session.add(stat)

            stat.applied = parse_int(cols[1])
            stat.approved = parse_int(cols[2])
            stat.rejected = parse_int(cols[3])
            stat.withdrawn = parse_int(cols[4])
            stat.data_date = cols[5].get_text(strip=True)
            stat.last_scraped = datetime.utcnow()

            count += 1

        db.session.commit()
        flash(f"Erfolgreich synchronisiert! {count} Bundesländer aktualisiert.", "success")

    except Exception as e:
        flash(f"Fehler beim Synchronisieren: {str(e)}", "danger")

    return redirect(url_for('stats.index'))


# NEU: Route zum Speichern der Mariana Zahlen
@bp.route('/update_mariana', methods=['POST'])
@login_required
@permission_required('stats_access')
def update_mariana():
    """Speichert die Mariana-Zahlen für ALLE Bundesländer gleichzeitig."""
    try:
        # Alle Stats laden
        all_stats = MarketStat.query.all()
        count = 0

        for stat in all_stats:
            # Wir erwarten Form-Felder im Format: "m_applied_ID", "m_approved_ID" etc.
            prefix = str(stat.id)

            # Helper: Wert holen, leere Strings zu 0, Integer parsen
            def get_val(name):
                raw = request.form.get(f'{name}_{prefix}')
                if not raw: return 0
                return int(raw)

            # Werte setzen
            # Wir prüfen, ob der Key überhaupt im Request ist (zur Sicherheit)
            if f'm_applied_{prefix}' in request.form:
                stat.mariana_applied = get_val('m_applied')
                stat.mariana_approved = get_val('m_approved')
                stat.mariana_rejected = get_val('m_rejected')
                stat.mariana_withdrawn = get_val('m_withdrawn')
                count += 1

        db.session.commit()
        flash(f"Erfolgreich gespeichert! ({count} Datensätze aktualisiert)", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Fehler beim Speichern: {e}", "danger")

    return redirect(url_for('stats.index'))


MARIANA_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQk7raieqSwVtFn6cD0KiQXpet7Ojx8QCAHsxeyek50HYJu5bCT1cET9jiCa7DOZQ/pub?output=csv&gid=1584782275"


@bp.route('/fetch_mariana_sheet', methods=['GET'])
@login_required
@permission_required('stats_access')
def fetch_mariana_sheet():
    """
    Lädt die Mariana-Daten aus dem Google Sheet anhand fester Koordinaten.
    """
    try:
        response = requests.get(MARIANA_SHEET_URL)
        response.raise_for_status()

        # CSV in eine Liste von Listen umwandeln (Das Raster)
        decoded_content = response.content.decode('utf-8')
        # Wir nutzen list(csv.reader(...)) um das komplette Grid im Speicher zu haben
        grid = list(csv.reader(io.StringIO(decoded_content), delimiter=','))

        # --- KONFIGURATION DER KOORDINATEN ---
        # Format: 'Bundesland Name in DB': (Zeilen-Index, Spalten-Index)
        # HINWEIS: Zeile 1 in Excel ist Index 0. Spalte A ist Index 0.
        # Beispiel: Wert steht in C5 -> Zeile 4, Spalte 2

        SHEET_COORDS = {
            'Baden-Württemberg': (5, 75),  # <--- BITTE ÄNDERN
            'Bayern': (58, 5),  # <--- BITTE ÄNDERN
            'Berlin': (8, 95),  # <--- BITTE ÄNDERN
            'Brandenburg': (5, 95),  # <--- BITTE ÄNDERN
            'Bremen': (5, 65),  # <--- BITTE ÄNDERN
            'Hamburg': (5, 88),  # <--- BITTE ÄNDERN
            'Hessen': (5, 69),  # <--- BITTE ÄNDERN
            'Mecklenburg-Vorpommern': (5, 80),  # <--- BITTE ÄNDERN
            'Niedersachsen': (62, 7),  # <--- BITTE ÄNDERN
            'Nordrhein-Westfalen': (69, 8),  # <--- BITTE ÄNDERN
            'Rheinland-Pfalz': (8, 80),  # <--- BITTE ÄNDERN
            'Saarland': (8, 88),  # <--- BITTE ÄNDERN
            'Sachsen': (8, 101),  # <--- BITTE ÄNDERN
            'Sachsen-Anhalt': (5, 101),  # <--- BITTE ÄNDERN
            'Schleswig-Holstein': (8, 75),  # <--- BITTE ÄNDERN
            'Thüringen': (85, 8),  # <--- BITTE ÄNDERN
        }

        data_map = {}

        for state, (row_idx, col_idx) in SHEET_COORDS.items():
            try:
                # Prüfen, ob die Zelle existiert
                if row_idx < len(grid) and col_idx < len(grid[row_idx]):
                    raw_val = grid[row_idx][col_idx].strip()

                    # Leere Felder zu 0
                    if not raw_val:
                        val = 0
                    else:
                        # Entferne Punkte (Tausendertrennzeichen) und parse Int
                        # Falls da Text steht ("ca. 10"), entfernen wir alles was keine Zahl ist?
                        # Besser: Wir versuchen strikt zu parsen, sonst 0
                        clean_val = ''.join(filter(str.isdigit, raw_val))
                        val = int(clean_val) if clean_val else 0

                    data_map[state] = val
                else:
                    # Koordinate außerhalb der CSV
                    data_map[state] = 0

            except Exception:
                # Fallback bei Fehler
                data_map[state] = 0

        return jsonify({"success": True, "data": data_map})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
