from flask import Blueprint

bp = Blueprint('roadmap', __name__)

from app.roadmap import routes