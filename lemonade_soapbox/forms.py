import arrow
from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from intervals import DateInterval
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, Review
from werkzeug.utils import secure_filename
from wtforms import (
    BooleanField,
    DateTimeField,
    HiddenField,
    IntegerField,
    RadioField,
    StringField,
    SubmitField,
    validators,
)
from wtforms.fields.html5 import EmailField
from wtforms.widgets import HTMLString, html_params, TextInput
from wtforms_alchemy import model_form_factory

Form = FlaskForm
BaseModelForm = model_form_factory(Form)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ButtonWidget:
    """Widget for SubmitFields that uses the button element instead."""

    def __call__(self, field, **kwargs):
        button_params = html_params(
            class_=kwargs.get('class'), name=kwargs.get('name', field.name)
        )
        html = '<button type="submit" value="true" {}>'.format(button_params)
        if 'icon_before' in kwargs:
            html += '<span class="i--{}"></span> '.format(kwargs['icon_before'])
        html += kwargs.get('label', field.label.text)
        if 'icon_after' in kwargs:
            html += ' <span class="i--{}"></span>'.format(kwargs['icon_after'])
        html += '</button>'
        return HTMLString(html)


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
        return HTMLString(
            '<span class="{}"><input type="date" {}/></span><span class="{}"><input type="time" {}/></span>'.format(
                date_class, date_params, time_class, time_params
            )
        )


class DateTimeLocalField(DateTimeField):
    """
    DateTimeField that assumes input is in app-configured timezone and converts
    to UTC for further processing/storage.
    """

    widget = DateTimeWidget()

    def process_formdata(self, valuelist):
        current_app.logger.debug(valuelist)
        if valuelist:
            date_str = ' '.join(valuelist)
            try:
                self.data = (
                    arrow.get(date_str)
                    .replace(tzinfo=current_app.config['TIMEZONE'])
                    .to('UTC')
                )
            except arrow.parser.ParserError as e:
                current_app.logger.warn('Invalid datetime value submitted: %s', e)
                raise ValueError(
                    'Not a valid datetime value. Looking for YYYY-MM-DD HH:mm.'
                )


# Note: This class is currently unused because DateRangeType from sqlalchemy-utils
# is not working as expected.
class DateRangeField(StringField):
    """Field for date ranges"""

    def _value(self):
        if self.data:
            start, end = [
                arrow.get(k).format('YYYY/MM/DD')
                for k in [self.data.lower, self.data.upper]
            ]
            return f'{start} - {end}'
        return ''

    def process_formdata(self, valuelist):
        if valuelist:
            start, end = [arrow.get(x.strip()) for x in valuelist[0].split('-')]
            self.data = DateInterval.closed(start.date(), end.date())
        else:
            self.data = ''


class TagListField(StringField):
    """
    A text input field that processes input as if it were a comma-separated
    list of tags.
    """

    def _value(self):
        """Turn the list into a comma-separated string in alphabetical order."""
        if self.data:
            return u', '.join(sorted(self.data, key=lambda s: s.lower()))
        else:
            return u''

    def process_data(self, value):
        """Form data should only have the actual tags, not the handles."""
        if value:
            self.data = value
        else:
            self.data = ''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = [x.strip() for x in valuelist[0].split(',')]
        else:
            self.data = []


class ArticleForm(ModelForm):
    class Meta:
        model = Article
        only = ['body', 'date_published', 'show_updated', 'title', 'summary', 'handle']

    date_published = DateTimeLocalField(
        'Published', format='%Y-%M-%D %H:%m', validators=[validators.Optional()]
    )
    tags = TagListField('Tags')
    publish = SubmitField('Publish', widget=ButtonWidget())
    save = SubmitField('Save', widget=ButtonWidget())
    delete = SubmitField('Delete', widget=ButtonWidget())
    drafts = SubmitField('Unpublish', widget=ButtonWidget())


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
            'title',
            'book_id',
            'goodreads_id',
            'book_cover',
            'dates_read',
            'rating',
            'spoilers',
        ]

    date_published = DateTimeLocalField(
        'Published', format='%Y-%M-%D %H:%m', validators=[validators.Optional()]
    )
    goodreads_id = IntegerField(widget=TextInput(), validators=[validators.Optional()])
    book_cover = FileField(
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
    save = SubmitField('Save', widget=ButtonWidget())
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
