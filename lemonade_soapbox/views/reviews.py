import random
import re
from pathlib import Path

import arrow
from flask import (
    abort,
    current_app,
    g,
    redirect,
    render_template,
    Response,
    request,
    url_for,
)
from flask_login import current_user
from flask_sqlalchemy import Pagination
from sqlalchemy import desc, or_, not_
from whoosh.query import Term as whoosh_term

from lemonade_soapbox import db
from lemonade_soapbox.helpers import Blueprint, read_changelog
from lemonade_soapbox.models import Post, Review, Tag

bp = Blueprint('reviews', __name__)


@bp.context_processor
def sitenav():
    links = [
        ("Bookshelves", "reviews.all_tags", "Reviews organized by categories"),
        ("Lists", "reviews.lists.index", "Series, Top 10 lists, and more!"),
        (
            "Review Index",
            "reviews.all_reviews",
            "All my reviews, grouped by year and month",
        ),
        ("Random", "reviews.random_review", "Are you feeling lucky?"),
    ]
    return dict(sitenav=links)


@bp.errorhandler(404)
def error_404(e):
    current_app.logger.info(f"404 not found: {e}")
    return (
        render_template(
            'reviews/layouts/basic.html',
            page_title="Page Not Found",
            description="Looks like the link you followed doesn’t work anymore. Maybe try searching for what you want?",
            cover=url_for(
                '.static',
                filename='images/layout/header_bg/syd-wachs-slItfWbhijc-unsplash.jpg',
            ),
        ),
        404,
    )


@bp.before_request
def before():
    g.total = (
        db.session.query(db.func.count(Review.id))
        .filter(Review.status == 'published')
        .scalar()
    )


@bp.route('/')
def index():
    # Get most recent fiction and non-fiction reviews
    fiction = (
        Review.published()
        .filter(not_(Review.tags.in_(['non-fiction'])))
        .order_by(Review.date_published.desc())
        .limit(3)
        .all()
    )
    non_fiction = (
        Review.published()
        .filter(Review.tags.in_(['non-fiction']))
        .order_by(Review.date_published.desc())
        .limit(3)
        .all()
    )
    return render_template(
        'reviews/index.html',
        reviews=(("Fiction", fiction), ("Non-Fiction", non_fiction)),
        total_reviews=g.total,
    )


@bp.route('/about/')
def about():
    return render_template('reviews/about.html', page_title='About This Site')


@bp.route('/changelog/')
def changelog():
    """Display the contents of the changelog."""
    contents, toc_dict = read_changelog("kara.reviews")
    return render_template(
        "reviews/changelog.html",
        page_title="Changelog",
        changelog_contents=contents,
        toc_dict=toc_dict,
    )


@bp.route('/feed/posts.<format>')
def show_feed(format):
    reviews = Review.published().order_by(Review.date_published.desc()).limit(10).all()
    return Response(
        render_template(
            'reviews/' + format + '.xml',
            page_title='All Reviews from Kara.Reviews',
            reviews=reviews,
            url=url_for('reviews.show_feed', _external=True, format=format),
        ),
        mimetype='application/' + format + '+xml',
    )


@bp.route('/random/')
def random_review():
    """Load a random book review."""
    review = Review.published().order_by(db.func.random()).first()
    return redirect(review.get_permalink(False))


@bp.route('/index/')
def all_reviews():
    """All reviews, grouped by year."""
    reviews = Review.published().order_by(Review.date_published).all()
    return render_template(
        'reviews/views/all_reviews.html',
        page_title="All Reviews, by Year",
        reviews=reviews,
    )


@bp.route('/search/')
def search():
    """Searching, obviously."""
    q = request.args.get('q')
    page = request.args.get('page', 1, int)
    per_page = request.args.get('per_page', 20, int)
    page_title = 'Search'
    reviews = None
    mode = None
    if q:
        search_params = {
            'pagenum': page,
            'pagelen': per_page,
            'filter': whoosh_term(
                'status', 'published'
            ),  # Only return published reviews
        }

        if sort_by := request.args.get('sortby'):
            search_params['sortedby'] = sort_by

            if reverse := request.args.get('reverse'):
                search_params['reverse'] = True

        # If query has no modifiers then search the title only
        split_q = q.split(" ")
        if split_q and ":" not in split_q[0]:
            mode = 'title'
            search_params['fields'] = 'title'

        results = Review.search(q, **search_params)
        # current_app.logger.debug(results)
        if results and (query := results['query']):
            if sort_by:
                query = (
                    query.order_by(desc(sort_by))
                    if reverse
                    else query.order_by(sort_by)
                )

            reviews = Pagination(
                None,
                page=page,
                per_page=per_page,
                total=results['total'],
                items=query,
            )
            page_title = (
                f"{results['total']} review{'s' if results['total'] > 1 else ''} found"
            )
        else:
            page_title = "No reviews found"
    return render_template(
        'reviews/views/review_list.html',
        cover=url_for(
            '.static',
            filename='images/layout/header_bg/regine-tholen-pAs8r_VZEWc-unsplash.jpg',
        ),
        mode=mode,
        page_title=page_title,
        reviews=reviews,
    )


@bp.route('/shelves/')
def all_tags():
    """Display a list of all tags."""
    shelves = [
        t for t in Tag.frequency(post_types=['review']).all() if t["review_count"] > 0
    ]
    sort_by = request.args.get('sort', 'alphabetical')
    return render_template(
        'reviews/views/shelves.html',
        page_title='My Bookshelves',
        shelves=shelves,
        sort_by=sort_by,
    )


@bp.route('/shelves/<handle>/')
@bp.route('/shelves/<handle>/posts.<format>')
def show_tag(handle, format=None):
    page = request.args.get('page', 1, int)
    shelf = Tag.query.filter_by(handle=handle).first_or_404()
    reviews = shelf.posts.filter(
        Post.post_type == "review",
        Post.status == 'published',
        Post.date_published <= arrow.utcnow(),
    ).order_by(Post.date_published.desc())

    if format:
        return Response(
            render_template(
                'reviews/' + format + '.xml',
                page_title=f'Kara.Reviews: {shelf.label.title()} Books',
                reviews=reviews.all(),
                url=url_for(
                    'reviews.show_tag',
                    _external=True,
                    handle=handle,
                    format=format,
                ),
            ),
            mimetype='application/' + format + '+xml',
        )

    reviews = reviews.paginate(page=page, per_page=20)
    filename = 'susan-yin-2JIvboGLeho-unsplash.jpg'
    if Path(
        current_app.static_folder, 'images/layout/header_bg', f"{handle}.jpg"
    ).exists():
        filename = handle + '.jpg'
    return render_template(
        'reviews/views/review_list.html',
        handle=handle,
        read_more_length=75,
        reviews=reviews,
        page_title=f'Books shelved under “{shelf.label.title()}”',
        cover=url_for(
            '.static',
            filename='images/layout/header_bg/' + filename,
            _external=True,
        ),
    )


@bp.route('/<handle>/')
def show_review(handle):
    """Display a review."""
    review = Review.query.filter_by(handle=handle).first_or_404()

    # Hide drafts and deleted reviews, or reviews published in the future, from
    # people who are not logged in
    if not current_user.is_authenticated and (
        review.status != 'published' or review.date_published > arrow.utcnow()
    ):
        abort(404)

    related_reviews = {}
    # Grab reviews from the same author
    from_author = (
        Review.published()
        .filter(Review.book_author == review.book_author, Review.id != review.id)
        .order_by(Review.date_published.desc())
        .limit(3)
        .all()
    )
    if from_author:
        related_reviews['More From This Author'] = from_author
    # Look for reviews of books mentioned in this review
    title_patterns = [
        re.compile(r'<cite>([^>]+)</cite>'),
        re.compile(r'<cite><a href=\"[^\"]+\">([^<]+)</a></cite>'),
    ]
    mentioned = None
    titles_mentioned = []
    for p in title_patterns:
        matches = p.findall(review.body_html)
        if matches:
            titles_mentioned.extend(matches)
    if titles_mentioned:
        mentioned = (
            Review.published()
            .filter(
                Review.id != review.id,
                or_(*[Review.title.startswith(t) for t in titles_mentioned]),
            )
            .all()
        )
    if mentioned:
        related_reviews['Mentioned in This Review'] = mentioned
    # If all else fails, grab books from the same shelf
    # if not (from_author or mentioned):
    if review._tags:
        shelf = random.choice(review._tags)
        shelved = (
            shelf.posts.filter(
                Post.post_type == "review",
                Post.status == 'published',
                Post.id != review.id,
            )
            .order_by(db.func.random())
            .limit(3)
            .all()
        )
        if shelved:
            related_reviews[f'More {shelf.label} Reviews'] = shelved

    # Make sure no review appears more than once in the related reviews
    ids = []
    for t, l in related_reviews.items():
        for r in l:
            if r.id in ids:
                l.remove(r)
            else:
                ids.append(r.id)

    return render_template(
        'reviews/views/single_review.html',
        related_reviews=related_reviews,
        review=review,
    )
