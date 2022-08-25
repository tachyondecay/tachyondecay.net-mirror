import arrow
import pytest
from lemonade_soapbox.models import Tag
from tests.factories import ArticleFactory

pytestmark = pytest.mark.usefixtures("db")


def test_all_tags(client, db):
    ArticleFactory(tags=["test", "hello world"])
    db.session.flush()  # Avoids autoflush error because "hello world" tag isn't created yet
    ArticleFactory(tags=["hello world"])
    resp = client.get("http://main.test/blog/tags/")
    assert resp.status_code == 200
    print(resp.data)
    assert b"/blog/tags/hello-world/" in resp.data
    assert b"/blog/tags/test/" in resp.data
    assert b"hello world" in resp.data


def test_default_feed(app, client):
    """Hitting /blog/feed/ should redirect to the default feed format."""
    resp = client.get("http://main.test/blog/feed/")
    assert resp.status_code == 302
    assert resp.location == f"/blog/feed/posts.{app.config['DEFAULT_FEED_FORMAT']}"


def test_error404(client):
    resp = client.get("http://main.test/blog/oops")
    assert resp.status_code == 404


def test_index(client):
    """Blog index should show 10 most recent articles."""
    articles = ArticleFactory.create_batch(10)
    resp = client.get("http://main.test/blog/")
    assert resp.status_code == 200
    assert all(a.title.encode() in resp.data for a in articles)


def test_month_archive(client):
    # Non-existent months should 404
    resp = client.get("http://main.test/blog/2005/20/")
    assert resp.status_code == 404

    # Months with no articles should 404
    resp = client.get("http://main.test/blog/2005/10/")
    assert resp.status_code == 404

    # Month with article should display that article
    article = ArticleFactory()
    year, month = [article.date_published.year, article.date_published.month]
    print(year, month)
    url = f"http://main.test/blog/{year}/{month}/"
    print(url)
    resp = client.get(url)
    assert resp.status_code == 200
    assert article.title.encode() in resp.data


def test_show_draft(client_authed, user):
    # If draft doesn't exist, 404
    resp = client_authed.get("http://main.test/blog/drafts/oops/")
    assert resp.status_code == 404

    draft = ArticleFactory(status="draft")
    resp = client_authed.get(f"http://main.test/blog/drafts/{draft.handle}/")
    assert resp.status_code == 200
    assert draft.title.encode() in resp.data


def test_show_feed(client, user):
    """Test the generation of Atom and RSS feeds."""
    articles = ArticleFactory.create_batch(5)
    for format in ["atom", "rss"]:
        resp = client.get(f"http://main.test/blog/feed/posts.{format}")
        assert resp.status_code == 200
        assert resp.mimetype == f"application/{format}+xml"
        assert all(a.title.encode() in resp.data for a in articles)


def test_show_tag(client, db):
    # Create a test tag
    tag = Tag(label="hello world")
    db.session.add(tag)
    db.session.flush()

    # Create 5 articles with that tag
    articles = ArticleFactory.create_batch(5, tags=["hello world"])
    resp = client.get("http://main.test/blog/tags/hello-world/")
    assert resp.status_code == 200
    assert all(a.title.encode() in resp.data for a in articles)


def test_show_trash(client_authed, user):
    # If deleted article doesn't exis, 404
    resp = client_authed.get("http://main.test/blog/trash/oops/")
    assert resp.status_code == 404

    trashed = ArticleFactory(status="deleted")
    resp = client_authed.get(f"http://main.test/blog/trash/{trashed.handle}/")
    assert resp.status_code == 200
    assert trashed.title.encode() in resp.data


def test_single_article(client, user):
    # Non-existent handle should 404
    resp = client.get("http://main.test/blog/2005/05/hello-world/")
    assert resp.status_code == 404

    # Existent article should be displayed
    article = ArticleFactory()
    year, month = [article.date_published.year, article.date_published.month]
    resp = client.get(f"http://main.test/blog/{year}/{month}/{article.handle}/")
    assert resp.status_code == 200
    assert article.title.encode() in resp.data

    # Article should *not* be displayed if year/month don't match
    resp = client.get(f"http://main.test/blog/2000/01/{article.handle}/")
    assert resp.status_code == 404

    # Article in the future should only be displayed if logged in
    pubdate = arrow.utcnow().shift(weeks=+1)
    future_article = ArticleFactory(date_published=pubdate)
    year, month = [
        future_article.date_published.year,
        future_article.date_published.month,
    ]
    url = f"http://main.test/blog/{year}/{month}/{future_article.handle}/"
    resp = client.get(url)
    assert resp.status_code == 404

    client.post(
        "http://main.test/meta/signin/",
        data={"email": "test@example.com", "password": "testing"},
        follow_redirects=True,
    )
    resp = client.get(url)
    assert resp.status_code == 200


def test_year_archive(client):
    # Non-existent years or years with no articles should 404
    resp = client.get("http://main.test/blog/2999/")
    assert resp.status_code == 404

    article = ArticleFactory()
    print(f"Hmm {article.author.id}")
    # assert False
    year = article.date_published.year
    resp = client.get(f"http://main.test/blog/{year}/")
    assert resp.status_code == 200
    assert article.title.encode() in resp.data
