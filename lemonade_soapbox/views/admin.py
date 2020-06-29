import base64
import os
import random
from datetime import datetime
from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, login_required, logout_user
from flask_sqlalchemy import Pagination
from lemonade_soapbox import db
from lemonade_soapbox.forms import ArticleForm, ReviewForm, SignInForm
from lemonade_soapbox.models import Article, Review
from lemonade_soapbox.models.users import User
from sqlalchemy import and_, func
from werkzeug.utils import secure_filename
from whoosh.query import Term as whoosh_term, Or as whoosh_or

bp = Blueprint('admin', __name__)


def posts_index(post_type, template, **kwargs):
    """
    Helper method that contains most of the logic common to both blog posts and reviews
    index.
    """
    post_class = globals()[post_type.capitalize()]
    status = request.args.getlist('status') or ['published']
    page = request.args.get('page', 1, int)
    sort_by = request.args.get(
        'sort_by', ('date_published' if status == 'published' else 'date_updated')
    )
    order = 'asc' if request.args.get('order') == 'asc' else 'desc'
    q = request.args.get('q')
    posts = Pagination(None, page=page, per_page=50, total=0, items=[])

    if q:
        search_params = {
            'pagenum': page,
            'pagelen': 50,
            'sort_field': sort_by,
            'sort_order': order,
            'filter': whoosh_or([whoosh_term('status', x) for x in status]),
        }
        results = post_class.search(q, **search_params)
        current_app.logger.debug(results)
        if results is not None and results['query'] is not None:
            posts.items = results['query'].all()
            posts.total = results['total']
    else:
        posts = (
            post_class.query.filter(post_class.status.in_(status))
            .order_by(getattr(getattr(post_class, sort_by), order)())
            .paginate(page=int(page), per_page=50)
        )

    status_count = (
        db.session.query(post_class.status, func.count(post_class.id))
        .group_by(post_class.status)
        .all()
    )
    subtitle = f"{posts.total} {post_type}" + ("s" if posts.total != 1 else "")

    return render_template(
        template,
        posts=posts,
        status_breakdown=status_count,
        status=status,
        subtitle=subtitle,
        **kwargs,
    )


@bp.route('/')
@login_required
def index():
    greetings = {
        "Arabic": "Ahlan",
        "Chinese": "Nǐ hǎo",
        "Danish": "Halløj",
        "Dutch": "Hallo",
        "French": "Salut",
        "German": "Guten Tag",
        "Greek": "Yassou",
        "Hindi": "Namaste",
        "Italian": "Ciao",
        "Japanese": "Konnichiwa",
        "Korean": "Anyoung",
        "Polish": "Dzień dobry",
        "Portuguese": "Olá",
        "Russian": "Privet",
        "Spanish": "¿Qué tal?",
        "Swahili": "Habari",
        "Swedish": "Hej",
        "Turkish": "Selam",
    }
    hello = random.choice(list(greetings))
    page_title = (
        f'<span title="{hello}">{greetings[hello]}</span>, '
        f'{current_user.first_name}!'
    )

    # Fetch stats
    published_count = {
        str(post_class.__name__): db.session.query(func.count(post_class.id))
        .filter(post_class.status == 'published')
        .scalar()
        for post_class in [Article, Review]
    }

    # Fetch drafts and upcoming posts
    drafts = []
    scheduled = []
    for post_class in [Article, Review]:
        drafts.extend(
            post_class.query.filter_by(status='draft')
            .order_by(post_class.date_updated)
            .limit(10)
            .all()
        )
        scheduled.extend(
            post_class.query.filter(
                and_(
                    post_class.status == 'published',
                    post_class.date_published > datetime.utcnow(),
                )
            )
            .order_by(post_class.date_published)
            .limit(10)
            .all()
        )
    drafts.sort(key=lambda x: x.date_updated, reverse=True)
    scheduled.sort(key=lambda x: x.date_published)

    return render_template(
        'admin/views/index.html',
        drafts=drafts,
        page_title=page_title,
        published=published_count,
        scheduled=scheduled,
        subtitle='Lemonade Soapbox Dashboard',
    )


@bp.route('/signin/', methods=['POST', 'GET'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('.index'))

    form = SignInForm(request.form)
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user or user.password != form.password.data:
            flash('Incorrect email address or password.', 'error')
            return redirect(url_for('.signin'))
        else:
            login_user(user)
            return redirect(url_for('.index'))
    else:
        current_app.logger.debug(form.errors)

    return render_template(
        'admin/views/signin.html',
        form=form,
        page_title='Lemonade Soapbox Dashboard',
        subtitle='Sign In',
    )


@bp.route('/signout/')
@login_required
def signout():
    if current_user.is_authenticated:
        name = current_user.name
        logout_user()
        flash('Goodbye, {}. You have been signed out.'.format(name), 'success')
    return redirect(url_for('.signin'))


#
# Blog endpoints
#


@bp.route('/blog/')
@login_required
def blog():
    """View and manage blog posts."""
    return posts_index(
        'article', 'admin/views/blog/index.html', page_title='Manage Blog Posts'
    )


@bp.route(
    '/blog/write/', defaults={'id': None, 'revision_id': None}, methods=['POST', 'GET']
)
@bp.route(
    '/blog/write/<int:id>/', defaults={'revision_id': None}, methods=['POST', 'GET']
)
@bp.route('/blog/write/<revision_id>/', defaults={'id': None}, methods=['POST', 'GET'])
@login_required
def edit_article(id, revision_id):
    """Compose a new article or edit an existing article."""
    # Load an article either by ID or a specific revision
    if id:
        article = Article.query.get_or_404(id)
        revision_id = article.revision_id
        g.search_query = 'id:' + str(id)
    elif revision_id:
        article = Article.from_revision(revision_id)
        g.search_query = 'revision:' + str(revision_id)
        if not article:
            abort(404)
    else:
        article = Article()
        # article.autosave = Revision.query.filter_by(article_id=None).first()

    form = ArticleForm(obj=article)
    if form.validate_on_submit():
        message = ''
        message_category = 'success'
        redirect_url = None
        # Save a copy of the original body before we overwrite it
        old_body = article.body
        form.populate_obj(article)

        if not form.handle.data:
            article.handle = article.slugify(article.title)

        #
        # Cover image uploading
        #
        # First, check if we uploaded a file the old-fashioned way
        if form.cover.data and request.files.get(form.cover.name):
            cover = request.files[form.book_cover.name]
            filename = secure_filename(
                article.handle + '-cover.' + cover.filename.rsplit('.', 1)[1].lower()
            )
            try:
                cover.save(
                    os.path.join(current_app.instance_path, 'media', 'blog', filename)
                )
            except Exception as e:
                current_app.logger.warn(f'Could not upload cover image: {e}.')
                flash(
                    'There was a problem uploading the cover image. Try again?', 'error'
                )
            else:
                article.cover = filename
        elif form.pasted_cover.data and not form.remove_cover.data:
            # We're uploading a pasted image, so decode the base64
            # and see if we can save it as an image file
            try:
                filename = secure_filename(f'{article.handle}-cover.png')
                current_app.logger.info('Creating new book image from pasted data.')
                with open(
                    os.path.join(current_app.instance_path, 'media', 'blog', filename),
                    'wb',
                ) as f:
                    # Decode Base64 dataURL. The split is there to grab the
                    # "data" portion of the dataURL
                    f.write(base64.b64decode(form.pasted_cover.data.split(",")[1]))
            except Exception as e:
                current_app.logger.warn(f'Could not save cover image: {e}.')
                flash('There was a problem uploading the cover image. Try again?')
            else:
                article.cover = filename
        if article.cover and (
            form.remove_cover.data or (article.status == 'deleted' and form.delete.data)
        ):
            try:
                os.remove(
                    os.path.join(
                        current_app.instance_path, 'media', 'blog', article.cover,
                    )
                )
                article.cover = ''
            except Exception as e:
                current_app.logger.warn(f'Could not delete cover image: {e}')
                flash('Could not delete cover image.', 'error')

        article.new_revision(old_body)
        if form.publish.data:
            message = article.publish_post()
        else:
            message = article.update_post()
            if form.delete.data:
                if article.status == 'deleted':
                    # Permanently deleting article
                    article.status = 'removed'
                    db.session.delete(article)
                    message = 'Article permanently deleted.'
                    redirect_url = url_for('.blog')
                else:
                    article.status = 'deleted'
                    message = 'Article moved to the trash.'
                message_category = 'removed'
            elif form.drafts.data:
                article.status = 'draft'
                article.date_published = None
                message = 'Article moved to drafts.'
        if article.status != 'removed':
            db.session.add(article)
        db.session.commit()
        flash(message, message_category)
        return redirect(redirect_url or url_for('.edit_article', id=article.id))
    elif form.errors:
        current_app.logger.debug(form.errors)
        flash('You need to fix a few things before you can save your changes.', 'error')

    return render_template('admin/views/blog/write.html', post=article, form=form)


#
# Review endpoints
#


@bp.route('/reviews/')
@login_required
def reviews():
    """View and manage reviews."""
    return posts_index(
        'review', 'admin/views/reviews/index.html', page_title='Manage Reviews'
    )


@bp.route(
    '/reviews/write/',
    defaults={'id': None, 'revision_id': None},
    methods=['POST', 'GET'],
)
@bp.route(
    '/reviews/write/<int:id>/', defaults={'revision_id': None}, methods=['POST', 'GET']
)
@bp.route(
    '/reviews/write/<revision_id>/', defaults={'id': None}, methods=['POST', 'GET']
)
@login_required
def edit_review(id, revision_id):
    """Compose a new review or edit an existing review."""
    # Load a review either by ID or a specific revision
    if id:
        review = Review.query.get_or_404(id)
        # revision_id = review.revision_id
        g.search_query = 'id:' + str(id)
    elif revision_id:
        review = Review.from_revision(revision_id)
        g.search_query = 'revision:' + str(revision_id)
        if not review:
            abort(404)
    else:
        review = Review()

    current_app.logger.debug(f'Review handle: {review.handle}')

    # Copy revisions section from edit_article when revisions enabled for reviews

    form = ReviewForm(obj=review)
    if form.validate_on_submit():
        message = ''
        message_category = 'success'
        redirect_url = None
        # Save a copy of the original body before we overwrite it
        old_body = review.body

        if not form.handle.data or (
            form.handle.data != review.handle
            and not review.unique_check(form.handle.data)
        ):
            form.populate_obj(review)
            review.handle = review.slugify(review.short_title)
        else:
            form.populate_obj(review)

        #
        # Book cover uploading
        #
        # First, check if we uploaded a file the old-fashioned way
        if form.book_cover.data and request.files.get(form.book_cover.name):
            cover = request.files[form.book_cover.name]
            filename = secure_filename(
                review.handle + '-cover.' + cover.filename.rsplit('.', 1)[1].lower()
            )
            try:
                cover.save(
                    os.path.join(
                        current_app.instance_path, 'media', 'book_covers', filename
                    )
                )
            except Exception as e:
                current_app.logger.warn(f'Could not upload book cover: {e}.')
                flash(
                    'There was a problem uploading the book cover. Try again?', 'error'
                )
            else:
                review.book_cover = filename
        elif form.pasted_cover.data and not form.remove_cover.data:
            # We're uploading a pasted image, so decode the base64
            # and see if we can save it as an image file
            try:
                filename = secure_filename(f'{review.handle}-cover.png')
                current_app.logger.info('Creating new book image from pasted data.')
                with open(
                    os.path.join(
                        current_app.instance_path, 'media', 'book_covers', filename
                    ),
                    'wb',
                ) as f:
                    # Decode Base64 dataURL. The split is there to grab the
                    # "data" portion of the dataURL
                    f.write(base64.b64decode(form.pasted_cover.data.split(",")[1]))
            except Exception as e:
                current_app.logger.warn(f'Could not save book cover: {e}.')
                flash('There was a problem uploading the book cover. Try again?')
            else:
                review.book_cover = filename
        if review.book_cover and (
            form.remove_cover.data or (review.status == 'deleted' and form.delete.data)
        ):
            try:
                os.remove(
                    os.path.join(
                        current_app.instance_path,
                        'media',
                        'book_covers',
                        review.book_cover,
                    )
                )
                review.book_cover = ''
            except Exception as e:
                current_app.logger.warn(f'Could not delete book cover: {e}')
                flash('Could not delete book cover.', 'error')

        review.new_revision(old_body)
        if form.publish.data:
            message = review.publish_post()
        else:
            message = review.update_post()
            if form.delete.data:
                if review.status == 'deleted':
                    # Permanently deleting review
                    review.status = 'removed'
                    db.session.delete(review)
                    message = 'Review permanently deleted.'
                    redirect_url = url_for('.reviews')
                else:
                    review.status = 'deleted'
                    message = 'Review moved to the trash.'
                message_category = 'removed'
            elif form.drafts.data:
                review.status = 'draft'
                review.date_published = None
                message = 'Review moved to drafts.'
        if review.status != 'removed':
            db.session.add(review)
        db.session.commit()
        flash(message, message_category)
        return redirect(redirect_url or url_for('.edit_review', id=review.id))
    elif form.errors:
        current_app.logger.debug(form.errors)
        flash('You need to fix a few things before you can save your changes.', 'error')

    return render_template('admin/views/reviews/write.html', post=review, form=form)
