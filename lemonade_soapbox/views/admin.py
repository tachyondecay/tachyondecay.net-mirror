import base64
import random
from datetime import datetime
from pathlib import Path

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
from sqlalchemy import and_, func
from werkzeug.utils import secure_filename
from whoosh.query import Term as whoosh_term, Or as whoosh_or

from lemonade_soapbox import db
from lemonade_soapbox.forms import ArticleForm, ListForm, ReviewForm, SignInForm
from lemonade_soapbox.helpers import Blueprint
from lemonade_soapbox.models.posts import (
    Article,
    List,
    ListItem,
    Review,
    RevisionMixin,
    Tag,
)
from lemonade_soapbox.models.users import User

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
    post_types = request.args.getlist('filter') or ['article', 'review']
    tags = None

    tags = Tag.frequency(
        post_types=post_types, status=None, page=page, per_page=per_page
    )
    # if sort_by == 'label':
    #     current_app.logger.debug('Sorting by label')
    #     tags = tags.order_by(getattr(Tag.label, order)())
    # elif sort_by == 'frequency':

    tags = Pagination(
        query=None,
        page=page,
        per_page=per_page,
        total=Tag.query.count(),
        items=tags,
    )
    # tags.items = [dict(zip(i.keys(), i)) for i in tags.items]

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
    post_classes = {"blog": Article, "lists": List, "reviews": Review}

    if post_type not in post_classes:
        abort(404)
    post_class = post_classes[post_type]

    # Load a post either by ID or a specific revision
    if id:
        post = post_class.query.get_or_404(id)
        revision_id = getattr(post, "current_revision_id", None)
    elif revision_id and issubclass(post_class, RevisionMixin):
        post = post_class.from_revision(revision_id)
        if not post:
            abort(404)
    else:
        post = post_class()

    form = globals()[f"{post_class.__name__}Form"](obj=post)
    if form.validate_on_submit():
        message = ''
        message_category = 'success'
        redirect_url = None
        # Save a copy of the original body before we overwrite it
        old_body = post.body

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
        cover_path = current_app.instance_path / "media" / post.post_type / "covers"
        if form.cover.data and request.files.get(form.cover.name):
            cover = request.files[form.cover.name]
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
                post.cover = ""
            else:
                post.cover = filename
        elif form.pasted_cover.data and not form.remove_cover.data:
            # We're uploading a pasted image, so decode the base64
            # and see if we can save it as an image file
            try:
                filename = secure_filename(f'{post.handle}-cover.png')
                current_app.logger.info('Creating new image from pasted data.')
                with open(
                    cover_path / filename,
                    'wb',
                ) as f:
                    # Decode Base64 dataURL. The split is there to grab the
                    # "data" portion of the dataURL
                    f.write(base64.b64decode(form.pasted_cover.data.split(",")[1]))
            except Exception as e:
                current_app.logger.warning(f'Could not save cover image: {e}.')
                flash('There was a problem uploading the cover image. Try again?')
                post.cover = ""
            else:
                post.cover = filename
        if post.cover and (
            form.remove_cover.data or (post.status == 'deleted' and form.delete.data)
        ):
            try:
                file = cover_path / post.cover
                file.unlink()
                post.cover = ""
                current_app.logger.info(f"Removed cover from {post.id}")
            except Exception as e:
                current_app.logger.warning(f'Could not delete cover image: {e}')
                flash('Could not delete cover image.', 'error')

        if issubclass(post, RevisionMixin):
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
                    # Need to do this to avoid SQLAlchemy RACE condition
                    if issubclass(post, RevisionMixin):
                        db.session.delete(post.selected_revision)
                    message = f'{post.post_type.capitalize()} permanently deleted.'
                    redirect_url = url_for(f".{post_type}")
                else:
                    post.status = 'deleted'
                    message = f'{post.post_type.capitalize()} moved to the trash.'
                message_category = 'removed'
            elif form.drafts.data:
                post.status = 'draft'
                post.date_published = None
                message = f'{post.post_type.capitalize()} moved to drafts.'
        if post.status != 'removed':
            db.session.add(post)
        db.session.commit()
        flash(message, message_category)
        return redirect(
            redirect_url or url_for('.edit_post', id=post.id, post_type=post_type)
        )
    if form.errors:
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
