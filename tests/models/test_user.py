import pytest

pytestmark = pytest.mark.usefixtures("app")


def test_email_hash(user):
    assert user.email_hash == "55502f40dc8b7c769880b10874abc9d0"


def test_first_name(user):
    assert user.first_name == "Kara"


def test_last_name(user):
    assert user.last_name == "Babcock"
