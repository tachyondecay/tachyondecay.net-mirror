from flask import request

from lemonade_soapbox.helpers import Blueprint

bp = Blueprint('lists', __name__)


@bp.route('/')
def index():
    return request.blueprint
