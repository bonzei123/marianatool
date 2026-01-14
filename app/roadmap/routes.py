# app/roadmap/routes.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.roadmap import bp
from app.models import SiteContent
from app.extensions import db
from datetime import datetime


@bp.route("/", methods=['GET', 'POST'])
@login_required
def index():
    # Content laden (Schlüssel ist 'roadmap')
    page_content = db.session.get(SiteContent, 'roadmap')

    # SPEICHERN (Nur Admins)
    if request.method == 'POST':
        if not current_user.is_admin:
            flash('Nur Admins dürfen speichern!', 'danger')
            return redirect(url_for('roadmap.index'))

        new_text = request.form.get('content')

        if not page_content:
            page_content = SiteContent(id='roadmap', content=new_text, author=current_user)
            db.session.add(page_content)
        else:
            page_content.content = new_text
            page_content.author = current_user
            page_content.updated_at = datetime.utcnow()

        db.session.commit()
        flash('Roadmap erfolgreich gespeichert.', 'success')
        return redirect(url_for('roadmap.index'))

    # ANZEIGEN (Für alle eingeloggten)
    markdown_text = page_content.content if page_content else "Noch keine Roadmap definiert."

    return render_template('roadmap/index.html', content=markdown_text, meta=page_content)