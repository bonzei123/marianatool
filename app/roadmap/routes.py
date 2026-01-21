from flask import render_template, redirect, url_for, flash, request, Blueprint
from flask_login import login_required, current_user
from datetime import datetime
from app.models import SiteContent
from app.extensions import db
from app.decorators import permission_required
from app.roadmap import bp


@bp.route("/", methods=['GET'])
@login_required
@permission_required('roadmap_access')
def view_roadmap():
    """Zeigt die Roadmap an (Read-Only)."""

    # NEU: Gelesen-Status setzen
    current_user.last_roadmap_visit = datetime.utcnow()
    db.session.commit()

    # Content laden (Schlüssel ist 'roadmap')
    page_content = db.session.get(SiteContent, 'roadmap')

    # Fallback Text, falls DB leer
    markdown_text = page_content.content if page_content else "Noch keine Roadmap definiert."

    return render_template('roadmap/index.html', content=markdown_text, meta=page_content)


@bp.route("/", methods=['POST'])
@login_required
@permission_required('roadmap_edit')
def update_roadmap():
    """Speichert Änderungen an der Roadmap."""
    new_text = request.form.get('content')
    page_content = db.session.get(SiteContent, 'roadmap')

    if not page_content:
        # Neu anlegen, falls noch nicht existiert
        page_content = SiteContent(id='roadmap', content=new_text, author=current_user)
        db.session.add(page_content)
    else:
        # Update bestehenden Eintrag
        page_content.content = new_text
        page_content.author = current_user
        page_content.updated_at = datetime.utcnow()

    db.session.commit()
    flash('Roadmap erfolgreich gespeichert.', 'success')

    # Redirect zur GET-Ansicht
    return redirect(url_for('roadmap.view_roadmap'))