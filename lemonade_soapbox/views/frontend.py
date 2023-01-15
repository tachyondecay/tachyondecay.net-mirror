from flask import render_template, request, url_for
from whoosh.query import Term as whoosh_term

from lemonade_soapbox.models import Article, Review
from lemonade_soapbox.helpers import Blueprint, read_changelog

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
    per_page = request.args.get('per_page', 20, int)
    page_title = 'Search'
    articles = None
    if q:
        search_params = {
            'pagenum': page,
            'pagelen': per_page,
            'filter': whoosh_term('status', 'published'),  # Only return published posts
            'sort_order': request.args.get('sort', 'asc'),
        }

        if sort_by := request.args.get('sortby'):
            search_params['sort_field'] = sort_by

        articles = Article.search(q, **search_params)
        if articles:
            page_title = (
                f"{articles.total} article{'s' if articles.total > 1 else ''} found"
            )
        else:
            page_title = "No articles found"
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


@bp.route('/changelog/')
def changelog():
    """Display the contents of the changelog."""
    contents, toc_dict = read_changelog("tachyondecay.net")
    return render_template(
        "frontend/changelog.html",
        page_title="Changelog",
        changelog_contents=contents,
        toc_dict=toc_dict,
    )


@bp.route('/editing/')
def editing():
    return render_template(
        'frontend/editing.html',
        page_title='Freelance Editing Services',
    )


@bp.route('/podcasts/')
def podcasts():
    return render_template('frontend/podcasts.html', page_title='My Podcasts')
