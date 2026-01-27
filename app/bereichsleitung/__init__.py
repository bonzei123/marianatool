from flask import Blueprint

bp = Blueprint('bereichsleitung', __name__)

from app.bereichsleitung import routes