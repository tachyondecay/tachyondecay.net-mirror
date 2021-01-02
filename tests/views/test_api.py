import pytest
from flask_wtf import csrf
from lemonade_soapbox.models import Article, Review, Tag
from sqlalchemy.orm.util import was_deleted
from tests.factories import ArticleFactory, ReviewFactory

pytestmark = pytest.mark.usefixtures("db")


def test_get_csrf(client):
    resp = client.get("http://main.test/api/csrf/")
    assert resp.status_code == 200


@pytest.mark.parametrize("post_type", [Article, Review])
def test_autosave(client, db, post_type, signin):
    data = {
        "body": "This is a test post body.",
        "title": "Post title here",
        "type": str(post_type.__name__).lower(),
    }

    # Test with a new post
    resp = client.post("http://main.test/api/posts/autosave/", data=data)
    assert resp.mimetype == "application/json"

    json = resp.get_json()
    post = post_type.query.filter_by(title=data["title"]).first()
    assert post
    assert post.revision_id == json["revision_id"]
    assert post.id == json["post_id"]
    assert post.handle == json["handle"]

    # Test with editing a post
    data["parent"] = post.revision_id
    data["body"] = "The new body of this post now."
    resp = client.post("http://main.test/api/posts/autosave/", data=data)
    assert resp.mimetype == "application/json"
    json = resp.get_json()
    assert post.autosave_id == json["revision_id"]

    # Test post 404
    data["parent"] = "invalid"
    resp = client.post("http://main.test/api/posts/autosave/", data=data)
    assert resp.status_code == 400

    db.session.delete(post)
    db.session.commit()


def test_goodreads_link(client, signin):
    # Test no input
    resp = client.get("http://main.test/api/posts/goodreads-link/")
    assert resp.status_code == 204

    r = ReviewFactory(handle="test-handle")
    resp = client.get("http://main.test/api/posts/goodreads-link/?q=test-handle")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert resp.get_json() == [[r.handle, r.goodreads_id]]


def test_posts_lookup(client, signin):
    a1 = ArticleFactory(title="Hello world")
    r1 = ReviewFactory(title="Say hello world")
    r2 = ReviewFactory(title="Hello to the world")
    resp = client.get("http://main.test/api/posts/search/?q=hello+world")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    json = resp.get_json()
    assert len(json) == 2


def test_tags_delete(client, db, signin):
    # No tag found
    resp = client.post("http://main.test/api/tags/delete/", json={"tag": "hello world"})
    assert resp.status_code == 400
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"message": "No tag found."}

    # Actually delete
    tag = Tag(label="hello world")
    db.session.add(tag)
    db.session.flush()

    resp = client.post("http://main.test/api/tags/delete/", json={"tag": "hello world"})
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"message": "Tag deleted."}
    assert was_deleted(tag)


def test_tags_lookup(client, db, signin):
    # No term
    resp = client.get("http://main.test/api/tags/search/")
    assert resp.status_code == 400
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"result": "No search term specified."}

    tag = Tag(label="hello world")
    db.session.add(tag)
    db.session.flush()

    ArticleFactory(tags=["hello world"])
    resp = client.get("http://main.test/api/tags/search/?term=hello&type=article")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert len(resp.get_json()) == 1

    resp = client.get("http://main.test/api/tags/search/?term=hello&type=review")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert len(resp.get_json()) == 0


def test_tags_rename(client, db, signin):
    # No tag found
    resp = client.post("http://main.test/api/tags/rename/", json={"old": "hello world"})
    assert resp.status_code == 400
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"message": "No tag found."}

    # Actually rename
    tag = Tag(label="hello world")
    db.session.add(tag)
    db.session.flush()

    resp = client.post(
        "http://main.test/api/tags/rename/",
        json={"old": "hello world", "new": "goodbye world"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"message": "Tag updated."}
    assert tag.label == "goodbye world"
    assert tag.handle == "goodbye-world"

    # Merge conflict
    conflict = Tag(label="brave new world")
    db.session.add(conflict)
    db.session.flush()

    a = ArticleFactory(tags=["goodbye world"])
    r = ReviewFactory(tags=["goodbye world"])

    resp = client.post(
        "http://main.test/api/tags/rename/",
        json={"old": "goodbye world", "new": "brave new world"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert resp.get_json() == {"message": "Tag updated."}
    assert conflict in a._tags
    assert conflict in r._tags

    db.session.delete(a)
    db.session.delete(r)
    db.session.commit()
