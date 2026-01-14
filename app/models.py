from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, login_manager

# Many-to-Many Tabelle
user_services = db.Table('user_services',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True)
)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    url = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), default="bi-box")
    color_class = db.Column(db.String(50), default="border-primary")
    slug = db.Column(db.String(50), unique=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    services = db.relationship('Service', secondary=user_services, lazy='subquery', backref=db.backref('users', lazy=True))

    def has_service(self, slug_name):
        return any(s.slug == slug_name for s in self.services) or self.is_admin

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
    tooltip = db.Column(db.String(255))
    options_json = db.Column(db.Text)
    types_json = db.Column(db.Text)
    order = db.Column(db.Integer)

class ImmoBackup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(100))
    data_json = db.Column(db.Text)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))