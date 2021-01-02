import pytest
import shutil

from lemonade_soapbox import db as _db
from lemonade_soapbox.create_app import create_app
from lemonade_soapbox.models import User
from pathlib import Path


@pytest.fixture(scope="session")
def monkeypatch_session(request):
    """Experimental (https://github.com/pytest-dev/pytest/issues/363)."""
    from _pytest.monkeypatch import MonkeyPatch

    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope="session")
def app(monkeypatch_session):
    """Set up an instance of the app for use during this testing session."""
    monkeypatch_session.setenv("MAIN_HOST", "main.test")
    monkeypatch_session.setenv("REVIEW_HOST", "reviews.test")
    app = create_app("testing")
    app.config["TESTING"] = True
    with app.app_context():
        _db.create_all()

        yield app

        for dir in [app.config["INDEX_PATH"], app.instance_path / "logs"]:
            shutil.rmtree(dir)
        _db.drop_all()


@pytest.fixture
def client(app):
    yield app.test_client()


@pytest.fixture
def db():
    """
    This allows for automatic cleanup of temporary db objects we don't
    want to persist across tests.
    """
    yield _db
    _db.session.remove()


@pytest.fixture(scope="module")
def user():
    """Create a user object that persists for the entire module of tests."""
    user = User(
        email="test@example.com",
        name="Kara Babcock",
        password="testing",
        url="https://tachyondecay.net/",
    )
    _db.session.add(user)
    _db.session.commit()
    yield user
    _db.session.delete(user)
    _db.session.commit()


@pytest.fixture
def signin(client, user):
    """Authenticate the user for views that are decorated with @login_required."""
    return client.post(
        "http://main.test/meta/signin/",
        data={"email": "test@example.com", "password": "testing"},
        follow_redirects=True,
    )
