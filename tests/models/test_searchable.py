import pytest
import shutil
from lemonade_soapbox.models import Article, Searchable
from tests.factories import ArticleFactory

pytestmark = pytest.mark.usefixtures("db")


@pytest.fixture
def clear_index(app):
    shutil.rmtree(app.config["INDEX_PATH"])
    app.config["INDEX_PATH"].mkdir()
    yield app.config["INDEX_PATH"]
    shutil.rmtree(app.config["INDEX_PATH"])
    app.config["INDEX_PATH"].mkdir()


def test__after_flush(app, clear_index, db):
    a = ArticleFactory.build()
    db.session.add(a)
    app.testing = False
    db.session.flush()
    assert any(app.config["INDEX_PATH"].iterdir())
    db.session.delete(a)
    db.session.flush()
    app.testing = True


def test_build_index(app, clear_index):
    # Test indexing by seeing if directory is non-empty
    assert not any(app.config["INDEX_PATH"].iterdir())
    ArticleFactory.create_batch(10)
    Article.build_index(per_pass=5)
    assert any(app.config["INDEX_PATH"].iterdir())

    # Remove index dir
    shutil.rmtree(app.config["INDEX_PATH"])
    with pytest.raises(Exception):
        Article.build_index()
    app.config["INDEX_PATH"].mkdir()


def test_schema_filters_not_implemented():
    with pytest.raises(NotImplementedError):
        Searchable().schema_filters()


def test_search(clear_index):
    ArticleFactory(title="Test article")
    ArticleFactory(title="Not a test")
    ArticleFactory(title="Hello world")
    Article.build_index()
    results = Article.search(query="test", sort_order="asc", sort_field="title")
    assert results["total"] == 2


def test_search_error():
    with pytest.raises(Exception):
        Article.search(query="test", sort_order="asc", sort_field="title")
