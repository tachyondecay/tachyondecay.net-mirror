import arrow
import pytest
from lemonade_soapbox.models import Article
from tests.factories import ArticleFactory

pytestmark = pytest.mark.usefixtures("db", "app_ctx")


def test_format():
    a = ArticleFactory()
    assert a.format("<strong>test</strong>") == "<p><strong>test</strong></p>"
    assert (
        a.format("<strong>test</strong>", True)
        == "<p>&lt;strong&gt;test&lt;/strong&gt;</p>"
    )


def test_post_breakdown():
    ArticleFactory(date_published=arrow.get("2019-01-10"))
    ArticleFactory(date_published=arrow.get("2020-02-20"))
    ArticleFactory(date_published=arrow.get("2020-03-22"))
    assert Article.post_breakdown() == {2019: {1: 1}, 2020: {2: 1, 3: 1}}


def test_unique_handle(db):
    ArticleFactory(title="test")
    db.session.flush()
    a = ArticleFactory(title="test")
    assert a.handle == "test-1"
