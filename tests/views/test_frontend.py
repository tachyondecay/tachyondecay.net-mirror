import pytest
from tests.factories import ArticleFactory

pytestmark = pytest.mark.usefixtures("db")


def test_about(client):
    resp = client.get("http://main.test/about/")
    assert resp.status_code == 200
    assert b"About Me" in resp.data


def test_error404(client):
    resp = client.get("http://main.test/oops")
    assert resp.status_code == 404


def test_index(client):
    """Site index should show 5 most recent articles."""
    articles = ArticleFactory.create_batch(5)
    resp = client.get("http://main.test/")
    assert resp.status_code == 200
    for article in articles:
        assert article.title.encode("utf-8") in resp.data
