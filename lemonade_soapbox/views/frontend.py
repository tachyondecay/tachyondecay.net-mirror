from flask import render_template
from lemonade_soapbox.models import Article
from lemonade_soapbox.helpers import Blueprint

bp = Blueprint('frontend', __name__, static_folder='assets')


@bp.app_errorhandler(404)
def error404(e):
    return render_template('frontend/404.html'), 404


@bp.route('/')
def index():
    articles = (
        Article.published().order_by(Article.date_published.desc()).limit(5).all()
    )
    return render_template('frontend/index.html', articles=articles, page_title='')


@bp.route('/about/')
def about_me():
    return render_template('frontend/about.html', page_title='About Me')
