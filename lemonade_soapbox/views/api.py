from flask import (
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from flask_wtf import csrf

from lemonade_soapbox import db
from lemonade_soapbox.helpers import Blueprint
from lemonade_soapbox.models import Article, Post, Review, Tag

bp = Blueprint('api', __name__)


@bp.route('/csrf/')
def get_csrf():
    return csrf.generate_csrf()


@bp.route('/posts/autosave/', methods=['POST'])
@login_required
def autosave():
    """Autosave the current draft content of a post object."""
    parent = request.form.get('parent')
    body = request.form.get('body')
    post_type = request.form.get('post_type').capitalize()
    if parent:
        post = getattr(globals()[post_type], 'from_revision')(parent)
        if not post:
            abort(400)
        r = post.new_autosave(body)
        db.session.commit()
        date_created = r.date_created.to(current_app.config['TIMEZONE']).format(
            'HH:mm:ss, DD MMM YYYY'
        )
        return jsonify(revision_id=r.id, date=date_created)

    # We're composing a brand new post, so let's create a new draft entry
    # in the database.
    params = request.form.to_dict()
    del params["parent"]
    post = globals()[post_type](**params)
    post.new_revision()
    db.session.add(post)
    db.session.commit()

    return jsonify(
        revision_id=post.current_revision_id,
        post_id=post.id,
        created=post.date_created.to(current_app.config['TIMEZONE']).format(
            'MMM DD, YYYY HH:mm'
        ),
        handle=post.handle,
        link=post.get_permalink(),
        history=render_template('admin/posts/revision_history.html', post=post),
    )


@bp.route('/posts/goodreads-link/')
@login_required
def goodreads_link():
    """Given a review handle, return the Goodreads ID."""
    if q := request.args.getlist('q'):
        reviews = db.session.execute(
            db.select(Review.handle, Review.goodreads_id).filter(Review.handle.in_(q))
        ).all()
        # return jsonify([r._asdict() for r in reviews])
        return jsonify([(r.handle, r.goodreads_id) for r in reviews])
    return '', 204


@bp.route('/posts/search/')
@login_required
def posts_lookup():
    """Quick lookup of post by title."""
    data = "No results found."
    if term := request.args.get('q'):
        articles = (
            Article.query.filter(Article.title.ilike(f'%{term}%'))
            .order_by(Article.title_sort)
            .all()
        )
        reviews = (
            Review.query.filter(Review.title.ilike(f'%{term}%'))
            .order_by(Review.title_sort)
            .all()
        )
        current_app.logger.debug(articles)
        current_app.logger.debug(reviews)
        posts = articles + reviews
        posts.sort(key=lambda x: x.title)

        data = [
            {
                "id": post.id,
                "type": post.post_type,
                "title": getattr(post, 'short_title', post.title),
                "full_title": post.title,
                "edit": post.get_editlink(),
                "copy": post.get_permalink(),
            }
            for post in posts
        ]

    return jsonify(data)


@bp.route('/tags/delete/', methods=['POST'])
@login_required
def tags_delete():
    """Deletes a given tag."""
    label = request.json.get('tag')
    if tag := Tag.query.filter_by(label=label).first():
        db.session.delete(tag)
        db.session.commit()
        return jsonify(message='Tag deleted.')
    return jsonify(message='No tag found.'), 400


@bp.route('/tags/rename/', methods=['POST'])
@login_required
def tags_rename():
    """Renames a given tag."""
    old = request.json.get('old')
    new = request.json.get('new')
    if tag := Tag.query.filter_by(label=old).first():
        # Check if a tag with the new label already exists
        if conflict := Tag.query.filter_by(label=new).first():
            for p in tag.posts:
                p._tags.append(conflict)
            db.session.delete(tag)
            db.session.add(conflict)
        else:
            tag.label = new
            tag.handle = tag.slugify(new)
            db.session.add(tag)
        db.session.commit()
        return jsonify(message='Tag updated.')
    return jsonify(message='No tag found.'), 400


@bp.route('/tags/search/')
@login_required
def tags_lookup():
    """Returns a list of JSON objects of tags that begin with a given `term` GET parameter."""
    if term := request.args.get('term'):
        matches = Tag.query.filter(Tag.label.startswith(term))
        blueprints = {'article': 'blog', 'review': 'reviews'}
        if post_type := request.args.get('type'):
            matches = matches.join(Post._tags).filter(Post.post_type == post_type)
        just_tags = [
            {
                'handle': t.handle,
                'value': t.label,
                'url': url_for(
                    f'{blueprints.get(post_type, "blog")}.show_tag', handle=t.handle
                ),
            }
            for t in matches.all()
        ]
        return jsonify(just_tags)
    return jsonify({'result': 'No search term specified.'}), 400
