import pytest

from lemonade_soapbox.models import Tag
from tests.factories import ArticleFactory, ReviewFactory

pytestmark = pytest.mark.usefixtures("app", "db")


@pytest.fixture
def populate_tags(db):
    ArticleFactory(tags=["rose", "petunia"])
    db.session.flush()
    ArticleFactory(tags=["rose"])
    ReviewFactory(tags=["petunia"])
    db.session.flush()
    ReviewFactory(tags=["oak"])
    db.session.flush()
    yield
    db.session.remove()


def test_tag_frequency(populate_tags):
    """Check that frequencies are correct for a given situation of tags."""
    frequencies = {
        "oak": (0, 1),
        "petunia": (1, 1),
        "rose": (2, 0),
    }
    freq_list = Tag.frequency().all()
    assert all(label in [r.Tag.label for r in freq_list] for label in frequencies)
    for r in freq_list:
        f = frequencies[r.Tag.label]
        assert r.article_count == f[0]
        assert r.review_count == f[1]


def test_tag_frequency_matching(populate_tags):
    """Test searching for the frequency of a specific tag yields 1 result."""
    freq_list = Tag.frequency(match="petu").all()
    assert len(freq_list) == 1


def test_tag_frequency_sort_order(populate_tags):
    """Test sorting on the article_count of a tag frequency query."""
    freq_list = Tag.frequency(sort_by="article_count", order_desc=True)
    expected_label_order = ["rose", "petunia", "oak"]
    assert expected_label_order == [r.Tag.label for r in freq_list]


def test_tag_frequency_status(populate_tags):
    """Test filtering on the status of a post for the tag frequency query."""
    freq_list = Tag.frequency(status=['draft']).all()
    assert all(t.article_count == 0 for t in freq_list)
    assert all(t.review_count == 0 for t in freq_list)
