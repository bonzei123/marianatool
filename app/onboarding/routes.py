from datetime import datetime
from flask import render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models import ImmoSection
from app.onboarding import bp


@bp.route('/', methods=['GET'])
@login_required
def start():
    """Zeigt das Onboarding-Formular."""
    if current_user.onboarding_confirmed_at:
        return redirect(url_for('projects.overview'))

    # Wir laden nur Sektionen mit category='onboarding'
    # Falls keine existieren, erstellen wir Dummy-Daten im Template oder Seed
    sections = ImmoSection.query.filter_by(category='onboarding').order_by(ImmoSection.order).all()

    return render_template('onboarding/start.html', sections=sections)


@bp.route('/confirm', methods=['POST'])
@login_required
def confirm():
    """Bestätigt das Onboarding."""
    current_user.onboarding_confirmed_at = datetime.utcnow()
    db.session.commit()

    flash("Onboarding erfolgreich abgeschlossen! Du kannst nun Projekte anlegen.", "success")
    return jsonify({'success': True})