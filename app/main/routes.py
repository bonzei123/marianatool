import os
from flask import render_template, send_from_directory, current_app
from flask_login import login_required, current_user
from app.main import bp
from app.models import SiteContent


@bp.route('/', methods=["GET", "POST"])
@login_required
def home():
    return render_template('main/main.html', services=current_user.services, is_admin=current_user.is_admin)


@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo_small.jpg',
        mimetype='image/jpeg'
    )
