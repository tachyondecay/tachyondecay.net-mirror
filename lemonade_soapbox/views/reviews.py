from flask import (
    Blueprint,
)
from flask_login import login_required

bp = Blueprint('reviews', __name__)


@bp.route('/')
def index():
    return ''


@bp.route('/drafts/<handle>/')
@login_required
def show_draft(handle):
    return ''


@bp.route('/trash/<handle>/')
@login_required
def show_deleted(handle):
    return ''


@bp.route('/<handle>/')
def show_published(handle):
    return ''
