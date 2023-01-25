import base64
import io
import random
import shutil

import arrow
import pytest
from flask_login import current_user
from sqlalchemy.orm.util import was_deleted

from lemonade_soapbox.models.posts import Article, List, Review, RevisionMixin
from tests.factories import ArticleFactory, ListFactory, ReviewFactory, TagFactory

pytestmark = pytest.mark.usefixtures("db")
post_types = {
    Article: "blog",
    List: "lists",
    Review: "reviews",
}


@pytest.fixture(params=[ArticleFactory, ListFactory, ReviewFactory])
def post(app_ctx, db, request, client_authed):
    """For testing various cases with the edit_post endpoint."""
    # Create the post and generate a new revision
    _post = request.param(title="Hello World", body="Test post here")

    # Create a new revision if the post type supports this
    if issubclass(request.param._meta.model, RevisionMixin):
        old_body = _post.body
        _post.body = "This is a replacement body text."
        _post.new_revision(old_body)

    # This is required to make sure the Revision objects work properly
    db.session.add(_post)
    db.session.flush()
    db.session.refresh(_post)

    yield _post

    # db.session.rollback()


@pytest.fixture
def cover_dir(app, post):
    """Creates a temporary directory for covers."""

    _cover_dir = app.instance_path / "media" / post.post_type / "covers"
    _cover_dir.mkdir(parents=True)
    yield _cover_dir
    shutil.rmtree(_cover_dir)


def test_protected_routes(client):
    """Almost all routes in the admin blueprint are login-protected."""
    routes = [
        "/",
        "/signout/",
        "/tags/",
        "/blog/",
        "/blog/write/",
        "/lists/",
        "/lists/write/",
        "/reviews/",
        "/reviews/write/",
    ]
    for route in routes:
        resp = client.get(f"http://main.test/meta{route}")
        assert resp.status_code == 302
        assert resp.location.startswith("/meta/signin/")


@pytest.mark.parametrize(
    "factory",
    [ArticleFactory, ReviewFactory],
)
def test_posts_index(app_ctx, client_authed, db, factory):
    """Test the /meta/blog/ and /meta/reviews/ views."""
    posts = factory.create_batch(5)

    posts.sort(key=lambda a: a.date_published, reverse=True)
    post_type = post_types[posts[0].__class__]

    # Test pagination and default sort/filter parameters
    resp = client_authed.get(f"http://main.test/meta/{post_type}/?page=2&per_page=4")
    assert posts[-1].title.encode() in resp.data
    assert all(a.title.encode() not in resp.data for a in posts[:-1])

    # Test ascending order
    posts.sort(key=lambda a: a.date_published)
    resp = client_authed.get(
        f"http://main.test/meta/{post_type}/?page=2&per_page=4&order=asc"
    )
    assert posts[-1].title.encode() in resp.data
    assert all(a.title.encode() not in resp.data for a in posts[:-1])

    # Test search
    resp = client_authed.get(
        f'http://main.test/meta/{post_type}/?q=title:"{posts[0].title}"'
    )
    assert posts[0].title.encode() in resp.data
    assert all(a.title.encode() not in resp.data for a in posts[1:-1])


def test_edit_post_type_not_specified(client_authed):
    resp = client_authed.get("http://main.test/meta/oops/write/")
    assert resp.status_code == 404


@pytest.mark.parametrize("post_class", [Article, List, Review])
def test_edit_post_new(app, client_authed, db, post_class):
    """Test that starting a brand new article works as expectd."""
    post_type = post_types[post_class]
    resp = client_authed.get(f"http://main.test/meta/{post_type}/write/")
    assert resp.status_code == 200

    resp = client_authed.post(
        f"http://main.test/meta/{post_type}/write/",
        data={
            "body": "A new beginning.",
            "book_author": "Nobody",
            "dates_read": "2010/05/08 - 2010/05/09",
            "owner": "kara.reviews",
            "publish": "yes",
            "title": "A Fresh Article",
        },
    )
    assert resp.status_code == 302

    with app.app_context():
        post = post_class.query.filter_by(title="A Fresh Article").first()
        assert post is not None
    # db.session.delete(post)
    # db.session.commit()


def test_edit_post_fetch_by_id(client_authed, post):
    """Test displaying a post to edit by ID."""
    post_type = post_types[post.__class__]
    resp = client_authed.get(f"http://main.test/meta/{post_type}/write/{post.id}/")
    assert resp.status_code == 200
    assert any(
        phrase in resp.data.decode()
        for phrase in ["Editing “Hello World”", "Editing review of"]
    )
    assert post.body in resp.data.decode()


def test_edit_post_fetch_by_revision(client_authed, post):
    """Fetch by old revision ID and check that the old body is present."""
    if not issubclass(post.__class__, RevisionMixin):
        return
    post_type = post_types[post.__class__]
    old_revision = post.revisions[0].id
    resp = client_authed.get(f"http://main.test/meta/{post_type}/write/{old_revision}/")
    assert resp.status_code == 200
    assert b"Test post here" in resp.data

    # Invalid revision ID
    resp = client_authed.get(f"http://main.test/meta/{post_type}/write/invalid/")
    assert resp.status_code == 404


def test_edit_post_errors(client_authed, post):
    """Test editing an post with no errors."""
    data = {}

    # Submit form with no errors
    resp = client_authed.post(
        f"http://main.test/meta/{post_types[post.__class__]}/write/{post.id}/",
        data=data,
    )
    assert resp.status_code == 200
    assert (
        b"You need to fix a few things before you can save your changes." in resp.data
    )


def test_edit_post_no_errors(client_authed, post):
    """Test editing a post with no errors."""
    data = {
        "body": "Edited body text",
        "book_author": "Nobody",
        "dates_read": "2010/05/08 - 2010/05/09",
        "title": post.title,
    }

    # Submit form with no errors
    resp = client_authed.post(
        f"http://main.test/meta/{post_types[post.__class__]}/write/{post.id}/",
        data=data,
    )
    assert resp.status_code == 302
    assert post.body == "Edited body text"


def test_edit_post_upload_cover(client_authed, db, post, cover_dir):
    """Test uploading a cover."""
    data = {
        "body": "Edited body text",
        "book_author": "Nobody",
        "cover": (io.BytesIO(b"hey"), "test.jpg"),
        "dates_read": "2010/05/08 - 2010/05/09",
        "title": post.title,
    }

    post_type = post_types[post.__class__]
    data["cover"] = (
        io.BytesIO(
            base64.b64decode(
                b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            )
        ),
        "test1.png",
    )
    resp = client_authed.post(
        f"http://main.test/meta/{post_type}/write/{post.id}/",
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    assert post.cover == f"{post.id}-{post.handle}-cover.jpg"

    # Now test an error
    data["cover"] = (
        io.BytesIO(
            base64.b64decode(
                b"VVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            )
        ),
        "test1.png",
    )
    resp = client_authed.post(
        f"http://main.test/meta/{post_type}/write/{post.id}/",
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    db.session.refresh(post)
    assert post.cover == ""


def test_edit_post_remove_cover(app, cover_dir, client_authed, db, post):
    """Test removing a cover."""
    data = {
        "body": "Edited body text",
        "book_author": "Nobody",
        "dates_read": "2010/05/08 - 2010/05/09",
        "remove_cover": "yes",
        "title": post.title,
    }
    post_type = post_types[post.__class__]

    # Create a fake cover image file to be deleted
    open(
        app.instance_path / "media" / post.post_type / "covers" / "hey.jpg", "a"
    ).close()

    resp = client_authed.post(
        f"http://main.test/meta/{post_type}/write/{post.id}/",
        data=data,
    )
    assert resp.status_code == 302
    assert post.cover == ""


def test_edit_post_pasted_cover(client_authed, cover_dir, db, post):
    """Test uploading a cover via pasted image data."""
    data = {
        "body": "Edited body text",
        "book_author": "Nobody",
        "dates_read": "2010/05/08 - 2010/05/09",
        "pasted_cover": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "title": post.title,
    }

    resp = client_authed.post(
        f"http://main.test/meta/{post_types[post.__class__]}/write/{post.id}/",
        data=data,
    )
    assert resp.status_code == 302
    db.session.refresh(post)
    assert post.cover == f"{post.id}-{post.handle}-cover.jpg"


def test_edit_post_delete(client_authed, db, post):
    """Test deleting article."""
    data = {
        "body": "Edited body text",
        "book_author": "Nobody",
        "dates_read": "2010/05/08 - 2010/05/09",
        "delete": "yes",
        "title": post.title,
    }
    post_type = post_types[post.__class__]
    resp = client_authed.post(
        f"http://main.test/meta/{post_type}/write/{post.id}/", data=data
    )
    assert resp.status_code == 302
    # db.session.refresh(post)
    assert post.status == "deleted"

    # Now permanently delete it
    resp = client_authed.post(
        f"http://main.test/meta/{post_type}/write/{post.id}/", data=data
    )
    assert resp.status_code == 302
    assert was_deleted(post)


def test_edit_post_unpublish(client_authed, post):
    """Test unpublishing an article."""
    data = {
        "body": "Edited body text",
        "book_author": "Nobody",
        "dates_read": "2010/05/08 - 2010/05/09",
        "drafts": "yes",
        "title": post.title,
    }
    resp = client_authed.post(
        f"http://main.test/meta/{post_types[post.__class__]}/write/{post.id}/",
        data=data,
    )
    assert resp.status_code == 302
    assert post.status == "draft"


def test_index(app_ctx, db, client_authed):
    ArticleFactory.create_batch(5)
    ReviewFactory.create_batch(6)
    draft = ArticleFactory(status="draft")
    scheduled = ReviewFactory(date_published=arrow.utcnow().shift(weeks=+1).datetime)

    resp = client_authed.get("http://main.test/meta/")
    assert resp.status_code == 200
    assert b"<strong>5</strong>" in resp.data
    assert b"<strong>7</strong>" in resp.data
    assert draft.title.encode() in resp.data
    assert scheduled.short_title.encode() in resp.data


def test_reviews(client_authed):
    # Most of the heavy lifting is done in test_blog
    # So we just want to make sure we hit this for coverage
    resp = client_authed.get("http://main.test/meta/reviews/")
    assert resp.status_code == 200


def test_signin_authed(client_authed):
    resp = client_authed.get("http://main.test/meta/signin/")
    assert resp.status_code == 302
    assert resp.location == "/meta/"


def test_signin_unauthed(client, user):
    url = "http://main.test/meta/signin/"

    # Invalid email address
    resp = client.post(
        url,
        data={"email": "test1@example.com", "password": "1234"},
    )
    assert resp.status_code == 302
    assert resp.location == "/meta/signin/"

    # Valid email address, invalid password
    resp = client.post(
        url,
        data={"email": "test@example.com", "password": "1234"},
    )
    assert resp.status_code == 302
    assert resp.location == "/meta/signin/"

    # Valid email and password
    resp = client.post(
        url,
        data={"email": "test@example.com", "password": "testing"},
    )
    assert resp.status_code == 302
    assert resp.location.startswith("http://reviews.test/")


def test_signout(client_authed, user):
    with client_authed:
        resp = client_authed.get("http://main.test/meta/")
        assert current_user.is_authenticated
        resp = client_authed.get("http://main.test/meta/signout/")
        assert not current_user.is_authenticated
        assert resp.status_code == 302


def test_tag_manager(app_ctx, client_authed, db):
    tags = TagFactory.create_batch(5)

    # Sort tags alphabetically so we know which one will show up
    tags.sort(key=lambda t: t.label)

    # Create 50 articles and reviews with a random selection of tags
    ArticleFactory.create_batch(
        2, tags=[getattr(k, "label") for k in random.choices(tags)]
    )
    ReviewFactory.create_batch(
        2, tags=[getattr(k, "label") for k in random.choices(tags)]
    )

    resp = client_authed.get("http://main.test/meta/tags/?page=2&per_page=4")
    assert resp.status_code == 200

    # Test that our last tag, and only our last tag, is present (pagination)
    assert tags[-1].label.encode() in resp.data
    assert all(t.label.encode() not in resp.data for t in tags[:-1])
