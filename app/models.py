from datetime import datetime, timedelta
import jwt
from time import time
from flask import current_app
from flask_login import UserMixin
from app.extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash

# --- KONSTANTEN ---

GERMAN_STATES = [
    ('BW', 'Baden-Württemberg'), ('BY', 'Bayern'), ('BE', 'Berlin'),
    ('BB', 'Brandenburg'), ('HB', 'Bremen'), ('HH', 'Hamburg'),
    ('HE', 'Hessen'), ('MV', 'Mecklenburg-Vorpommern'), ('NI', 'Niedersachsen'),
    ('NW', 'Nordrhein-Westfalen'), ('RP', 'Rheinland-Pfalz'), ('SL', 'Saarland'),
    ('SN', 'Sachsen'), ('ST', 'Sachsen-Anhalt'), ('SH', 'Schleswig-Holstein'),
    ('TH', 'Thüringen')
]

# --- ASSOCIATION TABLES ---

user_permissions = db.Table('user_permissions',
                            db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                            db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
                            )

# Kreuzverbindung: Welche User sind Bereichsleiter für welche Vereine?
verein_bereichsleitung = db.Table('verein_bereichsleitung',
                                  db.Column('verein_id', db.Integer, db.ForeignKey('verein.id'), primary_key=True),
                                  db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
                                  )


class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50), default="bi-box")
    url = db.Column(db.String(200), nullable=True)
    background_image = db.Column(db.String(100), nullable=True)


class StatusDefinition(db.Model):
    """
    Speichert dynamische Status-Workflows für verschiedene Bereiche.
    """
    __tablename__ = 'status_definition'

    CONTEXT_VEREIN = 'verein'
    CONTEXT_ANBAU = 'anbau'
    CONTEXT_AUSGABE = 'ausgabe'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    context = db.Column(db.String(20), nullable=False)  # z.B. 'verein', 'anbau'
    position = db.Column(db.Integer, default=0)  # Für die Sortierung

    def get_color_css(self, total_steps):
        """Berechnet dynamisch eine Farbe von Rot (0) bis Grün (100%)."""
        if total_steps <= 1:
            hue = 0
        else:
            # 0 = Rot, 120 = Grün.
            # Wir normalisieren die Position auf 0.0 bis 1.0
            percent = self.position / (total_steps - 1)
            hue = int(percent * 120)

        # HSL Rückgabe für CSS (Sättigung 70%, Helligkeit 45%)
        return f"background-color: hsl({hue}, 70%, 45%); color: white;"


class Anbaustelle(db.Model):
    __tablename__ = 'anbaustelle'

    TYPE_SINGLE = 'einzel'
    TYPE_CLUSTER = 'cluster'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255))
    state = db.Column(db.String(50))  # Bundesland Dropdown Value
    anbau_type = db.Column(db.String(20), default=TYPE_SINGLE)

    # Relation: Eine Anbaustelle kann mehrere Vereine beherbergen (Cluster)
    vereine = db.relationship('Verein', backref='anbaustelle', lazy=True)

    # NEU: Status Relation
    status_id = db.Column(db.Integer, db.ForeignKey('status_definition.id'), nullable=True)
    status_rel = db.relationship('StatusDefinition', foreign_keys=[status_id])

    @property
    def status_label(self):
        return self.status_rel.name if self.status_rel else "Kein Status"

    @property
    def status_color_css(self):
        if not self.status_rel:
            return "background-color: #6c757d; color: white;"

        # Wir müssen wissen, wie viele Schritte es insgesamt in diesem Kontext gibt
        # Das ist performancetechnisch nicht ideal direkt im Model, aber für kleine Mengen ok.
        total = db.session.query(StatusDefinition).filter_by(context='anbau').count()
        return self.status_rel.get_color_css(total)


class Verein(db.Model):
    __tablename__ = 'verein'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100))
    zip_code = db.Column(db.String(10))

    # Bundesländer
    state_seat = db.Column(db.String(50))  # Sitz des Vereins
    state_grow = db.Column(db.String(50))  # Anbaubundesland
    state_dist = db.Column(db.String(50))  # Default Abgabebundesland

    # Personen (Textfelder)
    board_member = db.Column(db.String(150))  # Vorstand
    prev_officer = db.Column(db.String(150))  # Präventionsbeauftragter

    is_ev = db.Column(db.Boolean, default=False)

    # NEU: Status Relation statt String
    status_id = db.Column(db.Integer, db.ForeignKey('status_definition.id'), nullable=True)
    status_rel = db.relationship('StatusDefinition', foreign_keys=[status_id])

    # Relationen
    anbaustelle_id = db.Column(db.Integer, db.ForeignKey('anbaustelle.id'), nullable=True)

    # Manager (Bereichsleitung) - Many-to-Many
    managers = db.relationship('User', secondary=verein_bereichsleitung,
                               backref=db.backref('managed_vereine', lazy=True))

    @property
    def status_label(self):
        return self.status_rel.name if self.status_rel else "Kein Status"

    @property
    def status_color_css(self):
        if not self.status_rel:
            return "background-color: #6c757d; color: white;"

        total = db.session.query(StatusDefinition).filter_by(context='verein').count()
        return self.status_rel.get_color_css(total)


class Ausgabestelle(db.Model):
    __tablename__ = 'ausgabestelle'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))  # Optionaler Name
    address = db.Column(db.String(255))
    state = db.Column(db.String(50))

    verein_id = db.Column(db.Integer, db.ForeignKey('verein.id'), nullable=False)
    verein = db.relationship('Verein', backref='ausgabestellen', lazy=True)

    # NEU: Status Relation
    status_id = db.Column(db.Integer, db.ForeignKey('status_definition.id'), nullable=True)
    status_rel = db.relationship('StatusDefinition', foreign_keys=[status_id])

    @property
    def status_label(self):
        return self.status_rel.name if self.status_rel else "Kein Status"

    @property
    def status_color_css(self):
        if not self.status_rel:
            return "background-color: #6c757d; color: white;"

        total = db.session.query(StatusDefinition).filter_by(context='ausgabe').count()
        return self.status_rel.get_color_css(total)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(64))
    last_name = db.Column(db.String(64))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_projects_visit = db.Column(db.DateTime)
    last_users_visit = db.Column(db.DateTime)
    last_roadmap_visit = db.Column(db.DateTime)
    onboarding_confirmed_at = db.Column(db.DateTime, nullable=True)

    # Permissions
    permissions = db.relationship('Permission', secondary=user_permissions, lazy='subquery',
                                  backref=db.backref('users', lazy=True))

    # NEU: Ein User kann Mitglied in EINEM Verein sein
    verein_id = db.Column(db.Integer, db.ForeignKey('verein.id'), nullable=True)
    verein = db.relationship('Verein', foreign_keys=[verein_id], backref='members')

    def has_permission(self, slug_name):
        if self.is_admin:
            return True
        return any(p.slug == slug_name for p in self.permissions)

    def get_reset_token(self, expires_sec=1800):
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

    @property
    def display_name(self):
        """
        Gibt Vorname zurück, wenn vorhanden.
        Sonst den Username.
        Gut für die Begrüßung im Dashboard ("Hallo Thomas").
        """
        if self.first_name:
            return self.first_name
        return self.username

    @property
    def full_name(self):
        """
        Gibt vollen Namen zurück, wenn vorhanden.
        Sonst den Username.
        Gut für PDFs und Listen ("Müller, Thomas").
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username


class ImmoSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)


class ImmoSection(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200))
    order = db.Column(db.Integer)
    is_expanded = db.Column(db.Boolean, default=True)
    category = db.Column(db.String(20), default='immo', nullable=False)
    questions = db.relationship('ImmoQuestion', backref='section', cascade="all, delete-orphan",
                                order_by='ImmoQuestion.order')


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
    id = db.Column(db.String(50), primary_key=True)
    content = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', backref='content_updates')


class DashboardTile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(255))
    icon = db.Column(db.String(64), default="bi-box")
    color_hex = db.Column(db.String(7), default="#19835A")
    route_name = db.Column(db.String(128), nullable=False)
    order = db.Column(db.Integer, default=0)
    required_permission_id = db.Column(db.Integer, db.ForeignKey('permission.id'), nullable=True)
    required_permission = db.relationship('Permission')


class Inspection(db.Model):
    __tablename__ = 'inspection'

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_REVIEW = 'review'
    STATUS_DONE = 'done'
    STATUS_REJECTED = 'rejected'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    csc_name = db.Column(db.String(100), nullable=False)
    inspection_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default=STATUS_DRAFT)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('inspections', lazy=True))

    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    pdf_path = db.Column(db.String(255))
    data_json = db.Column(db.Text, nullable=True)

    @property
    def status_color(self):
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
    action = db.Column(db.String(50))
    details = db.Column(db.Text)

    inspection = db.relationship('Inspection', backref=db.backref('logs', order_by=timestamp.desc(), lazy=True))
    user = db.relationship('User')


class MarketStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    state_name = db.Column(db.String(50), unique=True)

    applied = db.Column(db.Integer, default=0)
    approved = db.Column(db.Integer, default=0)
    rejected = db.Column(db.Integer, default=0)
    withdrawn = db.Column(db.Integer, default=0)

    mariana_applied = db.Column(db.Integer, default=0)
    mariana_approved = db.Column(db.Integer, default=0)
    mariana_rejected = db.Column(db.Integer, default=0)
    mariana_withdrawn = db.Column(db.Integer, default=0)

    data_date = db.Column(db.String(20))
    last_scraped = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def open_applications(self):
        app = self.applied or 0
        ok = self.approved or 0
        rej = self.rejected or 0
        wd = self.withdrawn or 0
        return app - (ok + rej + wd)

    @property
    def mariana_open(self):
        m_app = self.mariana_applied or 0
        m_ok = self.mariana_approved or 0
        m_rej = self.mariana_rejected or 0
        m_wd = self.mariana_withdrawn or 0
        return m_app - (m_ok + m_rej + m_wd)


class SystemSetting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
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