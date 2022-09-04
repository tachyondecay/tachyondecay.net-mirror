import calendar
from gettext import ngettext
from pathlib import Path

import arrow
from flask import (
    abort,
    current_app,
    g,
    redirect,
    render_template,
    request,
    Response,
    url_for,
)
from flask_login import current_user, login_required

from lemonade_soapbox import db
from lemonade_soapbox.helpers import Blueprint
from lemonade_soapbox.models import Article, Post, Tag

bp = Blueprint('blog', __name__)


@bp.errorhandler(404)
def error404(e):
    return render_template('blog/errors/404.html'), 404


@bp.route('/')
def index():
    page = request.args.get('page', 1, int)
    articles = (
        Article.published()
        .order_by(Article.date_published.desc())
        .paginate(page=page, per_page=10)
    )
    return render_template(
        'blog/views/index.html',
        articles=articles,
        description="Read my thoughts going back 18 years.",
        page_title="Kara’s Blog",
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
    tags = [
        t for t in Tag.frequency(post_types=['article']).all() if t["article_count"] > 0
    ]
    sort_by = request.args.get('sort', 'frequency')
    page_title = ngettext('%(num)d Tag', 'All %(num)d Tags', len(tags)) % {
        'num': len(tags)
    }
    return render_template(
        'blog/views/tags.html', page_title=page_title, tags=tags, sort_by=sort_by
    )


@bp.route('/tags/<handle>/')
@bp.route('/tags/<handle>/posts.<format>')
def show_tag(handle, format=None):
    page = request.args.get('page', 1, int)
    tag = Tag.query.filter_by(handle=handle).first_or_404()
    articles = tag.posts.filter(
        Post.post_type == "article",
        Post.status == 'published',
        Post.date_published <= arrow.utcnow(),
    ).order_by(Post.date_published.desc())

    if format:
        return Response(
            render_template(
                'blog/articles/' + format + '.xml',
                title=f'Kara.Reviews: {tag.label.title()} Books',
                articles=articles.all(),
                url=url_for(
                    'blog.show_tag',
                    _external=True,
                    handle=handle,
                    format=format,
                ),
            ),
            mimetype='application/' + format + '+xml',
        )

    articles = articles.paginate(page=page, per_page=20)

    cover = None
    if Path(
        current_app.static_folder, 'images/layout/header_bg', f"{handle}.jpg"
    ).exists():
        cover = url_for(
            '.static', filename=f"images/layout/header_bg/{handle}.jpg", _external=True
        )

    return render_template(
        'blog/views/article_list.html',
        handle=handle,
        read_more_length=75,
        articles=articles,
        page_title=f"Articles Tagged with “{tag.label}”",
        cover=cover,
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

    # Check if there are posts for previous and next years
    prev_link = (
        Article.published()
        .filter(db.func.extract('YEAR', Article.date_published) == (year - 1))
        .count()
        > 0
    )
    next_link = (
        Article.published()
        .filter(db.func.extract('YEAR', Article.date_published) == (year + 1))
        .count()
        > 0
    )

    year_summaries = {
        "2004": "First year of university, first real job, first year online.",
        "2005": "In which I discover Doctor Who, move high schools, and get political.",
        "2006": "Learning how to drive, playing with Linux, and more politics.",
        "2007": "Pop culture, environmental awareness, and high school graduation.",
        "2008": "Joining Twitter and Goodreads, visiting an online friend, discovering Mass Effect.",
        "2009": "Lots of thoughts on technology, more politics.",
        "2010": "A summer spent researching mathematics, my first smartphone.",
        "2011": "In which I was very into voting for the Hugo Awards.",
        "2012": "Learning how to knit, graduating university, and moving to England.",
        "2013": "Living and teaching in England and a lot of pop culture.",
        "2014": "Trip to Amsterdam, moving back to Canada, new phone who dis?",
        "2015": "In which I start blogging seriously about education.",
        "2016": "Critical reflections on education, algorithms, and some lighter fare in knitting.",
        "2017": "On being asexual and aromantic, buying a house, and meeting my ride or die",
        "2018": "Starting a podcast with my bestie, visiting her in Montréal.",
        "2019": "More reflections on being an educator in Ontario.",
        "2020": "Coming out as trans, launching Kara.Reviews.",
        "2021": "Transition during a pandemic and reflections on friendship and pop culture.",
        "2022": "The current year. I hope it’s a good one!",
    }

    return render_template(
        'blog/views/year_archive.html',
        articles=articles,
        page_title=f"{len(articles)} Articles from {year}",
        prev_link=prev_link,
        next_link=next_link,
        month_name=calendar.month_name,
        year=year,
        year_summaries=year_summaries,
    )


@bp.route('/<int:year>/<month>/')
def month_archive(year, month):
    if int(month) not in range(1, 13):
        abort(404)
    start, end = arrow.get(year, int(month), 1).span('month')
    articles = (
        Article.published()
        .filter(Article.date_published.between(start, end))
        .order_by(Article.date_published.desc())
        .all()
    )
    if not articles:
        abort(404)

    # Check if there are posts for previous and next months
    prev_article = (
        Article.published()
        .filter(Article.date_published < articles[-1].date_published)
        .order_by(Article.date_published.desc())
        .first()
    )
    prev_link = (
        (
            url_for(
                ".month_archive",
                year=prev_article.date_published.year,
                month=f"{prev_article.date_published.month:02}",
            ),
            prev_article.date_published.format("MMMM YYYY"),
        )
        if prev_article
        else None
    )
    next_article = (
        Article.published()
        .filter(Article.date_published > articles[0].date_published)
        .order_by(Article.date_published.asc())
        .first()
    )
    next_link = (
        (
            url_for(
                ".month_archive",
                year=next_article.date_published.year,
                month=f"{next_article.date_published.month:02}",
            ),
            next_article.date_published.format("MMMM YYYY"),
        )
        if next_article
        else None
    )

    return render_template(
        'blog/views/article_list.html',
        articles=articles,
        description=f"{len(articles)} articles",
        prev_link=prev_link,
        next_link=next_link,
        page_title=f"Articles from {calendar.month_name[int(month)]} {year}",
    )


@bp.route('/<int:year>/<month>/<handle>/')
def single_article(year, month, handle):
    start, end = arrow.get(year, int(month), 1).span('month')
    article = Article.query if current_user.is_authenticated else Article.published()
    article = (
        article.filter(Article.date_published.between(start, end))
        .filter_by(handle=handle)
        .first_or_404()
    )
    return render_template('blog/views/single_article.html', article=article)
