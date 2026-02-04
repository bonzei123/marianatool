import json
from flask import render_template, request, flash, redirect, url_for, jsonify
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

        # FIX: Sortierung nach position
        all_statuses=StatusDefinition.query.order_by(StatusDefinition.position).all(),

        # FIX: Alle User laden (auch Admins), damit Dropdown nicht leer ist
        all_users=User.query.order_by(User.username).all(),

        all_clusters=Anbaustelle.query.filter_by(anbau_type='cluster').all()
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
            def_stat = StatusDefinition.query.filter_by(context='verein').order_by(StatusDefinition.position).first()
            v = Verein(name=request.form.get('name'), city=request.form.get('city'))
            if def_stat: v.status_id = def_stat.id
            db.session.add(v)

        elif type == 'anbau':
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

    mapping = {'verein': '#clubs', 'anbau': '#grow', 'abgabe': '#dist'}
    return redirect(url_for('bereichsleitung.index') + mapping.get(type, ''))


@bp.route('/delete/<type>/<int:id>', methods=['POST'])
@login_required
def delete_entity(type, id):
    if not is_admin():
        flash('Nur für Admins.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    try:
        model_map = {'verein': Verein, 'anbau': Anbaustelle, 'abgabe': Ausgabestelle}
        ModelClass = model_map.get(type)

        if ModelClass:
            obj = db.session.get(ModelClass, id)
            if obj:
                db.session.delete(obj)
                db.session.commit()
                flash('Erfolgreich gelöscht.', 'success')
            else:
                flash('Objekt nicht gefunden.', 'warning')
    except Exception as e:
        flash(f'Löschen fehlgeschlagen (Abhängigkeiten?): {e}', 'danger')

    mapping = {'verein': '#clubs', 'anbau': '#grow', 'abgabe': '#dist'}
    return redirect(url_for('bereichsleitung.index') + mapping.get(type, ''))


# ==============================================================================
# DETAIL PAGES (EDIT)
# ==============================================================================

@bp.route('/vereine/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('bl_user')
def verein_detail(id):
    verein = db.session.get(Verein, id)
    if not verein:
        flash('Verein nicht gefunden.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    if not current_user.is_admin and verein not in current_user.managed_vereine:
        flash('Keine Berechtigung.', 'danger')
        return redirect(url_for('bereichsleitung.index'))

    if request.method == 'POST':
        verein.name = request.form.get('name')
        verein.city = request.form.get('city')
        verein.zip_code = request.form.get('zip_code')
        verein.state_seat = request.form.get('state_seat')
        verein.state_dist = request.form.get('state_dist')

        status_id = request.form.get('status')
        if status_id:
            verein.status_id = int(status_id)

        verein.is_ev = 'is_ev' in request.form
        verein.board_member = request.form.get('board_member')
        verein.prev_officer = request.form.get('prev_officer')

        anbau_id = request.form.get('anbaustelle_id')
        new_anbau_id = int(anbau_id) if anbau_id and anbau_id != 'none' else None

        if new_anbau_id:
            target_anbau = db.session.get(Anbaustelle, new_anbau_id)
            if target_anbau and target_anbau.anbau_type == 'einzel':
                besetzer = [v for v in target_anbau.vereine if v.id != verein.id]
                if besetzer:
                    flash(f"Fehler: '{target_anbau.name}' ist belegt.", 'danger')
                    return redirect(url_for('bereichsleitung.verein_detail', id=id))
            verein.anbaustelle_id = new_anbau_id
        else:
            verein.anbaustelle_id = None

        new_ausgabe_id = request.form.get('ausgabestelle_id')
        if new_ausgabe_id and new_ausgabe_id != 'none':
            aus = db.session.get(Ausgabestelle, int(new_ausgabe_id))
            if aus:
                for old_aus in verein.ausgabestellen: old_aus.verein_id = None
                aus.verein_id = verein.id
        elif new_ausgabe_id == 'none':
            for old_aus in verein.ausgabestellen: old_aus.verein_id = None

        manager_ids = request.form.getlist('manager_ids')
        if manager_ids:
            verein.managers = User.query.filter(User.id.in_(manager_ids)).all()
        else:
            verein.managers = []

        db.session.commit()
        flash(f'Verein "{verein.name}" gespeichert.', 'success')
        return redirect(url_for('bereichsleitung.verein_detail', id=id))

    all_anbaustellen = Anbaustelle.query.all()
    all_ausgabestellen = Ausgabestelle.query.all()
    potential_managers = User.query.all()  # Vereinfacht: Alle User können Manager sein
    current_ausgabe = verein.ausgabestellen[0] if verein.ausgabestellen else None
    status_options = StatusDefinition.query.filter_by(context='verein').order_by(StatusDefinition.position).all()

    return render_template(
        'bereichsleitung/verein_detail.html',
        verein=verein,
        states=GERMAN_STATES,
        all_anbaustellen=all_anbaustellen,
        all_ausgabestellen=all_ausgabestellen,
        current_ausgabe=current_ausgabe,
        potential_managers=potential_managers,
        status_options=status_options
    )


@bp.route('/anbau/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('bl_user')
def anbau_detail(id):
    anbau = db.session.get(Anbaustelle, id)
    if not anbau: return redirect(url_for('bereichsleitung.index'))

    if not current_user.is_admin:
        is_relevant = any(v in current_user.managed_vereine for v in anbau.vereine)
        if not is_relevant: return redirect(url_for('bereichsleitung.index'))

    if request.method == 'POST':
        anbau.name = request.form.get('name')
        anbau.address = request.form.get('address')
        anbau.state = request.form.get('state')
        stat_id = request.form.get('status')
        if stat_id: anbau.status_id = int(stat_id)
        db.session.commit()
        flash('Anbaustelle gespeichert.', 'success')
        return redirect(url_for('bereichsleitung.anbau_detail', id=id))

    status_options = StatusDefinition.query.filter_by(context='anbau').order_by(StatusDefinition.position).all()
    return render_template('bereichsleitung/anbau_detail.html', anbau=anbau, states=GERMAN_STATES,
                           status_options=status_options)


@bp.route('/ausgabe/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('bl_user')
def ausgabe_detail(id):
    ausgabe = db.session.get(Ausgabestelle, id)
    if not ausgabe: return redirect(url_for('bereichsleitung.index'))

    if not current_user.is_admin and ausgabe.verein not in current_user.managed_vereine:
        return redirect(url_for('bereichsleitung.index'))

    if request.method == 'POST':
        ausgabe.address = request.form.get('address')
        ausgabe.state = request.form.get('state')
        stat_id = request.form.get('status')
        if stat_id: ausgabe.status_id = int(stat_id)
        new_verein_id = request.form.get('verein_id')
        if new_verein_id: ausgabe.verein_id = int(new_verein_id)
        db.session.commit()
        flash('Abgabestelle gespeichert.', 'success')
        return redirect(url_for('bereichsleitung.ausgabe_detail', id=id))

    available_vereine = Verein.query.order_by(
        Verein.name).all() if current_user.is_admin else current_user.managed_vereine
    status_options = StatusDefinition.query.filter_by(context='ausgabe').order_by(StatusDefinition.position).all()
    return render_template('bereichsleitung/ausgabe_detail.html', ausgabe=ausgabe, states=GERMAN_STATES,
                           vereine=available_vereine, status_options=status_options)


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
                if 'status_id' in entry: v.status_id = entry['status_id']  # changed to status_id from json
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
                if 'status_id' in entry: a.status_id = entry['status_id']
                count += 1

        elif type == 'abgabe':
            for entry in data:
                v_name = entry.get('verein_name')
                verein = Verein.query.filter_by(name=v_name).first()
                if verein:
                    aus = Ausgabestelle(address=entry.get('address'), state=entry.get('state'), verein=verein)
                    if def_dist: aus.status_id = def_dist.id
                    if 'status_id' in entry: aus.status_id = entry['status_id']
                    db.session.add(aus)
                    count += 1

        db.session.commit()
        flash(f'Import ({type}) erfolgreich: {count} Einträge.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Import Fehler: {e}', 'danger')

    return redirect(url_for('bereichsleitung.index'))


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

    if context == 'verein':
        Verein.query.filter_by(status_id=id).update({'status_id': default.id})
    elif context == 'anbau':
        Anbaustelle.query.filter_by(status_id=id).update({'status_id': default.id})
    elif context == 'ausgabe':
        Ausgabestelle.query.filter_by(status_id=id).update({'status_id': default.id})

    db.session.delete(status)
    db.session.commit()
    reorder_statuses(context)
    return redirect(url_for('bereichsleitung.manage_status'))


@bp.route('/status/move/<int:id>/<direction>', methods=['POST'])
@login_required
def move_status(id, direction):
    if not is_admin(): return redirect(url_for('bereichsleitung.index'))
    status = db.session.get(StatusDefinition, id)
    if not status: return redirect(url_for('bereichsleitung.manage_status'))
    context = status.context
    reorder_statuses(context)
    items = StatusDefinition.query.filter_by(context=context).order_by(StatusDefinition.position).all()
    try:
        curr_idx = items.index(status)
    except ValueError:
        return redirect(url_for('bereichsleitung.manage_status'))

    if direction == 'up' and curr_idx > 0:
        items[curr_idx], items[curr_idx - 1] = items[curr_idx - 1], items[curr_idx]
    elif direction == 'down' and curr_idx < len(items) - 1:
        items[curr_idx], items[curr_idx + 1] = items[curr_idx + 1], items[curr_idx]

    for idx, item in enumerate(items): item.position = idx
    db.session.commit()
    return redirect(url_for('bereichsleitung.manage_status'))


def reorder_statuses(context):
    items = StatusDefinition.query.filter_by(context=context).order_by(StatusDefinition.position).all()
    for idx, item in enumerate(items): item.position = idx
    db.session.commit()


# ... (Imports und andere Routen bleiben gleich)

@bp.route('/bulk-update/<string:entity_type>', methods=['POST'])
@login_required
@permission_required('bl_user')
def bulk_update(entity_type):
    data = request.get_json()
    ids = data.get('ids', [])
    changes = data.get('changes', {})

    if not ids or not changes:
        return jsonify({"success": False, "error": "Keine Änderungen übermittelt."}), 400

    model_map = {'verein': Verein, 'anbau': Anbaustelle, 'abgabe': Ausgabestelle}
    ModelClass = model_map.get(entity_type)
    if not ModelClass: return jsonify({"success": False, "error": "Ungültiger Typ"}), 400

    # --- HIER DIE ÄNDERUNG ---
    # Wir entfernen alles außer Status (generell) und den spez. Verein-Feldern
    allowed_fields = {
        'verein': ['status_id', 'is_ev', 'anbaustelle_id'],  # manager_id wird separat behandelt
        'anbau': ['status_id'],
        'abgabe': ['status_id']
    }
    # -------------------------

    current_allowed = allowed_fields.get(entity_type, [])

    # Manager wird separat aus dem Dict geholt (da M2M Beziehung)
    new_manager_id = changes.pop('manager_id', None)

    clean_changes = {}
    for key, value in changes.items():
        if key in current_allowed and value is not None and value != "":
            clean_changes[key] = value

    if not clean_changes and not new_manager_id:
        return jsonify({"success": False, "error": "Keine gültigen Änderungen."}), 400

    try:
        if clean_changes:
            db.session.execute(db.update(ModelClass).where(ModelClass.id.in_(ids)).values(clean_changes))

        # Manager Update nur für Verein erlaubt
        if new_manager_id and entity_type == 'verein':
            if new_manager_id != "":
                manager = db.session.get(User, int(new_manager_id))
                if manager:
                    vereine = db.session.query(Verein).filter(Verein.id.in_(ids)).all()
                    for v in vereine:
                        v.managers = [manager]

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/bulk-delete/<string:entity_type>', methods=['POST'])
@login_required
@permission_required('admin')
def bulk_delete(entity_type):
    data = request.get_json()
    ids = data.get('ids', [])
    model_map = {'verein': Verein, 'anbau': Anbaustelle, 'abgabe': Ausgabestelle}
    ModelClass = model_map.get(entity_type)
    if not ModelClass or not ids: return jsonify({"success": False, "error": "Fehler"}), 400
    try:
        db.session.query(ModelClass).filter(ModelClass.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500