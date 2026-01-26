from datetime import datetime, timedelta
import jwt
from time import time
from flask import current_app
from flask_login import UserMixin
from app.extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash

# Many-to-Many Tabelle
user_permissions = db.Table('user_permissions',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)


class Permission(db.Model):
    # Tabellenname explizit setzen (optional, aber sauber)
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50), default="bi-box")
    url = db.Column(db.String(200), nullable=True)
    background_image = db.Column(db.String(100), nullable=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False) # <--- NEU
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_projects_visit = db.Column(db.DateTime)
    last_users_visit = db.Column(db.DateTime)
    last_roadmap_visit = db.Column(db.DateTime)
    permissions = db.relationship('Permission', secondary=user_permissions, lazy='subquery',
                                  backref=db.backref('users', lazy=True))

    def has_permission(self, slug_name):
        # Admin darf alles (Gott-Modus)
        if self.is_admin:
            return True
        # Sonst prüfen wir, ob der User den Service/Permission hat
        return any(p.slug == slug_name for p in self.permissions)

    def get_reset_token(self, expires_sec=1800):
        # Erstellt ein Token, das 30 Minuten gültig ist
        return jwt.encode(
            {'user_id': self.id, 'exp': time() + expires_sec},
            current_app.config['SECRET_KEY'], algorithm='HS256'
        )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def verify_reset_token(token):
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = data.get('user_id')
        except:
            return None
        return db.session.get(User, user_id)


class ImmoSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)


class ImmoSection(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200))
    order = db.Column(db.Integer)
    is_expanded = db.Column(db.Boolean, default=True)
    questions = db.relationship('ImmoQuestion', backref='section', cascade="all, delete-orphan", order_by='ImmoQuestion.order')


class ImmoQuestion(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    section_id = db.Column(db.String(50), db.ForeignKey('immo_section.id'))
    label = db.Column(db.Text)
    type = db.Column(db.String(50))
    width = db.Column(db.String(20))
    width_tablet = db.Column(db.String(20), default='default')
    width_mobile = db.Column(db.String(20), default='default')
    tooltip = db.Column(db.String(255))
    options_json = db.Column(db.Text)
    types_json = db.Column(db.Text)
    order = db.Column(db.Integer)
    is_required = db.Column(db.Boolean, default=False)
    is_metadata = db.Column(db.Boolean, default=False)
    is_print = db.Column(db.Boolean, default=True)


class ImmoBackup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(100))
    data_json = db.Column(db.Text)


class SiteContent(db.Model):
    id = db.Column(db.String(50), primary_key=True)  # z.B. 'roadmap'
    content = db.Column(db.Text, nullable=True)  # Markdown Text
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', backref='content_updates')


class DashboardTile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255))
    icon = db.Column(db.String(64), default="bi-box")  # z.B. "bi-house-check-fill"
    color_hex = db.Column(db.String(7), default="#19835A")  # z.B. "#19835A"
    route_name = db.Column(db.String(128), nullable=False)  # z.B. 'immo.immo_form'
    order = db.Column(db.Integer, default=0)  # Sortierung (1, 2, 3...)
    required_permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=True)
    required_permission = db.relationship('Permission')


class Inspection(db.Model):
    __tablename__ = 'inspection'

    # Status Konstanten (für sauberen Code)
    STATUS_DRAFT = 'draft'  # Entwurf (noch nicht abgesendet)
    STATUS_SUBMITTED = 'submitted'  # Abgeschickt (Grau/Blau)
    STATUS_REVIEW = 'review'  # In Prüfung (Gelb)
    STATUS_DONE = 'done'  # Erledigt / Genehmigt (Grün)
    STATUS_REJECTED = 'rejected'  # Abgelehnt / Nachbesserung (Rot)

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Metadaten zur Besichtigung
    csc_name = db.Column(db.String(100), nullable=False)  # Name des Anbauclubs/Projekts
    inspection_type = db.Column(db.String(50))  # einzel, cluster, ausgabe

    # Status (Ampel) - HIER GEÄNDERT: Default ist jetzt Draft
    status = db.Column(db.String(20), default=STATUS_DRAFT)

    # Verknüpfung zum Ersteller
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('inspections', lazy=True))

    is_archived = db.Column(db.Boolean, default=False, nullable=False)

    # Datei-Pfad (Relativ zu UPLOAD_FOLDER)
    pdf_path = db.Column(db.String(255))

    # JSON Daten (Wir speichern die kompletten Formulardaten,
    # damit man später Statistiken fahren oder editieren kann)
    data_json = db.Column(db.Text, nullable=True)

    @property
    def status_color(self):
        """Gibt die Bootstrap-Farbe für den Status zurück"""
        colors = {
            self.STATUS_DRAFT: 'secondary',
            self.STATUS_SUBMITTED: 'primary',
            self.STATUS_REVIEW: 'warning',
            self.STATUS_DONE: 'success',
            self.STATUS_REJECTED: 'danger'
        }
        return colors.get(self.status, 'light')

    @property
    def status_label(self):
        """Gibt ein schönes Label zurück"""
        labels = {
            self.STATUS_DRAFT: 'Entwurf',
            self.STATUS_SUBMITTED: 'Eingereicht',
            self.STATUS_REVIEW: 'In Prüfung',
            self.STATUS_DONE: 'Genehmigt',
            self.STATUS_REJECTED: 'Abgelehnt'
        }
        return labels.get(self.status, self.status)


class InspectionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey('inspection.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(50))  # z.B. 'status_change', 'data_update', 'file_upload'
    details = db.Column(db.Text)  # Beschreibung was geändert wurde

    inspection = db.relationship('Inspection', backref=db.backref('logs', order_by=timestamp.desc(), lazy=True))
    user = db.relationship('User')


class MarketStat(db.Model):
    """Speichert die Antragszahlen pro Bundesland."""
    id = db.Column(db.Integer, primary_key=True)
    state_name = db.Column(db.String(50), unique=True)

    # Gesamtmarkt (Scraper)
    applied = db.Column(db.Integer, default=0)
    approved = db.Column(db.Integer, default=0)
    rejected = db.Column(db.Integer, default=0)
    withdrawn = db.Column(db.Integer, default=0)

    # NEU: Mariana Interne Zahlen (Manuell oder später autom. gepflegt)
    mariana_applied = db.Column(db.Integer, default=0)
    mariana_approved = db.Column(db.Integer, default=0)
    mariana_rejected = db.Column(db.Integer, default=0)
    mariana_withdrawn = db.Column(db.Integer, default=0)

    data_date = db.Column(db.String(20))
    last_scraped = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def open_applications(self):
        """Berechnet: Gestellt - (Genehmigt + Abgelehnt + Zurückgezogen)"""
        # (x or 0) wandelt None sicher in 0 um
        app = self.applied or 0
        ok = self.approved or 0
        rej = self.rejected or 0
        wd = self.withdrawn or 0
        return app - (ok + rej + wd)

    @property
    def mariana_open(self):
        """Berechnet offene Mariana Anträge."""
        # Auch hier: None sicher in 0 umwandeln
        m_app = self.mariana_applied or 0
        m_ok = self.mariana_approved or 0
        m_rej = self.mariana_rejected or 0
        m_wd = self.mariana_withdrawn or 0
        return m_app - (m_ok + m_rej + m_wd)


class SystemSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)  # z.B. 'app_version', 'changelog_text'
    value = db.Column(db.Text)

    @staticmethod
    def get_value(key, default=None):
        setting = db.session.get(SystemSetting, key)
        return setting.value if setting else default

    @staticmethod
    def set_value(key, value):
        setting = db.session.get(SystemSetting, key)
        if not setting:
            setting = SystemSetting(key=key)
            db.session.add(setting)
        setting.value = value
        db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))