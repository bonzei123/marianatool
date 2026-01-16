import os
from flask import render_template, send_from_directory, current_app
from flask_login import login_required, current_user
from app.main import bp
from app.models import SiteContent

from app.models import DashboardTile  # <--- WICHTIG: Import


@bp.route('/home')
@bp.route('/')
@login_required
def home():
    # 1. Alle Kacheln laden, sortiert nach 'order'
    all_tiles = DashboardTile.query.order_by(DashboardTile.order).all()

    # 2. Filtern: Was darf dieser User sehen?
    visible_tiles = []
    for tile in all_tiles:
        # Bedingung: Kachel braucht keine Permission ODER User hat sie ODER User ist Admin
        if tile.required_service is None or \
                current_user.is_admin or \
                current_user.has_permission(tile.required_service.slug):
            visible_tiles.append(tile)

    # Wir geben 'tiles' an das Template weiter
    return render_template('main/main.html', tiles=visible_tiles)


@bp.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo_small.jpg',
        mimetype='image/jpeg'
    )
