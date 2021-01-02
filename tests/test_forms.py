import arrow
from lemonade_soapbox.forms import (
    ButtonWidget,
    DateTimeLocalField,
    Form,
    ModelForm,
    ReviewForm,
    TagListField,
)
from werkzeug.datastructures import MultiDict
from wtforms import SubmitField


def test_model_form(db):
    assert db.session == ModelForm.get_session()


def test_button_widget(app):
    """Test the ButtonWidget."""

    class TestForm(Form):
        button = SubmitField("Submit", widget=ButtonWidget())

    form = TestForm()
    button1 = form.button(icon_before="test")
    button2 = form.button(icon_after="test")
    assert '<span class="i--test"></span>Submit' in button1
    assert 'Submit<span class="i--test"></span>' in button2


def test_datetime_local_field(app):
    """Test my custom datetime field."""

    class TestForm(Form):
        datetime = DateTimeLocalField("Date and Time")

    # Valid input
    form = TestForm(
        formdata=MultiDict([("datetime", "2020-12-30"), ("datetime", "18:43")])
    )
    assert form.datetime.data == arrow.get("2020-12-30 18:43").replace(
        tzinfo=app.config["TIMEZONE"]
    ).to("UTC")

    # Invalid input
    form = TestForm(
        formdata=MultiDict([("datetime", "2020-12-30"), ("datetime", "invalid string")])
    )
    assert not form.datetime.data


def test_taglist_field(app):
    """Test the TagListField."""

    class TestForm(Form):
        tags = TagListField("Tags")

    # No data supplied
    form = TestForm()
    assert 'value=""' in form.tags()

    # Data supplied
    form = TestForm(data={"tags": ["tag1", "tag2"]})
    assert 'value="tag1, tag2"' in form.tags()

    # Process incoming data
    form = TestForm(formdata=MultiDict([("tags", "tag1,    tag2,tag3")]))
    assert form.tags.data == ["tag1", "tag2", "tag3"]


def test_validate_dates_read(app):
    # Trigger exception when date finished is before date started

    data = {
        "body": "Test body",
        "book_author": "Nobody",
        "dates_read": "2010/05/10 - 2010/04/10",
        "title": "This is the title",
    }
    form = ReviewForm(data=data)
    form.validate()
    assert "Dates read must be a valid range." in form.dates_read.errors
