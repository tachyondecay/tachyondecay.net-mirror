import json
from flask import (
    abort,
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    Response,
    url_for,
)
from flask_login import login_required
from flask_wtf import csrf
from sqlalchemy import text
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, Review, Tag, tag_relationships

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
    post_type = request.form.get('type').capitalize()
    if parent:
        post = getattr(globals()[post_type], 'from_revision')(parent)
        if not post:
            abort(404)
        r = post.new_autosave(body)
        db.session.commit()
        date_created = r.date_created.to(current_app.config['TIMEZONE']).format(
            'HH:mm:ss, DD MMM YYYY'
        )
        return jsonify(revision_id=r.id, date=date_created)
    else:
        # We're composing a brand new post, so let's create a new draft entry
        # in the database.
        post = globals()[post_type](
            handle=request.form.get('handle'),
            body=body,
            title=request.form.get('title'),
        )
        post.new_revision()
        db.session.add(post)
        db.session.commit()

        return jsonify(
            revision_id=post.revision_id,
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
        reviews = (
            db.session.query(Review.handle, Review.goodreads_id)
            .filter(Review.handle.in_(q))
            .all()
        )
        return jsonify(reviews)
    return jsonify('')


@bp.route('/posts/search/')
@login_required
def posts_lookup():
    """Quick lookup of post by title."""
    data = "No results found."
    if term := request.args.get('q'):
        articles = (
            Article.query.filter(Article.title.like(f'%{term}%'))
            .order_by(Article.title_sort)
            .all()
        )
        reviews = (
            Review.query.filter(Review.title.like(f'%{term}%'))
            .order_by(Review.title_sort)
            .all()
        )
        posts = articles + reviews
        posts.sort(key=lambda x: x.title)

        data = [
            {
                "type": post.type,
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
    else:
        return jsonify(message='No tag found.')


@bp.route('/tags/rename/', methods=['POST'])
@login_required
def tags_rename():
    """Renames a given tag."""
    old = request.json.get('old')
    new = request.json.get('new')
    if tag := Tag.query.filter_by(label=old).first():
        # Check if a tag with the new label already exists
        if conflict := Tag.query.filter_by(label=new).first():
            for a in tag.articles:
                a._tags.append(conflict)
            for r in tag.reviews:
                r._tags.append(conflict)
            db.session.delete(tag)
            db.session.add(conflict)
        else:
            tag.label = new
            tag.handle = tag.slugify(new)
            db.session.add(tag)
        db.session.commit()
        return jsonify(message='Tag updated.')
    else:
        return jsonify(message='No tag found.')


@bp.route('/tags/search/')
@login_required
def tags_lookup():
    """Returns a list of JSON objects of tags that begin with a given `term` GET parameter."""
    if term := request.args.get('term'):
        matches = Tag.query.filter(Tag.label.startswith(term))
        blueprints = {'article': 'blog', 'review': 'reviews'}
        if post_type := request.args.get('type'):
            table = tag_relationships.get(post_type.capitalize())
            if table is not None:
                matches = matches.join(table)
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
        return Response(json.dumps(just_tags), mimetype='application/json')
    else:
        return jsonify({'result': 'No search term specified.'}), 400
    return jsonify({})
