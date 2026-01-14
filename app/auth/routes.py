from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm
from app.models import User, Service
from app.extensions import db

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
    # Nur noch Notfall-Route
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('main.home'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Benutzername vergeben.', 'danger')
            return render_template("auth/register.html", form=form)
        new_user = User(username=form.username.data, password_hash=generate_password_hash(form.password.data))
        db.session.add(new_user)
        db.session.commit()
        flash('Account erstellt!', 'success')
        return redirect(url_for('auth.login'))
    return render_template("auth/register.html", form=form)