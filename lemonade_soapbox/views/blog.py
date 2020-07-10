import arrow
import calendar
from flask import abort, current_app, g, redirect, render_template, Response, url_for
from flask_login import login_required
from gettext import ngettext
from lemonade_soapbox.helpers import Blueprint
from lemonade_soapbox.models import Article, Tag

bp = Blueprint('blog', __name__)


@bp.errorhandler(404)
def error404(e):
    return render_template('blog/errors/404.html'), 404


@bp.before_request
def before():
    # Grab the year/month breakdown of articles.
    g.breakdown = Article.post_breakdown()
    g.full_month_name = calendar.month_name
    g.month_name = calendar.month_abbr


@bp.route('/')
def index():
    articles = (
        Article.published().order_by(Article.date_published.desc()).limit(10).all()
    )
    return render_template(
        'blog/views/article_list.html', articles=articles, page_title='Recent Posts'
    )


@bp.route('/drafts/<handle>/')
@login_required
def show_draft(handle):
    article = Article.query.filter_by(handle=handle, status='draft').first_or_404()
    return render_template('blog/views/single_article.html', article=article)


@bp.route('/trash/<handle>/')
@login_required
def show_deleted(handle):
    article = Article.query.filter_by(handle=handle, status='deleted').first_or_404()
    return render_template('blog/views/single_article.html', article=article)


@bp.route('/feed/')
def default_feed():
    return redirect(
        url_for('.show_feed', format=current_app.config['DEFAULT_FEED_FORMAT'])
    )


@bp.route('/feed/posts.<format>')
def show_feed(format):
    articles = (
        Article.published().order_by(Article.date_published.desc()).limit(10).all()
    )
    return Response(
        render_template(
            'blog/articles/' + format + '.xml',
            articles=articles,
            url=url_for('blog.show_feed', _external=True, format=format),
        ),
        mimetype='application/' + format + '+xml',
    )


@bp.route('/tags/')
def all_tags():
    tags = [t for t in Tag.frequency(post_types=['Article']).all() if t[1] > 0]
    page_title = ngettext('%(num)d Tag', 'All %(num)d Tags', len(tags)) % {
        'num': len(tags)
    }
    return render_template('blog/views/tags.html', page_title=page_title, all_tags=tags)


@bp.route('/tags/<handle>/')
def show_tag(handle):
    tag = Tag.query.filter_by(handle=handle).first_or_404()
    # articles = tag.articles.order_by(Article.date_published.desc()).all()
    articles = sorted(tag.articles, key=lambda k: k.date_published, reverse=True)
    page_title = ngettext(
        '%(num)d Article Tagged with “%(t)s”',
        '%(num)d Articles Tagged with “%(t)s”',
        len(articles),
    ) % {'num': len(articles), 't': tag.label}

    return render_template(
        'blog/views/article_list.html', articles=articles, page_title=page_title
    )


@bp.route('/<int:year>/')
def year_archive(year):
    start, end = arrow.get(year, 1, 1).span('year')
    articles = (
        Article.published()
        .filter(Article.date_published.between(start, end))
        .order_by(Article.date_published.desc())
        .all()
    )
    if not articles:
        abort(404)
    page_title = ngettext(
        '%(num)d Article from %(year)s', '%(num)d Articles from %(year)s', len(articles)
    ) % {'num': len(articles), 'year': year}

    return render_template(
        'blog/views/year_archive.html',
        articles=articles,
        page_title=page_title,
        year=year,
    )


@bp.route('/<int:year>/<month>/')
def month_archive(year, month):
    start, end = arrow.get(year, int(month), 1).span('month')
    articles = (
        Article.published()
        .filter(Article.date_published.between(start, end))
        .order_by(Article.date_published.desc())
        .all()
    )
    if not articles:
        abort(404)
    page_title = ngettext(
        '%(num)d Article from %(month)s %(year)s',
        '%(num)d Articles from %(month)s %(year)s',
        len(articles),
    ) % {'num': len(articles), 'month': calendar.month_name[int(month)], 'year': year}

    return render_template(
        'blog/views/article_list.html', articles=articles, page_title=page_title
    )


@bp.route('/<int:year>/<month>/<handle>/')
def single_article(year, month, handle):
    start, end = arrow.get(year, int(month), 1).span('month')
    article = (
        Article.published()
        .filter(Article.date_published.between(start, end))
        .filter_by(handle=handle)
        .first_or_404()
    )
    return render_template('blog/views/single_article.html', article=article)
