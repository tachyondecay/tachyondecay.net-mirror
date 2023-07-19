import arrow
import os
from flask import abort, render_template, request, url_for
from flask_login import current_user

from lemonade_soapbox.helpers import Blueprint
from lemonade_soapbox.models import List
from lemonade_soapbox.views import frontend, reviews

bp = Blueprint('lists', __name__)


@bp.route('/')
def index():
    if current_user.is_authenticated:
        return request.blueprint
    return render_template(
        'reviews/layouts/basic.html',
        page_title="Lists Coming Soon",
        description="The lists feature is under construction! Check back in a few weeks.",
        cover=url_for(
            '.static',
            filename='images/layout/header_bg/glenn-carstens-peters-RLw-UC03Gwc-unsplash.jpg',
        ),
    )


@bp.route('/<handle>/')
def show_list(handle):
    this_list = List.query.filter_by(handle=handle).first_or_404()

    # Hide drafts and deleted lists, or lists published in the future, from
    # people who are not logged in
    if not current_user.is_authenticated and (
        this_list.status != 'published' or this_list.date_published > arrow.utcnow()
    ):
        abort(404)

    return render_template("reviews/views/single_list.html", list=this_list)


@bp.route('/categories/<handle>/')
def show_tag(handle):
    return ""


frontend.bp.register_blueprint(
    bp,
    host=os.getenv('MAIN_HOST'),
    url_prefix='/lists',
)
print("registered frontend")
reviews.bp.register_blueprint(
    bp,
    host=os.getenv('REVIEW_HOST'),
    url_prefix='/lists',
)
