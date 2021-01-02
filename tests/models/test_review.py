import arrow
import pytest
from tests.factories import ReviewFactory

pytestmark = pytest.mark.usefixtures("app", "db")


def test_dates_read():
    r = ReviewFactory(
        date_started=arrow.get("2010-05-05"), date_finished=arrow.get("2010-05-08")
    )

    # Test getter
    assert r.dates_read == "2010-05-05 - 2010-05-08"

    # Test setter: valid input
    r.dates_read = "2010/05/08 - 2010/05/10"
    assert r.date_started == arrow.get("2010-05-08")
    assert r.date_finished == arrow.get("2010-05-10")

    # Test setter: invalid input
    with pytest.raises(Exception):
        r.dates_read = "2010/05/08 - 2010/04/08"


def test_short_title():
    r = ReviewFactory(title="Hello World: A Test Review")
    assert r.short_title == "Hello World"
