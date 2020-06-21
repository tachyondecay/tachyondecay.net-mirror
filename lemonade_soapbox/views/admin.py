import arrow
import base64
import os
import random
from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_user, login_required, logout_user
from flask_sqlalchemy import Pagination
from lemonade_soapbox import db, mail
from lemonade_soapbox.forms import ArticleForm, ReviewForm, SignInForm
from lemonade_soapbox.helpers import compose
from lemonade_soapbox.models import Article, Review, Revision, Tag
from lemonade_soapbox.models.users import User
from sqlalchemy import and_, func
from werkzeug import secure_filename
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

    # Fetch drafts
    drafts = []
    for post_class in [Article, Review]:
        drafts.extend(
            post_class.query.filter_by(status='draft')
            .order_by(post_class.date_updated)
            .limit(5)
            .all()
        )
    drafts.sort(key=lambda x: x.date_updated, reverse=True)

    return render_template(
        'admin/views/index.html',
        drafts=drafts,
        page_title=page_title,
        published=published_count,
        subtitle='Lemonade Soapbox Dashboard',
    )


@bp.route('/signin/', methods=['POST', 'GET'])
def signin():
    if current_user.is_authenticated:
        return redirect(url_for('.index'))

    token = request.args.get('token', None)
    if token:
        try:
            u = User.verify(token)
            if u:
                if getattr(u, 'id', False):
                    login_user(u, remember=True)
                    current_app.logger.info('New signin: {}.'.format(u.name))
                    return redirect(url_for('.index'))
                else:
                    # Add user to the database and welcome them
                    db.session.add(u)
                    db.session.commit()
                    login_user(u, remember=True)
                    current_app.logger.info('New account created: {}.'.format(u.email))
                    flash(
                        'Welcome to the blog. Take a moment to fill out your '
                        'profile, if you please.',
                        'success',
                    )
                    return redirect(url_for('.edit_user', user_id=u.id))
        except Exception as e:
            flash(e, 'error')

    form = SignInForm(request.form)
    if form.validate_on_submit():
        msg = None

        # Flood control
        signin_email_time = session.get('signin_email_time', None)
        if signin_email_time and arrow.get(signin_email_time) > arrow.utcnow():
            flash(
                'You can only request a signin link once every '
                '{} minutes.'.format(current_app.config['LOGIN_EMAIL_FLOOD']),
                'error',
            )
        else:
            # Check if user exists
            u = User.query.filter_by(email=form.email.data).first()
            if u:
                # User found, generate an auth token
                token = u.generate_token(id=u.id, email=u.email)
                msg = compose(
                    form.email.data,
                    'Sign Into {}'.format(current_app.config['BLOG_NAME']),
                    'email/signin',
                    signin_link=url_for('.signin', token=token, _external=True),
                    name=u.name,
                )
            elif current_app.config['LOGIN_ALLOW_NEW']:
                # Generate a registration token
                token = User.generate_token(email=form.email.data, register=True)
                msg = compose(
                    form.email.data,
                    'Confirm Registration at {}'.format(
                        current_app.config['BLOG_NAME']
                    ),
                    'email/register',
                    signin_link=url_for('.signin', token=token, _external=True),
                )
            else:
                flash(
                    'Your email doesn’t match any existing users, and registration is closed.',
                    'error',
                )

            if msg:
                mail.send(msg)
                session['signin_email_time'] = arrow.utcnow().replace(
                    minute=current_app.config['LOGIN_EMAIL_FLOOD']
                )
                flash('Verification link sent to {}'.format(form.email.data), 'success')
                current_app.logger.info('Auth link sent to {}'.format(form.email.data))
        return redirect(url_for('.signin'))
    else:
        current_app.logger.debug(form.errors)

    return render_template(
        'admin/views/signin.html',
        signin_form=form,
        page_title='Sign In',
        subtitle='Secret Lair',
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
        # Save a copy of the original body before we overwrite it
        old_body = article.body
        form.populate_obj(article)

        if not form.handle.data:
            article.handle = article.slugify(article.title)

        article.new_revision(old_body)
        if form.publish.data:
            message = article.publish_post()
        else:
            message = article.update_post()
            if form.delete.data:
                article.status = 'deleted'
                message = 'Article moved to the trash.'
                message_category = 'removed'
            elif form.drafts.data:
                article.status = 'draft'
                article.date_published = None
                message = 'Article moved to drafts.'
        db.session.add(article)
        db.session.commit()
        flash(message, message_category)
        return redirect(url_for('.edit_article', id=article.id))
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

    # Copy revisions section from edit_article when revisions enabled for reviews

    form = ReviewForm(obj=review)
    if form.validate_on_submit():
        message = ''
        message_category = 'success'
        # Save a copy of the original body before we overwrite it
        old_body = review.body
        old_handle = review.handle
        form.populate_obj(review)
        if old_handle != review.handle and not (
            form.handle.data and review.unique_check(review.handle)
        ):
            review.handle = review.slugify(review.title)

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
        if form.remove_cover.data and review.book_cover:
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
                review.status = 'deleted'
                message = 'Review moved to the trash.'
                message_category = 'removed'
            elif form.drafts.data:
                review.status = 'draft'
                review.date_published = None
                message = 'Review moved to drafts.'
        db.session.add(review)
        db.session.commit()
        flash(message, message_category)
        return redirect(url_for('.edit_review', id=review.id))
    elif form.errors:
        current_app.logger.debug(form.errors)
        flash('You need to fix a few things before you can save your changes.', 'error')

    return render_template('admin/views/reviews/write.html', post=review, form=form)
