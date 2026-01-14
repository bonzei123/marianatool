from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm, UpdateAccountForm, RequestResetForm, ResetPasswordForm
from app.models import User, Service
from app.extensions import db
from app.utils import send_reset_email

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("main.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)
            if not user.services and not user.is_admin:
                user.services = Service.query.all()
                db.session.commit()
            return redirect(url_for('main.home'))
        else:
            flash("Login fehlgeschlagen.", "danger")
    return render_template("auth/login.html", form=form)

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Ausgeloggt.', 'info')
    return redirect(url_for('auth.login'))

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('main.home'))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        # Email mit speichern!
        new_user = User(username=form.username.data, email=form.email.data, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Account erstellt! Du kannst dich nun einloggen.', 'success')
        return redirect(url_for('auth.login'))
    return render_template("auth/register.html", form=form)

@bp.route("/profile", methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Dein Profil wurde aktualisiert!', 'success')
        return redirect(url_for('auth.profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    return render_template('auth/profile.html', form=form)

# --- PASSWORT VERGESSEN LOGIK ---

@bp.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('Eine E-Mail mit Anweisungen wurde gesendet (siehe Server-Konsole).', 'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_request.html', form=form)

@bp.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    user = User.verify_reset_token(token)
    if not user:
        flash('Das Token ist ungültig oder abgelaufen.', 'warning')
        return redirect(url_for('auth.reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        user.password_hash = hashed_pw
        db.session.commit()
        flash('Dein Passwort wurde geändert! Du kannst dich nun einloggen.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_token.html', form=form)