import base64
import random
from datetime import datetime
from io import BytesIO

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
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import and_, func
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
    per_page = request.args.get('per_page', 50, int)
    sort_by = request.args.get(
        'sort_by', ('date_published' if status == 'published' else 'date_updated')
    )
    order = 'asc' if request.args.get('order') == 'asc' else 'desc'
    q = request.args.get('q')
    posts = None

    if q:
        search_params = {
            'pagenum': page,
            'pagelen': per_page,
            'sort_field': sort_by,
            'sort_order': order,
            'filter': whoosh_or([whoosh_term('status', x) for x in status]),
        }
        posts = post_class.search(q, **search_params)
    else:
        posts = (
            post_class.query.filter(post_class.status.in_(status))
            .order_by(getattr(getattr(post_class, sort_by), order)())
            .paginate(page=int(page), per_page=per_page)
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
        user = db.session.execute(
            db.select(User).filter_by(email=form.email.data)
        ).scalar_one_or_none()
        if not user or user.password != form.password.data:
            flash('Incorrect email address or password.', 'error')
            return redirect(url_for('.signin'))
        login_user(user)
        current_app.logger.info(f"{user.name} signed in to tachyondecay.net")

        # Sign an auth token for the reviews blueprint
        gateway = URLSafeTimedSerializer(current_app.secret_key)
        token = gateway.dumps(user.id)

        # Send the user to the reviews blueprint to be signed in there too
        return redirect(url_for("reviews.auth", action="signin", token=token))

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

        # Sign an auth token for the reviews blueprint
        gateway = URLSafeTimedSerializer(current_app.secret_key)
        token = gateway.dumps(current_user.id)

        logout_user()
        flash(f'Goodbye, {name}. You have been signed out.', 'success')
        current_app.logger.info(f"{name} signed out from tachyondecay.net")

        # Send the user to the reviews blueprint to be signed out there too
        return redirect(url_for("reviews.auth", action="signout", token=token))
    return redirect(url_for(".signin"))


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
        post_types=post_types,
        match=request.args.get("match"),
        status=None,
        page=page,
        per_page=per_page,
    )

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
        post = db.get_or_404(post_class, id)
        revision_id = getattr(post, "current_revision_id", None)
    elif revision_id and issubclass(post_class, RevisionMixin):
        post = post_class.from_revision(revision_id)
        if not post:
            abort(404)
    else:
        post = post_class()

    form = globals()[f"{post_class.__name__}Form"](obj=post)
    if form.validate_on_submit():
        # Save a copy of the original body before we overwrite it
        old_content = post.body

        if not form.handle.data or (
            form.handle.data != post.handle and not post.unique_check(form.handle.data)
        ):
            form.populate_obj(post)
            post.handle = post.slugify(getattr(post, "short_title", post.title))
        else:
            form.populate_obj(post)

        if form.delete.data:
            # Delete post
            message = post.save(action="deleted")
            db.session.commit()
            flash(message, "removed")
            return redirect(url_for("." + post_type))

        action = "saved"
        if form.publish.data:
            action = "published"
        elif form.drafts.data:
            action = "draft"

        message = post.save(
            action=action,
            old_content=old_content,
        )

        #
        # Cover image uploading
        cover_data = None
        if form.pasted_cover.data:  # This must come before next condition
            # Remove the data prefix on the binary image data
            cover_data = BytesIO(base64.b64decode(form.pasted_cover.data.split(",")[1]))
        elif form.cover.data:
            cover_data = request.files.get(form.cover.name)

        # Remove cover if desired
        if form.remove_cover.data and post.cover:
            (post.cover_path / post.cover).unlink(missing_ok=True)
            post.cover = ""
        else:
            try:
                if not post.id:
                    db.session.flush()
                post.process_cover(cover_data)
            except Exception as e:
                current_app.logger.warning(
                    f"Could not upload cover image for {post}: {e}."
                )
                flash(
                    "There was a problem uploading the cover image. Try again?", "error"
                )
                post.cover = ""

        db.session.commit()

        flash(message, "success")
        return redirect(url_for(".edit_post", id=post.id, post_type=post_type))
    if form.errors:
        current_app.logger.debug(form.errors)
        flash("You need to fix a few things before you can save your changes.", "error")

    return render_template(
        f'admin/views/{post_type}/write.html', post=post, form=form, post_type=post_type
    )


@bp.route('/lists/')
@login_required
def lists():
    """View and manage lists."""
    return posts_index(
        'list', 'admin/views/lists/index.html', page_title='Manage Lists'
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
