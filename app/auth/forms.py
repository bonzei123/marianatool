from flask_wtf import FlaskForm
from flask_login import current_user
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo, Email, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    username = StringField("Benutzer", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Einloggen")


class RegisterForm(FlaskForm):
    username = StringField("Benutzer", validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField("E-Mail", validators=[DataRequired(), Email()]) # <--- NEU
    password = PasswordField("Passwort", validators=[DataRequired()])
    confirm_password = PasswordField("Passwort bestätigen", validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField("Registrieren")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user: raise ValidationError('Benutzername vergeben.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user: raise ValidationError('E-Mail wird bereits verwendet.')


class UpdateAccountForm(FlaskForm):
    username = StringField("Benutzer", validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField("E-Mail", validators=[DataRequired(), Email()])
    submit = SubmitField("Aktualisieren")


    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user: raise ValidationError('Benutzername vergeben.')


    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user: raise ValidationError('E-Mail wird bereits verwendet.')


class RequestResetForm(FlaskForm):
    email = StringField('E-Mail', validators=[DataRequired(), Email()])
    submit = SubmitField('Passwort zurücksetzen anfordern')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('Es gibt keinen Account mit dieser E-Mail.')


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Neues Passwort", validators=[DataRequired()])
    confirm_password = PasswordField("Bestätigen", validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField("Passwort speichern")