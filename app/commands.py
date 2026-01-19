import click
import json
import os
from flask import Blueprint
from app.extensions import db
from app.models import Permission, DashboardTile, User
from werkzeug.security import generate_password_hash

# 1. Blueprint erstellen
cmd_bp = Blueprint('commands', __name__)


def load_json_data():
    """Lädt die JSON Datei aus dem data Ordner."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'data', 'initial_data.json')

    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# 2. Command am Blueprint registrieren (.cli.command statt click.command)
@cmd_bp.cli.command('seed-db')
def seed_db_command():
    """Befüllt die Datenbank mit Daten aus initial_data.json."""
    data = load_json_data()

    click.echo("🌱 Starte Database Seeding...")
    db.create_all()

    # --- 1. Permissions ---
    click.echo(f"   Prüfe {len(data['permissions'])} Berechtigungen...")
    for p in data['permissions']:
        existing = db.session.get(Permission, p['id'])
        if not existing:
            perm = Permission(
                id=p['id'],
                slug=p['slug'],
                name=p['name'],
                description=p.get('description', ''),
                icon=p.get('icon', '')
            )
            db.session.add(perm)
            click.echo(f"   [+] Permission erstellt: {p['name']}")
        else:
            existing.slug = p['slug']
            existing.icon = p.get('icon', '')

    db.session.commit()

    # --- 2. Tiles ---
    click.echo(f"   Prüfe {len(data['tiles'])} Dashboard Kacheln...")
    for t in data['tiles']:
        existing = DashboardTile.query.filter_by(route_name=t['route']).first()
        perm_obj = Permission.query.filter_by(slug=t['permission_slug']).first()

        if not perm_obj and t['permission_slug']:
            click.echo(f"   [!] WARNUNG: Permission '{t['permission_slug']}' fehlt!")
            continue

        if not existing:
            tile = DashboardTile(
                title=t['title'],
                route_name=t['route'],
                icon=t['icon'],
                color_hex=t['color'],
                order=t['order'],
                required_permission=perm_obj
            )
            db.session.add(tile)
            click.echo(f"   [+] Kachel erstellt: {t['title']}")
        else:
            existing.title = t['title']
            existing.icon = t['icon']
            existing.color_hex = t['color']
            existing.order = t['order']
            existing.required_permission = perm_obj

    db.session.commit()

    # --- 3. Default Admin ---
    if not User.query.filter_by(username='admin').first():
        click.echo("   [+] Erstelle Default Admin User (admin / passwort)")
        admin = User(
            username='admin',
            email='admin@local.test',
            password_hash=generate_password_hash('passwort'),
            is_admin=True
        )
        for p in Permission.query.all():
            admin.permissions.append(p)
        db.session.add(admin)
        db.session.commit()

    click.echo("✅ Seeding abgeschlossen.")