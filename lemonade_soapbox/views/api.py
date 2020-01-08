import json
from flask import abort, Blueprint, current_app, jsonify, render_template, request, Response, url_for
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, Tag

bp = Blueprint('api', __name__)


@bp.route('/articles/autosave/', methods=['POST'])
def autosave():
    """Autosave the current draft content of an article."""
    parent = request.form.get('parent')
    body = request.form.get('body')
    if parent:
        article = Article.from_revision(parent)
        if not article:
            abort(404)
        r = article.new_autosave(body)
        db.session.commit()
        return jsonify(revision_id=r.id,
                       date=r.date_created.to(current_app.config['TIMEZONE']).format('HH:mm:ss, DD MMM YYYY'))
    else:
        # We're composing a brand new article, so let's create a new draft entry
        # in the database.
        article = Article(title=request.form.get('title'),
                          handle=request.form.get('handle'),
                          body=body)
        article.new_revision()
        db.session.add(article)
        db.session.commit()

        return jsonify(revision_id=article.revision_id,
                       article_id=article.id,
                       created=article.date_created.to(current_app.config['TIMEZONE']).format('MMM DD, YYYY HH:mm'),
                       handle=article.handle,
                       link=article.get_permalink(),
                       history=render_template('admin/articles/revision_history.html',
                                               article=article,
                                               selected_revision=article.revision_id,
                                               revisions=article.revisions))


@bp.route('/articles/slugify/')
def get_handle():
    """Create a handle based on a given `title`."""
    handle = ''
    title = request.args.get('title')
    if title:
        a = Article()
        handle = a.slugify(title)
    return jsonify(handle=handle)


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
