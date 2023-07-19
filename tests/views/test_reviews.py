import re

import arrow
import pytest

from lemonade_soapbox.models import Review, Tag
from tests.factories import ReviewFactory

pytestmark = pytest.mark.usefixtures("db", "app_ctx")


def test_about(client):
    resp = client.get("http://reviews.test/about/")
    assert resp.status_code == 200
    assert b"About This Site" in resp.data


def test_all_reviews(client):
    reviews = ReviewFactory.create_batch(5)
    resp = client.get("http://reviews.test/index/")
    assert resp.status_code == 200
    assert all(r.short_title.encode() in resp.data for r in reviews)


def test_all_tags(client, db):
    ReviewFactory(tags=["test", "hello world"])
    db.session.flush()  # Avoids autoflush error because "hello world" tag isn't created yet
    ReviewFactory(tags=["hello world"])
    resp = client.get("http://reviews.test/shelves/")
    assert resp.status_code == 200
    assert b"/shelves/hello-world/" in resp.data
    assert b"/shelves/test/" in resp.data
    assert b"1 books shelved" in resp.data
    assert b"2 books shelved" in resp.data


def test_index(client, db):
    tag = Tag(label="non-fiction")
    db.session.add(tag)
    db.session.flush()
    reviews = ReviewFactory.create_batch(
        3, tags=["non-fiction"]
    ) + ReviewFactory.create_batch(3)
    resp = client.get("http://reviews.test/")
    assert resp.status_code == 200
    assert all(r.short_title.encode() in resp.data for r in reviews)


def test_lists(client):
    resp = client.get("http://reviews.test/lists/")
    assert resp.status_code == 200
    assert b"The lists feature is under construction" in resp.data


def test_random_review(client):
    r = ReviewFactory()
    resp = client.get("http://reviews.test/random/")
    assert resp.status_code == 302
    assert resp.location == f"http://reviews.test/{r.handle}/"


def test_search(client, db):
    ReviewFactory(title="Empire of Wild", book_author="Cherie Dimaline")
    ReviewFactory(
        title="Mediocre: The Dangerous Legacy of White Male America",
        book_author="Ijeoma Oluo",
    )
    ReviewFactory(title="The Project", book_author="Courtney Summers")
    for i in range(0, 52):
        ReviewFactory(title="After the Silence")
        db.session.flush()

    Review.build_index()  # Automatic indexing is disabled during testing

    # Test searching by title
    resp = client.get("http://reviews.test/search/?q=mediocre")
    assert b"1 review found" in resp.data

    # Test searching by author
    resp = client.get("http://reviews.test/search/?q=book_author%3Asummers")
    assert b"1 review found" in resp.data

    # Test no results
    resp = client.get("http://reviews.test/search/?q=blue")
    assert b"No reviews found" in resp.data

    # Test pagination
    resp = client.get("http://reviews.test/search/?q=after+silence&page=2")
    assert b"52 reviews found" in resp.data
    assert b"pagination-links" in resp.data


def test_show_feed(client):
    """Test the generation of Atom and RSS feeds."""
    reviews = ReviewFactory.create_batch(5)
    for format in ["atom", "rss"]:
        resp = client.get(f"http://reviews.test/feed/posts.{format}")
        assert resp.status_code == 200
        assert resp.mimetype == f"application/{format}+xml"
        assert all(r.short_title.upper().encode() in resp.data for r in reviews)


def test_show_review_unauthenticated(client):
    review = ReviewFactory(status="draft")
    url = f"http://reviews.test/{review.handle}/"

    # Drafts and scheduled reviews should 404 if not authenticated
    resp = client.get(url)
    assert resp.status_code == 404

    review.status = "published"
    review.date_published = arrow.utcnow().shift(weeks=+1)
    resp = client.get(url)
    assert resp.status_code == 404


def test_show_review_authenticated(client_authed_reviews):
    review = ReviewFactory(status="draft")
    url = f"http://reviews.test/{review.handle}/"

    resp = client_authed_reviews.get(url)
    assert resp.status_code == 200
    assert review.title.encode() in resp.data

    review.status = "published"
    review.date_published = arrow.utcnow().shift(weeks=+1)
    resp = client_authed_reviews.get(url)
    assert resp.status_code == 200
    assert review.title.encode() in resp.data


def test_show_review(client, db):
    review_body = "This is a fake review body.<cite>The Midnight Library</cite>"
    review = ReviewFactory(
        book_author="Charles Stross", body=review_body, tags=["science fiction"]
    )
    db.session.flush()
    ReviewFactory(
        book_author="Charles Stross", title="Empire Games", tags=["science fiction"]
    )
    ReviewFactory(title="The Midnight Library")
    ReviewFactory(title="Stars Beyond", tags=["science fiction"])

    resp = client.get(f"http://reviews.test/{review.handle}/")
    assert resp.status_code == 200
    assert review.title.encode() in resp.data
    assert b"The Midnight Library" in resp.data  # Mentioned in This Review
    assert b"Stars Beyond" in resp.data  # Reviews related by shelf

    # Make sure no review appears more than once in related reviews
    assert len(re.findall(r'title="Empire Games', resp.data.decode())) == 1


def test_show_tag(client, db):
    # Create a test tag
    tag = Tag(label="science fiction")
    db.session.add(tag)
    db.session.flush()

    # Create 5 articles with that tag
    reviews = ReviewFactory.create_batch(5, tags=["science fiction"])

    # Test regular shelf view
    resp = client.get("http://reviews.test/shelves/science-fiction/")
    assert resp.status_code == 200

    # Check if all reviews are present
    assert all(r.short_title.encode() in resp.data for r in reviews)

    # Test shelf feed view
    for format in ["atom", "rss"]:
        resp = client.get(f"http://reviews.test/shelves/science-fiction/posts.{format}")
        assert resp.status_code == 200
        assert resp.mimetype == f"application/{format}+xml"
        assert all(r.short_title.upper().encode() in resp.data for r in reviews)
