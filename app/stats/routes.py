import requests
from bs4 import BeautifulSoup
from datetime import datetime
from flask import render_template, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.extensions import db
from app.models import MarketStat
from app.decorators import permission_required
from app.stats import bp

URL_SOURCE = "https://anbauverband.de/antrags-und-genehmigungszahlen/"


@bp.route('/', methods=['GET'])
@login_required
@permission_required('stats_access')
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