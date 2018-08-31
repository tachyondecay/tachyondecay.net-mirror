import arrow
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
    url_for
)
from flask_login import current_user, login_user, login_required, logout_user
from lemonade_soapbox import db, mail
from lemonade_soapbox.forms import ArticleForm, SignInForm
from lemonade_soapbox.helpers import compose
from lemonade_soapbox.models import Article, Revision
from lemonade_soapbox.models.users import User
from sqlalchemy import and_, func

bp = Blueprint('admin', __name__)


@bp.before_request
def before_request():
    g.search_query = request.args.get('q', '')


@bp.route('/')
@login_required
def index():
    return 'Hello {}'.format(current_user.name)


@bp.route('/search/')
def search():
    """Search for articles."""
    next_year = str(arrow.utcnow().replace(years=1).year)
    q = request.args.get('q', 'date_created:<' + next_year).strip()
    results = None
    articles = None
    subtitle = 'No results found'

    if q:
        if q.startswith('id:') or q.startswith('revision:'):
            comp = q.split(':')
            return redirect(url_for('.edit_article', **{comp[0]: comp[1]}))

        search_params = {
            'pagenum': request.args.get('page', 1, int),
            'pagelen': request.args.get('per_page', 50, int),
            'sort_field': request.args.get('order_by', 'date_created'),
            'sort_order': request.args.get('order', 'desc')
        }
        current_app.logger.debug('Searching for "{}"'.format(q))
        results = Article.search(q, **search_params)
        if results is not None and results['query'] is not None:
            articles = results['query'].all()
            subtitle = 'Showing {} – {} of {}'.format(results['offset']+1,
                                                      results['offset'] + results['pagelen'],
                                                      results['total']
                                                 )
    return render_template('admin/views/search.html',
                           articles=articles,
                           mode='admin.search',
                           page_title='Search Results',
                           query_string=q,
                           results=results,
                           subtitle=subtitle)


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
                    flash('Welcome to the blog. Take a moment to fill out your '
                          'profile, if you please.', 'success')
                    return redirect(url_for('.edit_user', user_id=u.id))
        except Exception as e:
            flash(e, 'error')

    form = SignInForm(request.form)
    if form.validate_on_submit():
        msg = None

        # Flood control
        signin_email_time = session.get('signin_email_time', None)
        if signin_email_time and arrow.get(signin_email_time) > arrow.utcnow():
            flash('You can only request a signin link once every '
                  '{} minutes.'.format(current_app.config['LOGIN_EMAIL_FLOOD']), 'error')
        else:
            # Check if user exists
            u = User.query.filter_by(email=form.email.data).first()
            if u:
                # User found, generate an auth token
                token = u.generate_token(id=u.id, email=u.email)
                msg = compose(form.email.data,
                              'Sign Into {}'.format(current_app.config['BLOG_NAME']),
                              'email/signin',
                              signin_link=url_for('.signin', token=token, _external=True),
                              name=u.name)
            elif current_app.config['LOGIN_ALLOW_NEW']:
                # Generate a registration token
                token = User.generate_token(email=form.email.data, register=True)
                msg = compose(form.email.data,
                              'Confirm Registration at {}'.format(current_app.config['BLOG_NAME']),
                              'email/register',
                              signin_link=url_for('.signin', token=token, _external=True))
            else:
                flash('Your email doesn’t match any existing users, and registration is closed.', 'error')

            if msg:
                mail.send(msg)
                session['signin_email_time'] = arrow.utcnow().replace(minutes=current_app.config['LOGIN_EMAIL_FLOOD'])
                flash('Verification link sent to {}'.format(form.email.data), 'success')
                current_app.logger.info('Auth link sent to {}'.format(form.email.data))
        return redirect(url_for('.signin'))
    else:
        current_app.logger.debug(form.errors)

    return render_template('admin/views/signin.html',
                           signin_form=form,
                           page_title='Sign In')


@bp.route('/signout/')
def signout():
    if current_user.is_authenticated:
        name = current_user.name
        logout_user()
        flash('Goodbye, {}. You have been signed out.'.format(name), 'success')
    return redirect(url_for('.signin'))


@bp.route('/people/', defaults={'user_id': None})
@bp.route('/people/<int:user_id>/')
def show_users(user_id):
    if not user_id:
        # Show all users
        return 'List of all users'

    u = User.query.get(user_id)
    if not u:
        abort(404)
    return 'Profile for {}'.format(u.name)


@login_required
@bp.route('/people/<int:user_id>/edit/', methods=['GET', 'POST'])
def edit_user(user_id):
    u = User.query.get(user_id)
    if not u:
        abort(404)

    if u.id != current_user.id:
        abort(403)
    return 'Editing {}'.format(u.name)


#
# Blog endpoints
#


@bp.route('/blog/')
@login_required
def blog():
    """View and manage blog posts."""
    status = request.args.get('status', 'published')
    articles = Article.query.filter_by(status=status)
    subtitle = '{} Posts'.format(status.title())
    current_month = ''
    if not status or status == 'published':
        month = request.args.get('month')
        if month:
            month = arrow.get(month).span('month')
        else:
            month = arrow.utcnow().span('month')
        articles = articles.filter(Article.date_published.between(month[0], month[1]))
        current_app.logger.debug('Month: {}'.format(month))
        subtitle = 'posts from {}'.format(month[0].format('MMMM YYYY'))
        current_month = month[0].format('YYYY-MM')


    articles = articles.order_by(Article.date_updated.desc()).all()
    subtitle = '{} {}'.format(len(articles), subtitle)
    if len(articles) == 1:
        subtitle = subtitle.replace('posts', 'post')


    status_count = db.session.query(Article.status, func.count(Article.id)).group_by(Article.status).all()
    current_app.logger.debug(status_count)

    return render_template('admin/views/blog/index.html',
                           articles=articles,
                           current_status=status,
                           current_month=current_month,
                           page_title='Manage Blog Posts',
                           status_breakdown=status_count,
                           subtitle=subtitle)


@bp.route('/blog/write/', defaults={'id': None, 'revision_id': None}, methods=['POST', 'GET'])
@bp.route('/blog/write/<int:id>/', defaults={'revision_id': None}, methods=['POST', 'GET'])
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
        article = Article(author=current_user)
        # article.autosave = Revision.query.filter_by(article_id=None).first()

    if article.id:
        revisions = article.revisions.order_by(Revision.date_created.desc())\
            .filter(and_(Revision.id != article.autosave_id, Revision.major)).limit(5).all()
    else:
        revisions = None

    form = ArticleForm(obj=article)
    if(form.validate_on_submit()):
        message = ''
        message_category = 'success'
        # Save a copy of the original body before we overwrite it
        current_body = article.body
        form.populate_obj(article)
        if not form.handle.data:
            article.handle = article.slugify(article.title)

        # Remove an autosave if present, since we're creating a revision anyway
        if article.autosave:
            article.autosave_id = None
            db.session.delete(article.autosave)

        # Create a new revision, conditionally
        if current_body != form.body.data or article.revision_id != revision_id:
            article.new_revision(new=form.body.data, old=current_body)
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

    return render_template('admin/views/blog/write.html',
                           article=article,
                           form=form,
                           revisions=revisions,
                           selected_revision=revision_id)
