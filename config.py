import os


class Config:
    # ... deine anderen Configs ...
    SECRET_KEY = os.environ.get('SECRET_KEY') or '7be05da9bd2c091116f985c7501452dd'

    # --- DATENBANK LOGIK ---
    # Prüfen, ob eine DB_PATH Variable existiert (wird nur von Docker gesetzt)
    docker_db_path = os.environ.get('DB_PATH')

    if docker_db_path:
        # FALL 1: DOCKER / SERVER
        # Nutzt den Pfad, den Docker vorgibt
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{docker_db_path}'
    else:
        # FALL 2: LOKAL / PYCHARM
        # Fallback auf die lokale Datei im Projektordner
        # Wir nutzen 'instance/site.db' oder einfach 'site.db', je nachdem wo du sie haben willst
        base_dir = os.path.abspath(os.path.dirname(__file__))
        # Tipp: Bei Flask ist es sauberer, die DB im 'instance' Ordner zu haben,
        # aber für den schnellen Test reicht auch Root.
        SQLALCHEMY_DATABASE_URI = 'sqlite:///site.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pfade für Uploads
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'app', 'static')

    # MAIL SETTINGS
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')