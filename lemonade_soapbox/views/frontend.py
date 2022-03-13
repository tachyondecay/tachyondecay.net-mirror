from flask import render_template, request, url_for
from flask_sqlalchemy import Pagination
from whoosh.query import Term as whoosh_term

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
    """Searching, obviously."""
    q = request.args.get('q')
    page = request.args.get('page', 1, int)
    page_title = 'Search'
    reviews = None
    mode = None
    if q:
        search_params = {
            'pagenum': page,
            'pagelen': 20,
            'filter': whoosh_term('status', 'published'),  # Only return published posts
        }

        # If query has no modifiers then search the title only
        # split_q = q.split(" ")
        # if split_q and ":" not in split_q[0]:
        #     mode = 'title'
        #     search_params['fields'] = 'title'

        results = Article.search(q, **search_params)
        # current_app.logger.debug(results)
        if results is not None and results['query'] is not None:
            articles = Pagination(
                None,
                page=page,
                per_page=20,
                total=results['total'],
                items=results['query'].all(),
            )
            page_title = (
                f"{results['total']} article{'s' if results['total'] > 1 else ''} found"
            )
        else:
            page_title = "No reviews found"
    return render_template(
        'blog/views/article_list.html',
        cover=url_for(
            '.static',
            filename='images/layout/header_bg/regine-tholen-pAs8r_VZEWc-unsplash.jpg',
        ),
        page_title=page_title,
        articles=articles,
    )


@bp.route('/about/')
def about_me():
    return render_template('frontend/about.html', page_title='About Me')


@bp.route('/editing/')
def editing():
    return render_template(
        'frontend/editing.html',
        page_title='Freelance Editing Services',
    )


@bp.route('/podcasts/')
def podcasts():
    return render_template('frontend/podcasts.html', page_title='My Podcasts')
