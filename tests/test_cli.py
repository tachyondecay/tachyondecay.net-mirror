from tests.factories import ArticleFactory


def test_reindex(app):
    runner = app.test_cli_runner()
    ArticleFactory.create_batch(5)

    result = runner.invoke(args=["reindex", "Article"])
    assert "Indexing complete." in result.output

    result = runner.invoke(args=["reindex", "NotAModel"])
    assert "Invalid model name." in result.output

    result = runner.invoke(args=["reindex", "User"])
    assert "Model is not Searchable." in result.output
