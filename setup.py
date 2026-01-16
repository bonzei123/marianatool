import os
import json
from datetime import datetime
from app import create_app
from app.extensions import db
from app.models import User, Permission, DashboardTile, SiteContent
from app.utils import import_json_data
from werkzeug.security import generate_password_hash

app = create_app()


def run_setup():
    """
    Führt das komplette Seed-Setup durch.
    Kann sicher mehrfach ausgeführt werden (prüft auf Existenz).
    """
    with app.app_context():
        print("🚀 Starte System-Initialisierung...")

        # ==========================================
        # 1. PERMISSIONS (Ehemals Services)
        # ==========================================
        print("🔐 [1/5] Prüfe Berechtigungen...")
        permissions_data = [
            # Name, Slug, Icon, Beschreibung
            ("Immo Tool Zugriff", "immo_user", "bi-house-check", "Darf Besichtigungen durchführen"),
            ("Roadmap Ansehen", "roadmap_access", "bi-map", "Darf die Roadmap sehen"),
            ("Roadmap Bearbeiten", "roadmap_edit", "bi-pencil-square", "Darf die Roadmap bearbeiten"),
            ("Formular Builder", "immo_admin", "bi-tools", "Darf Fragen & Layout bearbeiten"),
            ("Datei Manager", "immo_files_access", "bi-folder2-open", "Zugriff auf Uploads & Dateien"),
            ("User Verwaltung", "view_users", "bi-people", "Darf Nutzer verwalten & Rechte vergeben"),
            ("Einstellungen", "view_settings", "bi-gear", "Zugriff auf globale Konfiguration"),
        ]

        for name, slug, icon, desc in permissions_data:
            perm = Permission.query.filter_by(slug=slug).first()
            if not perm:
                perm = Permission(name=name, slug=slug, icon=icon, description=desc)
                db.session.add(perm)
                print(f"   ➕ Berechtigung erstellt: {slug}")
            else:
                # Update (falls Icon/Text geändert wurde)
                perm.name = name
                perm.icon = icon
                perm.description = desc

        db.session.commit()

        # ==========================================
        # 2. ADMIN USER
        # ==========================================
        print("👤 [2/5] Prüfe Admin User...")
        if User.query.filter_by(username='admin').first() is None:
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('admin')  # Setzt Hash via Model-Methode

            # Admin bekommt ALLE Rechte
            all_perms = Permission.query.all()
            admin.permissions = all_perms

            db.session.add(admin)
            db.session.commit()
            print("   ➕ Admin User erstellt (User: admin / Pass: admin)")
        else:
            print("   ✅ Admin User existiert bereits.")

        # ==========================================
        # 3. DASHBOARD KACHELN
        # ==========================================
        print("puzzle_piece [3/5] Konfiguriere Dashboard Kacheln...")
        # Alte Kacheln löschen für saubere Sortierung/Neuanlage
        db.session.query(DashboardTile).delete()

        # Titel, Desc, Icon, Farbe, Route, RequiredPermissionSlug, Order
        tiles_data = [
            ("Immobilien Check", "Besichtigungen durchführen.", "bi-house-check-fill", "#19835A", "immo.immo_form",
             "immo_user", 10),
            ("Roadmap", "Projektstatus & Updates.", "bi-map-fill", "#8e44ad", "roadmap.index", "roadmap_access", 20),
            ("Formular Builder", "Fragen & Layout anpassen.", "bi-tools", "#e74c3c", "admin.immo_admin_dashboard",
             "immo_admin", 80),
            ("Datei Manager", "Uploads verwalten.", "bi-folder2-open", "#f1c40f", "admin.immo_admin_files",
             "immo_files_access", 85),
            (
            "User Verwaltung", "Benutzer & Rechte.", "bi-people-fill", "#3498db", "admin.user_management", "view_users",
            90),
            ("Einstellungen", "Konfiguration & Design.", "bi-gear-fill", "#34495e", "admin.settings_page",
             "view_settings", 100),
        ]

        for t in tiles_data:
            # Permission ID suchen
            perm = Permission.query.filter_by(slug=t[5]).first()

            tile = DashboardTile(
                title=t[0],
                description=t[1],
                icon=t[2],
                color_hex=t[3],
                route_name=t[4],
                order=t[6],
                required_permission_id=perm.id if perm else None
            )
            db.session.add(tile)

        db.session.commit()
        print("   ✅ Kacheln aktualisiert.")

        # ==========================================
        # 4. ROADMAP CONTENT
        # ==========================================
        print("🗺️ [4/5] Prüfe Roadmap Content...")
        if not db.session.get(SiteContent, 'roadmap'):
            initial_roadmap = SiteContent(
                id='roadmap',
                content="# Willkommen zur Roadmap\n\nHier stehen aktuelle Updates.",
                updated_at=datetime.utcnow()
            )
            db.session.add(initial_roadmap)
            db.session.commit()
            print("   ➕ Leere Roadmap angelegt.")

        # ==========================================
        # 5. FRAGEN IMPORT (questions.json)
        # ==========================================
        print("📝 [5/5] Importiere Fragenkatalog...")
        json_path = os.path.join(app.root_path, 'static', 'questions.json')

        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Nutzt die Import-Funktion aus app/utils.py
                    import_json_data(data)
                    print(f"   ✅ Fragen aus '{json_path}' importiert.")
            except Exception as e:
                print(f"   ❌ Fehler beim Import: {e}")
        else:
            print(f"   ⚠️ Datei nicht gefunden: {json_path} (Überspringe Import)")

        print("\n🎉 SETUP ERFOLGREICH ABGESCHLOSSEN!")


if __name__ == "__main__":
    run_setup()