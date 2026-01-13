from flask import Flask, render_template, flash, redirect, url_for, request, send_file
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user
from forms import LoginForm
import ldap3
from credentials import *

app = Flask(__name__)
app.config["SECRET_KEY"] = 'e79b9847144221ba4e85df9dd483a3e5'
login_manager = LoginManager(app)


# LDAP SETTINGS
LDAP_USER = LDAP_USER
LDAP_PASS = LDAP_PASS
LDAP_SERVER = LDAP_SERVER
AD_DOMAIN = AD_DOMAIN
SEARCH_BASE = SEARCH_BASE


class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.cn = ''
        self.mail = ''
        self.department = ''
        self.groups = []


@login_manager.user_loader
def load_user(uid):
    user = User(uid)
    if user:
        user.cn, user.mail, user.department, user.groups = get_user_data(uid)
    return user


def authenticate_ldap(username, password):
    """
    Check authentication of user against AD with LDAP
    :param username: Username
    :param password: Password
    :return: True is authentication is successful, else False
    """
    server = ldap3.Server(LDAP_SERVER, use_ssl=True, get_info=ldap3.ALL)

    try:
        with ldap3.Connection(server,
                              user=f'{AD_DOMAIN}\\{username}',
                              password=password,
                              authentication=ldap3.SIMPLE,
                              check_names=True,
                              raise_exceptions=True) as conn:
            if conn.bind():
                print("Authentication successful")
                user = User(username)
                return user
    except Exception as e:
        print(f"LDAP authentication failed: {e}")
    return False


def get_user_data(username):
    server = ldap3.Server(LDAP_SERVER, use_ssl=True, get_info=ldap3.ALL)
    with ldap3.Connection(server,
                          user=LDAP_USER,
                          password=LDAP_PASS,
                          auto_bind=True) as conn:
        if conn.bind():
            if conn.search('DC=stadt,DC=worms', "(&(sAMAccountName=" + username + "))",
                               ldap3.SUBTREE,
                               attributes=['mail', 'memberOf', 'department', 'cn']):
                cn = conn.entries[0]['cn']
                mail = conn.entries[0]['mail']
                department = conn.entries[0]['department']
                groups = [group.split(',')[0].split('=')[1] for group in conn.entries[0]['memberOf']]
                return cn, mail, department, groups
    return ""


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
        user = authenticate_ldap(form.username.data, form.password.data)
        if user:
            login_user(user, remember=True)
            flash("Eingeloggt als " + user.id + "!", "success")
            return redirect(url_for('home'))
        else:
            flash("Falsches Passwort oder Benutzername", "danger")
    return render_template("login.html", title="login", form=form)


@app.route("/logout", methods=["GET"])
def logout():
    logout_user()
    return redirect(url_for("login"))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
