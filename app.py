from flask import Flask, render_template, flash, redirect, url_for, request
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm  # RegisterForm müssen wir in forms.py noch erstellen
from credentials import *

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY if SECRET_KEY else 'e79b9847144221ba4e85df9dd483a3e5'
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- DATENBANK MODEL ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    # Zusätzliche Felder, um dein Layout nicht kaputt zu machen
    cn = db.Column(db.String(150))  # Voller Name
    department = db.Column(db.String(150))
    is_admin = db.Column(db.Boolean, default=False)

    @property
    def groups(self):
        # Fake-Eigenschaft für Kompatibilität mit deinem Layout
        return ['Domänen-Admins'] if self.is_admin else []


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- ROUTES ---

@app.route('/', methods=["GET", "POST"])
def home():
    if current_user.is_authenticated:
        return render_template('main.html')
    else:
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)
            flash(f"Eingeloggt als {user.username}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Falsches Passwort oder Benutzername", "danger")

    return render_template("login.html", title="Login", form=form)


@app.route("/register", methods=["GET", "POST"])
def register():
    # Diese Route ist neu, damit du User anlegen kannst
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data,
                        password_hash=hashed_password,
                        cn=form.username.data,  # Vorläufig gleich wie Username
                        department="Standard")  # Default Wert
        db.session.add(new_user)
        db.session.commit()
        flash('Account erstellt! Du kannst dich nun einloggen.', 'success')
        return redirect(url_for('login'))

    return render_template("register.html", title="Registrieren", form=form)


@app.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


if __name__ == '__main__':
    # Datenbank erstellen, falls sie nicht existiert
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=3000, debug=True)