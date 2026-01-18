from app import create_app
from app.extensions import db
from app.models import DashboardTile

app = create_app()

# Mapping: Alte Route -> Neue Route
ROUTE_MAPPING = {
    "immo.immo_form": "projects.create_view",
    "roadmap.index": "roadmap.view_roadmap",
    "admin.immo_admin_dashboard": "formbuilder.builder_view",
    "admin.immo_admin_files": "projects.files_overview",
    "admin.user_management": "user.list_users",
    "admin.settings_page": "admin.global_settings_view",
    "immo.overview": "projects.overview"
}


def fix_routes():
    with app.app_context():
        print("🔧 Starte Reparatur der Dashboard-Kacheln...")
        tiles = DashboardTile.query.all()
        count = 0
        for tile in tiles:
            if tile.route_name in ROUTE_MAPPING:
                print(f"   Update: {tile.title}: {tile.route_name} -> {ROUTE_MAPPING[tile.route_name]}")
                tile.route_name = ROUTE_MAPPING[tile.route_name]
                count += 1

        db.session.commit()
        print(f"✅ {count} Kacheln aktualisiert.")


if __name__ == "__main__":
    fix_routes()