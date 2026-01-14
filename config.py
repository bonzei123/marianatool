import os


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dein_geheimer_key_123'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pfade
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'app', 'static')

    # Datenbank Logik (Docker vs Lokal)
    custom_db_path = os.environ.get('DB_PATH')
    if custom_db_path:
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{custom_db_path}'
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'