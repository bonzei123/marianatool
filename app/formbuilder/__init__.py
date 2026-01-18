from flask import Blueprint

bp = Blueprint('formbuilder', __name__)

from app.formbuilder import routes