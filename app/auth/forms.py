from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo

class LoginForm(FlaskForm):
    username = StringField("Benutzer", validators=[DataRequired()])
    password = PasswordField("Passwort", validators=[DataRequired()])
    submit = SubmitField("Einloggen")

class RegisterForm(FlaskForm):
    username = StringField("Benutzer", validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField("Passwort", validators=[DataRequired()])
    confirm_password = PasswordField("Passwort bestätigen", validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField("Registrieren")