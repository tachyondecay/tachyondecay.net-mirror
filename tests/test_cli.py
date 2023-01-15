import pytest

from tests.factories import ArticleFactory

pytestmark = pytest.mark.usefixtures("db", "app_ctx")


def test_reindex(app, db):
    runner = app.test_cli_runner()
    ArticleFactory.create_batch(5)
    db.session.flush()

    result = runner.invoke(args=["reindex", "Article", "--per-pass=2"])
    assert "Indexing complete." in result.output

    result = runner.invoke(args=["reindex", "NotAModel"])
    assert "Invalid model name." in result.output

    result = runner.invoke(args=["reindex", "User"])
    assert "Model is not Searchable." in result.output
