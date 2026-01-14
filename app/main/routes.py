from flask import render_template
from flask_login import login_required, current_user
from app.main import bp
from app.models import SiteContent

@bp.route('/', methods=["GET", "POST"])
@login_required
def home():
    return render_template('main/main.html', services=current_user.services, is_admin=current_user.is_admin)
