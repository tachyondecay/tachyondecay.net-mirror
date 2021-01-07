import base64
import random
from datetime import datetime
from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_user, login_required, logout_user
from flask_sqlalchemy import Pagination
from lemonade_soapbox import db
from lemonade_soapbox.forms import ArticleForm, ReviewForm, SignInForm
from lemonade_soapbox.helpers import Blueprint
from lemonade_soapbox.models import Article, Review, Tag
from lemonade_soapbox.models.users import User
from pathlib import Path
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


@bp.route('/tags/')
@login_required
def tag_manager():
    """Bulk management of all post tags."""
    page = request.args.get('page', 1, int)
    per_page = request.args.get('per_page', 100, int)
    sort_by = request.args.get('sort_by', 'label')
    order = 'asc' if request.args.get('order') == 'asc' else 'desc'
    post_types = request.args.getlist('filter') or ['Article', 'Review']
    tags = None

    tags = Tag.frequency(post_types=post_types, status=None)
    # if sort_by == 'label':
    #     current_app.logger.debug('Sorting by label')
    #     tags = tags.order_by(getattr(Tag.label, order)())
    # elif sort_by == 'frequency':

    tags = tags.paginate(page=page, per_page=per_page)
    tags.items = [dict(zip(i.keys(), i)) for i in tags.items]

    return render_template(
        'admin/views/tag_manager.html',
        page_title='Tag Manager',
        post_types=post_types,
        subtitle=f'{tags.total} tags found',
        tags=tags,
    )


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
    '/<post_type>/write/',
    defaults={'id': None, 'revision_id': None},
    methods=['POST', 'GET'],
)
@bp.route(
    '/<post_type>/write/<int:id>/',
    defaults={'revision_id': None},
    methods=['POST', 'GET'],
)
@bp.route(
    '/<post_type>/write/<revision_id>/', defaults={'id': None}, methods=['POST', 'GET']
)
@login_required
def edit_post(post_type, id, revision_id):
    """Compose a new post or edit an existing post."""
    specifics = {
        "blog": {
            "class": Article,
            "cover_dir": "blog",
            "cover_field": "cover",
            "form": ArticleForm,
        },
        "reviews": {
            "class": Review,
            "cover_dir": "book_covers",
            "cover_field": "book_cover",
            "form": ReviewForm,
        },
    }
    if post_type not in specifics:
        abort(404)
    else:
        specifics = specifics[post_type]

    # Load a post either by ID or a specific revision
    if id:
        post = specifics["class"].query.get_or_404(id)
        revision_id = post.revision_id
    elif revision_id:
        post = specifics["class"].from_revision(revision_id)
        if not post:
            abort(404)
    else:
        post = specifics["class"]()

    form = specifics["form"](obj=post)
    if form.validate_on_submit():
        message = ''
        message_category = 'success'
        redirect_url = None
        # Save a copy of the original body before we overwrite it
        old_body = post.body
        form.populate_obj(post)

        if not form.handle.data or (
            form.handle.data != post.handle and not post.unique_check(form.handle.data)
        ):
            form.populate_obj(post)
            post.handle = post.slugify(getattr(post, "short_title", post.title))
        else:
            form.populate_obj(post)

        #
        # Cover image uploading
        #
        # First, check if we uploaded a file the old-fashioned way
        cover_field = getattr(form, specifics["cover_field"])
        cover_path = Path(current_app.instance_path, "media", specifics["cover_dir"])
        if cover_field.data and request.files.get(cover_field.name):
            cover = request.files[cover_field.name]
            filename = secure_filename(
                post.handle + '-cover.' + cover.filename.rsplit('.', 1)[1].lower()
            )
            try:
                cover.save(cover_path / filename)
            except Exception as e:
                current_app.logger.warning(f'Could not upload cover image: {e}.')
                flash(
                    'There was a problem uploading the cover image. Try again?', 'error'
                )
                setattr(post, specifics["cover_field"], "")
            else:
                setattr(post, specifics["cover_field"], filename)
        elif form.pasted_cover.data and not form.remove_cover.data:
            # We're uploading a pasted image, so decode the base64
            # and see if we can save it as an image file
            try:
                filename = secure_filename(f'{post.handle}-cover.png')
                current_app.logger.info('Creating new image from pasted data.')
                with open(cover_path / filename, 'wb',) as f:
                    # Decode Base64 dataURL. The split is there to grab the
                    # "data" portion of the dataURL
                    f.write(base64.b64decode(form.pasted_cover.data.split(",")[1]))
            except Exception as e:
                current_app.logger.warning(f'Could not save cover image: {e}.')
                flash('There was a problem uploading the cover image. Try again?')
                setattr(post, specifics["cover_field"], "")
            else:
                setattr(post, specifics["cover_field"], filename)
        if getattr(post, specifics["cover_field"]) and (
            form.remove_cover.data or (post.status == 'deleted' and form.delete.data)
        ):
            try:
                file = cover_path / getattr(post, specifics["cover_field"])
                file.unlink()
                setattr(post, specifics["cover_field"], "")
                current_app.logger.info(f"Removed cover from {post.id}")
            except Exception as e:
                current_app.logger.warning(f'Could not delete cover image: {e}')
                flash('Could not delete cover image.', 'error')

        post.new_revision(old_body)
        if form.publish.data:
            message = post.publish_post()
        else:
            message = post.update_post()
            if form.delete.data:
                if post.status == 'deleted':
                    # Permanently deleting post
                    post.status = 'removed'
                    db.session.delete(post)
                    message = f'{post.__class__} permanently deleted.'
                    redirect_url = url_for('.blog')
                else:
                    post.status = 'deleted'
                    message = f'{post.__class__} moved to the trash.'
                message_category = 'removed'
            elif form.drafts.data:
                post.status = 'draft'
                post.date_published = None
                message = f'{post.__class__} moved to drafts.'
        if post.status != 'removed':
            db.session.add(post)
        db.session.commit()
        flash(message, message_category)
        return redirect(
            redirect_url or url_for('.edit_post', id=post.id, post_type=post_type)
        )
    elif form.errors:
        current_app.logger.debug(form.errors)
        flash('You need to fix a few things before you can save your changes.', 'error')

    return render_template(
        f'admin/views/{post_type}/write.html', post=post, form=form, post_type=post_type
    )


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
