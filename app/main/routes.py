import os
import markdown
from app.main import bp
from datetime import datetime
from flask import request, flash, redirect, url_for, current_app, render_template, send_from_directory, jsonify
from flask_login import login_required, current_user
from flask_mail import Message
from app.extensions import db, mail
from app.models import DashboardTile, Inspection, User, SiteContent, ImmoSetting, SystemSetting


@bp.route('/home')
@bp.route('/')
@login_required
def home():
    """Dashboard / Startseite mit INTELLIGENTEN Badges."""
    from app.models import DashboardTile, Inspection, User  # Import hier

    all_tiles = DashboardTile.query.order_by(DashboardTile.order).all()

    badges = {}

    # --- 1. BADGE: Neue/Geänderte Projekte ---
    # Logik: Zähle alle Inspections, deren update-Datum NEUER ist als mein letzter Besuch
    # Wenn ich noch nie da war (last_projects_visit is None), ist ALLES neu.

    proj_query = Inspection.query
    # Optional: Nur eigene filtern?
    # proj_query = proj_query.filter_by(user_id=current_user.id)
    # Aber meist will man wissen "Gibt es generell was neues?", also lassen wir den Filter weg oder passen ihn an.
    # Wenn du nur DEINE Änderungen sehen willst:
    proj_query = proj_query.filter_by(user_id=current_user.id)

    if current_user.last_projects_visit:
        new_projects = proj_query.filter(Inspection.updated_at > current_user.last_projects_visit).count()
    else:
        new_projects = proj_query.count()  # Alles ist neu beim ersten Mal

    badges['projects.overview'] = new_projects

    # --- 2. BADGE: Neue User (Nur für Admins) ---
    if current_user.has_permission('view_users'):
        user_query = User.query
        if current_user.last_users_visit:
            new_users = user_query.filter(User.created_at > current_user.last_users_visit).count()
        else:
            new_users = user_query.count()

        badges['user.list_users'] = new_users

    # --- 3. BADGE: Roadmap Updates ---
    # Wir holen den Inhalt der Roadmap
    roadmap_content = db.session.get(SiteContent, 'roadmap')

    if roadmap_content and roadmap_content.updated_at:
        # Check: Habe ich sie noch nie gesehen? ODER ist das Update neuer als mein Besuch?
        if not current_user.last_roadmap_visit or roadmap_content.updated_at > current_user.last_roadmap_visit:
            # Wir zeigen eine "1" an, um zu signalisieren: Hier gibt es was Neues
            badges['roadmap.view_roadmap'] = 1


    # --- Kacheln bauen ---
    visible_tiles = []
    for tile in all_tiles:
        if tile.required_permission is None or \
                current_user.is_admin or \
                current_user.has_permission(tile.required_permission.slug):
            tile.badge_count = badges.get(tile.route_name, 0)
            visible_tiles.append(tile)

    return render_template('main/main.html', tiles=visible_tiles)


@bp.route('/report_issue', methods=['POST'])
@login_required
def report_issue():
    """Sendet Feedback per E-Mail an den Admin."""
    category = request.form.get('category')
    message_text = request.form.get('message')
    source_url = request.form.get('current_url', 'Unbekannt')  # <--- NEU

    if not message_text:
        flash("Bitte eine Nachricht eingeben.", "warning")
        return redirect(request.referrer or url_for('main.home'))

    # 1. Empfänger laden
    setting = db.session.get(ImmoSetting, 'email_receiver')
    receiver = setting.value if (setting and setting.value) else current_app.config.get('MAIL_DEFAULT_SENDER')

    if not receiver:
        flash("Keine Empfänger-E-Mail konfiguriert!", "danger")
        return redirect(request.referrer)

    try:
        # 2. E-Mail mit User-Infos bauen
        subject = f"[Support] {category.upper()}: {current_user.username}"

        body = f"""
Ein Nutzer hat Feedback gesendet:

------------------------------------------------
BENUTZER:  {current_user.username} (ID: {current_user.id})
E-MAIL:    {current_user.email}
ROLLE:     {'Admin' if current_user.is_admin else 'User'}
ZEIT:      {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC
URL:       {source_url}
------------------------------------------------

KATEGORIE: {category}

NACHRICHT:
{message_text}
"""
        msg = Message(subject, recipients=[receiver])
        msg.body = body

        # 3. Senden
        mail.send(msg)
        flash("Feedback wurde gesendet! Wir kümmern uns darum.", "success")

    except Exception as e:
        current_app.logger.error(f"Mail Error: {e}")
        flash(f"Fehler beim Senden: {e}", "danger")

    return redirect(request.referrer or url_for('main.home'))


@bp.route('/impressum')
def impressum():
    return render_template('main/legal.html', title="Impressum", content="")


@bp.route('/datenschutz')
def datenschutz():
    return render_template('main/legal.html', title="Datenschutz", content="")


@bp.app_context_processor
def inject_version():
    """Macht die Variable 'app_version' in allen Templates verfügbar."""
    version = SystemSetting.get_value('app_version', '1.0.0')
    return dict(app_version=version)


# --- PUBLIC ROUTE ---
@bp.route('/versionshinweise', methods=['GET'])
def changelog_view():
    """Zeigt die Patchnotes an."""
    version = SystemSetting.get_value('app_version', '1.0.0')
    raw_text = SystemSetting.get_value('changelog_text', '# Keine Patchnotes verfügbar.')

    # Markdown in HTML wandeln
    content_html = markdown.markdown(raw_text)

    return render_template('changelog.html', version=version, content_html=content_html)


# --- ADMIN API (Speichern) ---
@bp.route('/settings/changelog', methods=['POST'])
@login_required
# @permission_required('admin')  <-- Falls du Admin-Check hast
def update_changelog():
    data = request.json
    try:
        SystemSetting.set_value('app_version', data.get('version'))
        SystemSetting.set_value('changelog_text', data.get('text'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/settings/changelog', methods=['GET'])
@login_required
def get_changelog_settings():
    return jsonify({
        'version': SystemSetting.get_value('app_version', '1.0.0'),
        'text': SystemSetting.get_value('changelog_text', '')
    })


@bp.route('/favicon.ico')
def favicon():
    """Favicon ausliefern."""
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo_small.png',
        mimetype='image/png'
    )