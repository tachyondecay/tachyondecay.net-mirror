import shutil

import pytest

from flask_login import FlaskLoginClient
from itsdangerous import URLSafeTimedSerializer

from lemonade_soapbox import db as _db
from lemonade_soapbox.create_app import create_app
from lemonade_soapbox.models import User


@pytest.fixture
def app(monkeypatch):
    """Set up an instance of the app for use during the test."""
    monkeypatch.setenv("MAIN_HOST", "main.test")
    monkeypatch.setenv("REVIEW_HOST", "reviews.test")
    _app = create_app("testing")
    _app.config["TESTING"] = True
    _app.test_client_class = FlaskLoginClient
    yield _app

    for directory in [
        _app.config["INDEX_PATH"],
        _app.instance_path / "logs",
        _app.instance_path / "media",
    ]:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def app_ctx(app):
    with app.app_context():
        yield


@pytest.fixture
def db(app):
    """
    This allows for automatic cleanup of temporary db objects we don't
    want to persist across tests.
    """
    with app.app_context():
        _db.create_all()

    yield _db

    with app.app_context():
        _db.drop_all()


@pytest.fixture
def user(app, db):
    _user = User(
        email="test@example.com",
        name="Kara Babcock",
        password="testing",
        url="https://tachyondecay.net/",
    )
    with app.app_context():
        db.session.add(_user)
        db.session.commit()
        db.session.refresh(_user)
    yield _user


@pytest.fixture
def client(app):
    yield app.test_client()


@pytest.fixture
def client_authed(app, db, user):
    yield app.test_client(user=user)


@pytest.fixture
def client_authed_reviews(app, db, user):
    """Required to emulate being logged into the reviews site."""
    gateway = URLSafeTimedSerializer(app.secret_key)
    token = gateway.dumps(user.id)
    c = app.test_client(user=user)
    c.get(f"http://reviews.test/auth/?token={token}")
    yield c
