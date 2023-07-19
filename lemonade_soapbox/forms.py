import arrow
from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from markupsafe import Markup
from wtforms import (
    BooleanField,
    DateTimeField,
    EmailField,
    HiddenField,
    IntegerField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    validators,
)
from wtforms.widgets import HiddenInput, html_params, TextInput
from wtforms_alchemy import model_form_factory, ModelFieldList, ModelFormField

from lemonade_soapbox import db
from lemonade_soapbox.models import Article, List, ListItem, Review

Form = FlaskForm
BaseModelForm = model_form_factory(Form)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(cls):
        return db.session


class ButtonWidget:
    """Widget for SubmitFields that uses the button element instead."""

    def __call__(self, field, **kwargs):
        button_params = html_params(
            class_=kwargs.get("class", ""), name=kwargs.get("name", field.name)
        )
        html = f'<button type="submit" value="true" {button_params}>'
        if 'icon_before' in kwargs:
            html += f'<span class="i--{kwargs["icon_before"]}"></span>'
        html += kwargs.get('label', field.label.text)
        if 'icon_after' in kwargs:
            html += f'<span class="i--{kwargs["icon_after"]}"></span>'
        html += '</button>'
        return Markup(html)


class DateTimeWidget:
    """Widget for DateTimeFields using separate date and time inputs."""

    def __call__(self, field, **kwargs):
        id = kwargs.pop('id', field.id)
        date = time = ''
        if field.data:
            dt = arrow.get(field.data).to(current_app.config['TIMEZONE'])
            date = dt.format('YYYY-MM-DD')
            time = dt.format('HH:mm:ss')
        date_class = kwargs.get('date_class', '')
        time_class = kwargs.get('time_class', '')
        date_params = html_params(
            name=field.name, id=id + '-date', value=date, **kwargs
        )
        time_params = html_params(
            name=field.name, id=id + '-time', step='1', value=time, **kwargs
        )
        return Markup(
            f'<span class="{date_class}"><input type="date" {date_params}/></span>'
            f'<span class="{time_class}"><input type="time" {time_params}/></span>'
        )


class DateTimeLocalField(DateTimeField):
    """
    DateTimeField that assumes input is in app-configured timezone and converts
    to UTC for further processing/storage.
    """

    widget = DateTimeWidget()

    def process_formdata(self, valuelist):
        if valuelist:
            date_str = ' '.join(valuelist)
            if date_str.strip():
                try:
                    self.data = (
                        arrow.get(date_str)
                        .replace(tzinfo=current_app.config['TIMEZONE'])
                        .to('UTC')
                    )
                except arrow.parser.ParserError as e:
                    current_app.logger.warning(
                        f'Invalid datetime value submitted: {date_str} - {e}'
                    )


class TagListField(StringField):
    """
    A text input field that processes input as if it were a comma-separated
    list of tags.
    """

    def _value(self):
        """Turn the list into a comma-separated string in alphabetical order."""
        if self.data:
            return ', '.join(sorted(self.data, key=lambda s: s.lower()))
        return ''

    def process_data(self, value):
        """Form data should only have the actual tags, not the handles."""
        if value:
            self.data = value
        else:
            self.data = ''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(',') if x.strip() != '']
        else:
            self.data = []


class ArticleForm(ModelForm):
    class Meta:
        model = Article
        only = [
            'body',
            'cover',
            'date_published',
            'show_updated',
            'title',
            'summary',
            'handle',
        ]

    date_published = DateTimeLocalField(
        'Published', format='%Y-%M-%D %H:%m', validators=[validators.Optional()]
    )
    tags = TagListField('Tags')
    publish = SubmitField('Publish', widget=ButtonWidget())
    update = SubmitField('Save', widget=ButtonWidget())
    delete = SubmitField('Delete', widget=ButtonWidget())
    drafts = SubmitField('Unpublish', widget=ButtonWidget())
    cover = FileField(
        validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif']), validators.Optional()]
    )
    remove_cover = BooleanField(
        'Remove uploaded cover', validators=[validators.Optional()]
    )
    pasted_cover = HiddenField(validators=[validators.Optional()])


class ListItemForm(ModelForm):
    class Meta:
        model = ListItem
        only = [
            "list_id",
            "post_id",
            "position",
            "blurb",
        ]

    list_id = HiddenField()
    post_id = HiddenField()
    position = HiddenField()
    remove = BooleanField(widget=HiddenInput(), validators=[validators.Optional()])


class ListForm(ArticleForm):
    class Meta:
        model = List
        only = [
            'body',
            'cover',
            'date_published',
            'handle',
            'owner',
            'reverse_order',
            'show_numbers',
            'show_updated',
            'summary',
            'title',
        ]

    items = ModelFieldList(ModelFormField(ListItemForm))
    owner = SelectField(
        'Owner', choices=["kara.reviews", "tachyondecay.net"], default="kara.reviews"
    )


def validate_book_author_sort(form, field):
    if not field.data and form.book_author.data:
        fullname = form.book_author.data.split()
        if len(fullname) > 1:
            field.data = fullname[-1] + ', ' + ' '.join(fullname[0:-1])
        else:
            field.data = fullname[0]


class ReviewForm(ModelForm):
    class Meta:
        model = Review
        only = [
            'body',
            'date_published',
            'show_updated',
            'summary',
            'handle',
            'book_author',
            'book_author_sort',
            'title',
            'book_id',
            'goodreads_id',
            'storygraph_id',
            'cover',
            'rating',
            'spoilers',
        ]

    book_author_sort = StringField(
        'Author (Sort by)', validators=[validate_book_author_sort]
    )
    dates_read = StringField('Dates Read')

    date_published = DateTimeLocalField(
        'Published', format='%Y-%M-%D %H:%m', validators=[validators.Optional()]
    )
    book_id = StringField('ISBN', filters=[lambda x: x.strip() if x else None])
    goodreads_id = IntegerField(widget=TextInput(), validators=[validators.Optional()])
    cover = FileField(
        validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif']), validators.Optional()]
    )
    remove_cover = BooleanField(
        'Remove uploaded cover', validators=[validators.Optional()]
    )
    pasted_cover = HiddenField(validators=[validators.Optional()])
    handle = StringField('URL Handle', validators=[validators.Optional()])
    rating = RadioField(
        'Rating',
        choices=[
            (5, '5 out of 5 stars'),
            (4, '4 out of 5 stars'),
            (3, '3 out of 5 stars'),
            (2, '2 out of 5 stars'),
            (1, '1 out of 5 stars'),
            (0, 'No rating'),
        ],
        coerce=int,
        default=0,
        validators=[validators.Optional()],
    )
    tags = TagListField('Shelves')
    publish = SubmitField('Publish', widget=ButtonWidget())
    update = SubmitField('Save', widget=ButtonWidget())
    delete = SubmitField('Delete', widget=ButtonWidget())
    drafts = SubmitField('Unpublish', widget=ButtonWidget())

    def validate_dates_read(form, field):
        """Validate the dates read field is a range of dates"""
        try:
            start, end = [arrow.get(x.strip()) for x in field.data.split('-')]
            if end < start:
                raise Exception
        except Exception:
            raise validators.ValidationError('Dates read must be a valid range.')


class SignInForm(Form):
    email = EmailField(
        'Email address', validators=[validators.InputRequired(), validators.Email()]
    )
    password = PasswordField('Password', validators=[validators.InputRequired()])
