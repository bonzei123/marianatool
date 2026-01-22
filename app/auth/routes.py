from flask import render_template, redirect, url_for, flash, request, Blueprint
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from app.auth.forms import LoginForm, RegisterForm, RequestResetForm, ResetPasswordForm
from app.models import User, Permission
from app.extensions import db
from app.utils import send_reset_email
from app.auth import bp


# --- LOGIN ---

@bp.route("/login", methods=["GET"])
def login_view():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = LoginForm()
    return render_template("auth/login.html", form=form)


@bp.route("/login", methods=["POST"])
def login_action():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=True)
            return redirect(url_for('main.home'))
        else:
            flash("Login fehlgeschlagen. Bitte prüfen.", "danger")

    # Bei Fehler: Template neu laden (mit Fehlermeldungen)
    return render_template("auth/login.html", form=form)


# --- LOGOUT ---

@bp.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    flash('Ausgeloggt.', 'info')
    return redirect(url_for('auth.login_view'))  # Verweist auf die GET Methode


# --- REGISTER ---

@bp.route("/register", methods=["GET"])
def register_view():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('main.home'))
    form = RegisterForm()
    return render_template("auth/register.html", form=form)


@bp.route("/register", methods=["POST"])
def register_action():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('main.home'))

    form = RegisterForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, email=form.email.data, password_hash=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash('Account erstellt! Du kannst dich nun einloggen.', 'success')
        return redirect(url_for('auth.login_view'))

    return render_template("auth/register.html", form=form)


# --- PASSWORD RESET ---

@bp.route("/reset_password", methods=['GET'])
def reset_request_view():
    # Kein login_required, sonst kann man Pwd nicht resetten wenn ausgeloggt
    form = RequestResetForm()
    return render_template('auth/reset_request.html', form=form)


@bp.route("/reset_password", methods=['POST'])
def reset_request_action():
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_reset_email(user)
        # Wir flashen immer success, um E-Mail Enumeration zu erschweren (Security Best Practice)
        flash('Falls diese E-Mail existiert, wurde ein Reset-Link versendet.', 'info')
        return redirect(url_for('auth.login_view'))
    return render_template('auth/reset_request.html', form=form)


@bp.route("/reset_password/<token>", methods=['GET'])
def reset_token_view(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    user = User.verify_reset_token(token)
    if not user:
        flash('Das Token ist ungültig oder abgelaufen.', 'warning')
        return redirect(url_for('auth.reset_request_view'))

    form = ResetPasswordForm()
    return render_template('auth/reset_token.html', form=form)


@bp.route("/reset_password/<token>", methods=['POST'])
def reset_token_action(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    user = User.verify_reset_token(token)
    if not user:
        flash('Das Token ist ungültig oder abgelaufen.', 'warning')
        return redirect(url_for('auth.reset_request_view'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_pw = generate_password_hash(form.password.data)
        user.password_hash = hashed_pw
        db.session.commit()
        flash('Dein Passwort wurde geändert! Du kannst dich nun einloggen.', 'success')
        return redirect(url_for('auth.login_view'))

    return render_template('auth/reset_token.html', form=form)