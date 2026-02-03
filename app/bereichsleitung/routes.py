import json
from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.decorators import permission_required
from app.models import Verein, Anbaustelle, Ausgabestelle, User, StatusDefinition, GERMAN_STATES
from app.bereichsleitung import bp


# --- HELPER ---
def is_admin():
    return current_user.is_admin


@bp.route('/', methods=['GET'])
@login_required
@permission_required('bl_user')
def index():
    # Daten laden
    vereine = Verein.query.order_by(Verein.name).all() if is_admin() else current_user.managed_vereine

    # Anbaustellen: Admin sieht alle, BL sieht nur die verknüpften
    all_anbaustellen = Anbaustelle.query.all()
    if is_admin():
        visible_anbaustellen = all_anbaustellen
    else:
        # Nur die Anbaustellen der eigenen Vereine
        visible_anbaustellen = list({v.anbaustelle for v in vereine if v.anbaustelle})

    # Abgabestellen
    ausgabestellen = []
    if is_admin():
        ausgabestellen = Ausgabestelle.query.all()
    else:
        for v in vereine:
            ausgabestellen.extend(v.ausgabestellen)

    return render_template(
        'bereichsleitung/index.html',
        mein_verein=current_user.verein,
        vereine=vereine,
        anbaustellen=visible_anbaustellen,
        all_anbaustellen_options=all_anbaustellen,
        ausgabestellen=ausgabestellen,
        states=GERMAN_STATES,
        # NEU: Status Options aus der DB laden (nicht mehr hardcoded)
        # Wir übergeben hier keine Tuple-Liste mehr, sondern Objekte.
        # Das Template muss angepasst werden (siehe unten) oder wir mappen es hier.
        # Aber da wir index.html eh für Detail-Links umgebaut haben, wird das Dropdown dort
        # vermutlich gar nicht mehr für Inline-Edit genutzt, sondern nur für Anzeige.
        # Falls doch, ist es sicherer, das Status-Objekt im Verein-Model direkt zu nutzen.
    )


# ==============================================================================
# CREATE & DELETE (NUR ADMIN)
# ==============================================================================

@bp.route('/create/<type>', methods=['POST'])
@login_required
def create_entity(type):
    if not is_admin():
        flash('Nur für Admins.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    try:
        if type == 'verein':
            # Default Status setzen
            def_stat = StatusDefinition.query.filter_by(context='verein').order_by(StatusDefinition.position).first()
            v = Verein(name=request.form.get('name'), city=request.form.get('city'))
            if def_stat: v.status_id = def_stat.id
            db.session.add(v)

        elif type == 'anbau':
            # Default Status setzen
            def_stat = StatusDefinition.query.filter_by(context='anbau').order_by(StatusDefinition.position).first()
            a = Anbaustelle(name=request.form.get('name'), anbau_type=request.form.get('type'))
            if def_stat: a.status_id = def_stat.id
            db.session.add(a)

        elif type == 'abgabe':
            def_stat = StatusDefinition.query.filter_by(context='ausgabe').order_by(StatusDefinition.position).first()
            v_id = request.form.get('verein_id')
            if not v_id:
                flash('Ausgabestelle benötigt einen Verein.', 'warning')
                return redirect(url_for('bereichsleitung.index'))
            a = Ausgabestelle(address=request.form.get('address'), verein_id=v_id)
            if def_stat: a.status_id = def_stat.id
            db.session.add(a)

        db.session.commit()
        flash(f'{type.capitalize()} angelegt.', 'success')
    except Exception as e:
        flash(f'Fehler: {e}', 'danger')

    return redirect(url_for('bereichsleitung.index'))


@bp.route('/delete/<type>/<int:id>', methods=['POST'])
@login_required
def delete_entity(type, id):
    if not is_admin():
        flash('Nur für Admins.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    try:
        obj = None
        if type == 'verein':
            obj = db.session.get(Verein, id)
        elif type == 'anbau':
            obj = db.session.get(Anbaustelle, id)
        elif type == 'abgabe':
            obj = db.session.get(Ausgabestelle, id)

        if obj:
            db.session.delete(obj)
            db.session.commit()
            flash('Erfolgreich gelöscht.', 'success')
        else:
            flash('Objekt nicht gefunden.', 'warning')
    except Exception as e:
        flash(f'Löschen fehlgeschlagen (Abhängigkeiten?): {e}', 'danger')

    return redirect(url_for('bereichsleitung.index'))


# ==============================================================================
# DETAIL PAGES (EDIT)
# ==============================================================================

@bp.route('/vereine/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('bl_user')
def verein_detail(id):
    """Detailansicht und Bearbeitung eines Vereins."""
    verein = db.session.get(Verein, id)
    if not verein:
        flash('Verein nicht gefunden.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    if not current_user.is_admin and verein not in current_user.managed_vereine:
        flash('Keine Berechtigung.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    if request.method == 'POST':
        # 1. Stammdaten
        verein.name = request.form.get('name')
        verein.city = request.form.get('city')
        verein.zip_code = request.form.get('zip_code')
        verein.state_seat = request.form.get('state_seat')
        verein.state_dist = request.form.get('state_dist')

        # 2. Status (NEU: ID speichern)
        status_id = request.form.get('status')  # Dropdown liefert ID
        if status_id:
            verein.status_id = int(status_id)

        verein.is_ev = 'is_ev' in request.form
        verein.board_member = request.form.get('board_member')
        verein.prev_officer = request.form.get('prev_officer')

        # 3. Anbaustelle (mit VALIDIERUNG für Einzel-Typ)
        anbau_id = request.form.get('anbaustelle_id')
        new_anbau_id = int(anbau_id) if anbau_id and anbau_id != 'none' else None

        if new_anbau_id:
            target_anbau = db.session.get(Anbaustelle, new_anbau_id)
            if target_anbau:
                if target_anbau.anbau_type == 'einzel':
                    besetzer = [v for v in target_anbau.vereine if v.id != verein.id]
                    if besetzer:
                        flash(
                            f"Fehler: Die Anbaustelle '{target_anbau.name}' ist ein Einzelstandort und bereits belegt.",
                            'danger')
                        return redirect(url_for('bereichsleitung.verein_detail', id=id))
            verein.anbaustelle_id = new_anbau_id
        else:
            verein.anbaustelle_id = None

        # 4. Ausgabestelle
        new_ausgabe_id = request.form.get('ausgabestelle_id')
        if new_ausgabe_id and new_ausgabe_id != 'none':
            aus = db.session.get(Ausgabestelle, int(new_ausgabe_id))
            if aus:
                for old_aus in verein.ausgabestellen: old_aus.verein_id = None
                aus.verein_id = verein.id
        elif new_ausgabe_id == 'none':
            for old_aus in verein.ausgabestellen: old_aus.verein_id = None

        # 5. Manager
        manager_ids = request.form.getlist('manager_ids')
        if manager_ids:
            verein.managers = User.query.filter(User.id.in_(manager_ids)).all()
        else:
            verein.managers = []

        db.session.commit()
        flash(f'Verein "{verein.name}" gespeichert.', 'success')
        return redirect(url_for('bereichsleitung.verein_detail', id=id))

    # GET
    all_anbaustellen = Anbaustelle.query.all()
    all_ausgabestellen = Ausgabestelle.query.all()
    potential_managers = User.query.filter(User.permissions.any(slug='bl_bl')).all()
    current_ausgabe = verein.ausgabestellen[0] if verein.ausgabestellen else None

    # NEU: Status aus DB laden
    status_options = StatusDefinition.query.filter_by(context='verein').order_by(StatusDefinition.position).all()

    return render_template(
        'bereichsleitung/verein_detail.html',
        verein=verein,
        states=GERMAN_STATES,
        all_anbaustellen=all_anbaustellen,
        all_ausgabestellen=all_ausgabestellen,
        current_ausgabe=current_ausgabe,
        potential_managers=potential_managers,
        status_options=status_options  # Übergibt Liste von Objekten (id, name)
    )


@bp.route('/anbau/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('bl_user')
def anbau_detail(id):
    """Detailansicht Anbaustelle."""
    anbau = db.session.get(Anbaustelle, id)
    if not anbau:
        return redirect(url_for('bereichsleitung.index'))

    if not current_user.is_admin:
        is_relevant = any(v in current_user.managed_vereine for v in anbau.vereine)
        if not is_relevant:
            return redirect(url_for('bereichsleitung.index'))

    if request.method == 'POST':
        anbau.name = request.form.get('name')
        anbau.address = request.form.get('address')
        anbau.state = request.form.get('state')

        # Status speichern
        stat_id = request.form.get('status')
        if stat_id: anbau.status_id = int(stat_id)

        db.session.commit()
        flash('Anbaustelle gespeichert.', 'success')
        return redirect(url_for('bereichsleitung.anbau_detail', id=id))

    # Status Optionen laden
    status_options = StatusDefinition.query.filter_by(context='anbau').order_by(StatusDefinition.position).all()

    return render_template(
        'bereichsleitung/anbau_detail.html',
        anbau=anbau,
        states=GERMAN_STATES,
        status_options=status_options
    )


@bp.route('/ausgabe/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('bl_user')
def ausgabe_detail(id):
    """Detailansicht Ausgabestelle."""
    ausgabe = db.session.get(Ausgabestelle, id)
    if not ausgabe:
        return redirect(url_for('bereichsleitung.index'))

    if not current_user.is_admin and ausgabe.verein not in current_user.managed_vereine:
        return redirect(url_for('bereichsleitung.index'))

    if request.method == 'POST':
        ausgabe.address = request.form.get('address')
        ausgabe.state = request.form.get('state')

        stat_id = request.form.get('status')
        if stat_id: ausgabe.status_id = int(stat_id)

        new_verein_id = request.form.get('verein_id')
        if new_verein_id:
            ausgabe.verein_id = int(new_verein_id)

        db.session.commit()
        flash('Abgabestelle gespeichert.', 'success')
        return redirect(url_for('bereichsleitung.ausgabe_detail', id=id))

    if current_user.is_admin:
        available_vereine = Verein.query.order_by(Verein.name).all()
    else:
        available_vereine = current_user.managed_vereine

    status_options = StatusDefinition.query.filter_by(context='ausgabe').order_by(StatusDefinition.position).all()

    return render_template(
        'bereichsleitung/ausgabe_detail.html',
        ausgabe=ausgabe,
        states=GERMAN_STATES,
        vereine=available_vereine,
        status_options=status_options
    )


# ==============================================================================
# IMPORTS & ADMIN (STATUS)
# ==============================================================================

@bp.route('/import/<type>', methods=['POST'])
@login_required
def import_data(type):
    if not is_admin(): return redirect(url_for('bereichsleitung.index'))

    file = request.files.get('file')
    if not file: return redirect(url_for('bereichsleitung.index'))

    try:
        data = json.load(file)
        count = 0

        # Default Stati laden (Cache)
        def_v = StatusDefinition.query.filter_by(context='verein').order_by(StatusDefinition.position).first()
        def_a = StatusDefinition.query.filter_by(context='anbau').order_by(StatusDefinition.position).first()
        def_dist = StatusDefinition.query.filter_by(context='ausgabe').order_by(StatusDefinition.position).first()

        if type == 'vereine':
            for entry in data:
                v = Verein.query.filter_by(name=entry.get('name')).first()
                if not v:
                    v = Verein(name=entry.get('name'))
                    if def_v: v.status_id = def_v.id
                    db.session.add(v)

                v.city = entry.get('city')
                v.zip_code = entry.get('zip_code')
                v.state_seat = entry.get('state_seat')
                # JSON Status als String mappen? Hier einfachheitshalber ignorieren oder suchen
                # Falls JSON "status": "Gegründet" enthält:
                if 'status' in entry:
                    s_obj = StatusDefinition.query.filter_by(context='verein', name=entry['status']).first()
                    if s_obj: v.status_id = s_obj.id

                count += 1

        elif type == 'anbau':
            for entry in data:
                a = Anbaustelle.query.filter_by(name=entry.get('name')).first()
                if not a:
                    a = Anbaustelle(name=entry.get('name'))
                    if def_a: a.status_id = def_a.id
                    db.session.add(a)
                a.address = entry.get('address')
                a.state = entry.get('state')
                a.anbau_type = entry.get('type', 'einzel')
                count += 1

        elif type == 'abgabe':
            for entry in data:
                v_name = entry.get('verein_name')
                verein = Verein.query.filter_by(name=v_name).first()
                if verein:
                    aus = Ausgabestelle(address=entry.get('address'), state=entry.get('state'), verein=verein)
                    if def_dist: aus.status_id = def_dist.id
                    db.session.add(aus)
                    count += 1

        db.session.commit()
        flash(f'Import ({type}) erfolgreich: {count} Einträge.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Import Fehler: {e}', 'danger')

    return redirect(url_for('bereichsleitung.index'))


# --- STATUS ADMIN ROUTEN (Wie zuvor besprochen) ---

@bp.route('/status/manage', methods=['GET'])
@login_required
def manage_status():
    if not is_admin(): return redirect(url_for('bereichsleitung.index'))
    stati = StatusDefinition.query.order_by(StatusDefinition.context, StatusDefinition.position).all()
    grouped = {'verein': [], 'anbau': [], 'ausgabe': []}
    for s in stati:
        if s.context in grouped: grouped[s.context].append(s)
    return render_template('bereichsleitung/admin_status.html', grouped=grouped)


@bp.route('/status/add', methods=['POST'])
@login_required
def add_status():
    if not is_admin(): return redirect(url_for('bereichsleitung.index'))
    name = request.form.get('name')
    context = request.form.get('context')
    reorder_statuses(context)
    last = StatusDefinition.query.filter_by(context=context).order_by(StatusDefinition.position.desc()).first()
    new_pos = (last.position + 1) if last else 0
    db.session.add(StatusDefinition(name=name, context=context, position=new_pos))
    db.session.commit()
    return redirect(url_for('bereichsleitung.manage_status'))


@bp.route('/status/delete/<int:id>', methods=['POST'])
@login_required
def delete_status(id):
    if not is_admin(): return redirect(url_for('bereichsleitung.index'))
    status = db.session.get(StatusDefinition, id)
    if not status: return redirect(url_for('bereichsleitung.manage_status'))

    context = status.context
    default = StatusDefinition.query.filter(StatusDefinition.context == context, StatusDefinition.id != id).order_by(
        StatusDefinition.position).first()

    if not default:
        flash('Letzter Status kann nicht gelöscht werden.', 'danger')
        return redirect(url_for('bereichsleitung.manage_status'))

    # Update Entities
    if context == 'verein':
        Verein.query.filter_by(status_id=id).update({'status_id': default.id})
    elif context == 'anbau':
        Anbaustelle.query.filter_by(status_id=id).update({'status_id': default.id})
    elif context == 'ausgabe':
        Ausgabestelle.query.filter_by(status_id=id).update({'status_id': default.id})

    db.session.delete(status)
    db.session.commit()

    reorder_statuses(context)
    flash('Status gelöscht. Lücken wurden geschlossen.', 'success')
    return redirect(url_for('bereichsleitung.manage_status'))


@bp.route('/status/move/<int:id>/<direction>', methods=['POST'])
@login_required
def move_status(id, direction):
    if not is_admin(): return redirect(url_for('bereichsleitung.index'))

    status = db.session.get(StatusDefinition, id)
    if not status: return redirect(url_for('bereichsleitung.manage_status'))

    # 1. Liste laden und normalisieren (falls Lücken da waren)
    context = status.context
    reorder_statuses(context)  # Stellt sicher: 0, 1, 2, 3...

    # 2. Liste neu laden (jetzt sauber)
    items = StatusDefinition.query.filter_by(context=context).order_by(StatusDefinition.position).all()

    # 3. Index finden
    try:
        curr_idx = items.index(status)
    except ValueError:
        return redirect(url_for('bereichsleitung.manage_status'))  # Sollte nicht passieren

    # 4. Tauschen in der Python-Liste
    if direction == 'up' and curr_idx > 0:
        items[curr_idx], items[curr_idx - 1] = items[curr_idx - 1], items[curr_idx]

    elif direction == 'down' and curr_idx < len(items) - 1:
        items[curr_idx], items[curr_idx + 1] = items[curr_idx + 1], items[curr_idx]

    # 5. Positionen basierend auf neuer Listen-Reihenfolge speichern
    for idx, item in enumerate(items):
        item.position = idx

    db.session.commit()
    return redirect(url_for('bereichsleitung.manage_status'))


def reorder_statuses(context):
    """
    Nummeriert alle Stati eines Kontextes sauber von 0 bis N durch.
    Schließt Lücken (z.B. nach Löschen).
    """
    # Alle holen, sortiert nach aktueller Position
    items = StatusDefinition.query.filter_by(context=context).order_by(StatusDefinition.position).all()

    for idx, item in enumerate(items):
        item.position = idx  # 0, 1, 2, 3... erzwingen

    db.session.commit()
