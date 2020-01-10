import json
from flask import abort, Blueprint, current_app, jsonify, render_template, request, Response, url_for
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, Review, Tag

bp = Blueprint('api', __name__)


@bp.route('/posts/autosave/', methods=['POST'])
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
        date_created = r.date_created.to(
            current_app.config['TIMEZONE']
        ).format('HH:mm:ss, DD MMM YYYY')
        return jsonify(revision_id=r.id, date=date_created)
    else:
        # We're composing a brand new post, so let's create a new draft entry
        # in the database.
        post = globals()[post_type](handle=request.form.get('handle'),
                                    body=body, title=request.form.get('title'))
        post.new_revision()
        db.session.add(post)
        db.session.commit()

        return jsonify(
            revision_id=post.revision_id,
            post_id=post.id,
            created=post.date_created.to(
                current_app.config['TIMEZONE']
            ).format('MMM DD, YYYY HH:mm'),
            handle=post.handle,
            link=post.get_permalink(),
            history=render_template(
                'admin/posts/revision_history.html',
                post=post
            )
        )

@bp.route('/tags/search/')
def tags_lookup():
    """Returns a list of JSON objects of tags that begin with a given `term` GET parameter."""
    term = request.args.get('term')
    if term is not None:
        matches = Tag.query.filter(Tag.label.startswith(term)).all()
        just_tags = [{'handle': t.handle,
                      'value': t.label,
                      'url': url_for('blog.show_tag', handle=t.handle),
                      } for t in matches]
        return Response(json.dumps(just_tags), mimetype='application/json')
    else:
        return jsonify({'result': 'No search term specified.'}), 400
    return jsonify({})
