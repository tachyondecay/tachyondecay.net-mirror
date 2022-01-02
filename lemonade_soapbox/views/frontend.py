from flask import render_template
from lemonade_soapbox.models import Article, Review
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
    reviews = Review.published().order_by(Review.date_published.desc()).limit(5).all()
    return render_template(
        'frontend/index.html', articles=articles, page_title='', reviews=reviews
    )


@bp.route('/search/')
def search():
    return ''


@bp.route('/about/')
def about_me():
    return render_template('frontend/about.html', page_title='About Me')


@bp.route('/podcasts/')
def podcasts():
    return render_template('frontend/podcasts.html', page_title='My Podcasts')
