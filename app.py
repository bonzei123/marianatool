from flask import Flask, render_template, flash, redirect, url_for, request
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm
from credentials import SECRET_KEY, SQLALCHEMY_DATABASE_URI

app = Flask(__name__)

# --- KONFIGURATION ---
app.config["SECRET_KEY"] = SECRET_KEY if SECRET_KEY else 'dein_geheimer_key_fallback'
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI if SQLALCHEMY_DATABASE_URI else 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bitte einloggen, um auf das Dashboard zuzugreifen."
login_manager.login_message_category = "info"

# --- DATENBANK MODELLE ---

# 1. Verknüpfungstabelle (Many-to-Many: User <-> Service)
user_services = db.Table('user_services',
                         db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                         db.Column('service_id', db.Integer, db.ForeignKey('service.id'), primary_key=True)
                         )


# 2. Das Service Model (Deine Microservices)
class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    url = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), default="bi-box")  # Bootstrap Icon Klasse
    color_class = db.Column(db.String(50), default="border-primary")  # Rahmenfarbe


# 3. Das User Model (Bereinigt: kein CN mehr)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    # Beziehung zu den Services
    services = db.relationship('Service', secondary=user_services, lazy='subquery',
                               backref=db.backref('users', lazy=True))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- HILFSFUNKTIONEN ---

def create_dummy_data():
    """Erstellt Beispiel-Services, falls die DB leer ist."""
    if Service.query.count() == 0:
        s1 = Service(name="Mitglieder DB", description="Verwaltung", url="/members", icon="bi-person-rolodex",
                     color_class="border-success")
        s2 = Service(name="Grow-Room", description="Sensoren Live", url="http://localhost:5000", icon="bi-moisture",
                     color_class="border-info")
        s3 = Service(name="Lager", description="Inventar & Dünger", url="/inventory", icon="bi-box-seam",
                     color_class="border-warning")
        s4 = Service(name="Chat", description="Team Kommunikation", url="https://chat.google.com", icon="bi-chat-dots",
                     color_class="border-secondary")

        db.session.add_all([s1, s2, s3, s4])
        db.session.commit()
        print("Initial Services wurden angelegt.")


# --- ROUTES ---

@app.route('/', methods=["GET", "POST"])
@login_required
def home():
    # Zeige nur die Services an, die dem User zugeordnet sind
    my_services = current_user.services
    return render_template('main.html', services=my_services)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)

            # OPTIONAL: Falls User noch keine Services hat, gib ihm zum Testen alle (kann später raus)
            if not user.services:
                user.services = Service.query.all()
                db.session.commit()

            flash(f"Willkommen zurück, {user.username}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Falsches Passwort oder Benutzername", "danger")

    return render_template("login.html", title="Login", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegisterForm()
    if form.validate_on_submit():
        # User prüfen
        if User.query.filter_by(username=form.username.data).first():
            flash('Benutzername bereits vergeben.', 'danger')
            return render_template("register.html", title="Registrieren", form=form)

        # Passwort hashen (ohne method='sha256' -> nutzt sichereres Default)
        hashed_password = generate_password_hash(form.password.data)

        # User erstellen (ohne CN)
        new_user = User(username=form.username.data, password_hash=hashed_password)

        db.session.add(new_user)
        db.session.commit()
        flash('Account erstellt! Bitte einloggen.', 'success')
        return redirect(url_for('login'))

    return render_template("register.html", title="Registrieren", form=form)


@app.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    flash("Du wurdest ausgeloggt.", "info")
    return redirect(url_for("login"))


# --- START ---

if __name__ == '__main__':
    with app.app_context():
        # Erstellt Tabellen basierend auf den Models oben
        db.create_all()
        # Füllt DB mit Test-Services
        create_dummy_data()

    app.run(host='0.0.0.0', port=3000, debug=True)