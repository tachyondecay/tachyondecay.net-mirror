import arrow
from flask import current_app
from flask_wtf import Form
from lemonade_soapbox import db
from lemonade_soapbox.models import Article
from wtforms import (
    DateTimeField,
    StringField,
    SubmitField,
    validators
)
from wtforms.fields.html5 import EmailField
from wtforms.widgets import HTMLString, html_params
from wtforms_alchemy import model_form_factory

BaseModelForm = model_form_factory(Form)


class ModelForm(BaseModelForm):
    @classmethod
    def get_session(self):
        return db.session


class ButtonWidget:
    """Widget for SubmitFields that uses the button element instead."""
    def __call__(self, field, **kwargs):
        button_params = html_params(class_=kwargs.get('class'),
                                    name=kwargs.get('name', field.name))
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
        date_params = html_params(name=field.name, id=id + '-date', value=date, **kwargs)
        time_params = html_params(name=field.name, id=id + '-time', step='1', value=time, **kwargs)
        return HTMLString('<span class="{}"><input type="date" {}/></span><span class="{}"><input type="time" {}/></span>'.format(date_class, date_params, time_class, time_params))


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
                self.data = arrow.get(date_str).replace(tzinfo=current_app.config['TIMEZONE']).to('UTC')
            except arrow.parser.ParserError as e:
                current_app.logger.warn('Invalid datetime value submitted: %s', e)
                raise ValueError('Not a valid datetime value. Looking for YYYY-MM-DD HH:mm.')


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
    date_published = DateTimeLocalField('Published',
                                        format='%Y-%M-%D %H:%m',
                                        validators=[validators.Optional()])
    tags = TagListField('Tags')
    publish = SubmitField('Publish', widget=ButtonWidget())
    save = SubmitField('Save', widget=ButtonWidget())
    delete = SubmitField('Delete', widget=ButtonWidget())
    drafts = SubmitField('Unpublish', widget=ButtonWidget())


class SignInForm(Form):
    email = EmailField('Email address', validators=[validators.Email()])
