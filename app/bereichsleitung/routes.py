from flask import render_template
from flask_login import login_required
from app.decorators import permission_required
from app.bereichsleitung import bp

@bp.route('/', methods=['GET'])
@login_required
@permission_required('bl_user')
def index():
    """Übersicht der Bereichsleitung."""
    # Hier folgen später die Daten (Liste der BLs, Vereine etc.)
    return render_template('bereichsleitung/index.html')