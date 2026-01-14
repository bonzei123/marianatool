from flask import Blueprint
bp = Blueprint('immo', __name__)
from app.immo import routes