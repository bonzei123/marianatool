import os
from flask import render_template, send_from_directory, current_app, Blueprint
from flask_login import login_required, current_user
from app.models import DashboardTile
from app.main import bp

@bp.route('/home')
@bp.route('/')
@login_required
def home():
    """Dashboard / Startseite."""
    all_tiles = DashboardTile.query.order_by(DashboardTile.order).all()

    visible_tiles = []
    for tile in all_tiles:
        # Berechtigung prüfen:
        # 1. Kachel ist öffentlich (permission is None) ODER
        # 2. User ist Admin ODER
        # 3. User hat die spezifische Permission
        if tile.required_permission is None or \
           current_user.is_admin or \
           current_user.has_permission(tile.required_permission.slug):
            visible_tiles.append(tile)

    return render_template('main/main.html', tiles=visible_tiles)


@bp.route('/favicon.ico')
def favicon():
    """Favicon ausliefern."""
    return send_from_directory(
        os.path.join(current_app.root_path, 'static', 'img'),
        'logo_small.jpg',
        mimetype='image/jpeg'
    )