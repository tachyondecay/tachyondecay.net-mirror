import arrow
import re
import time
from bs4 import BeautifulSoup
from decimal import Decimal
from flask import current_app, Markup, render_template
from flask_mail import Message
from flask.json import JSONEncoder as BaseJSONEncoder
from fractions import Fraction
from html.parser import HTMLParser


def compose(to, subject, template, **kwargs):
    msg = Message(subject, recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    return msg


def truncate_html(content, max_length=None):
    """Truncate HTML content to a certain number of words."""
    if not max_length:
        max_length = current_app.config['EXCERPT_LEN']
    try:
        bs = BeautifulSoup(str(content), "html.parser")
        parser = HTMLAbbrev(max_length)
        parser.feed(str(bs))
        return Markup(parser.close())
    except Exception as e:
        current_app.logger.debug(e)
        return "Could not truncate HTML"


def weight(tag_list):
    """Generate a weight relative to the frequency of a value."""
    # Find the maximum frequency
    tags, freqs = zip(*tag_list)
    max_frequency = max(freqs)
    weights = []

    # Use logarithmic scale
    for f in freqs:
        weights.append(
            Decimal(f).ln() / Decimal(max_frequency).ln() / Decimal(1.5)
            + Decimal.from_float(float(Fraction('1/3')))
        )

    return zip(tags, freqs, weights)


class JSONEncoder(BaseJSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, arrow.Arrow):
                return obj.format('YYYY-MM-DD HH:mm:ssZ')
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return JSONEncoder.default(self, obj)


whitespace = re.compile('(\S+)')


class HTMLAbbrev(HTMLParser):
    """
    Truncate HTML in a way that does not mangle tags. Adapted from Dan Crosta,
    http://late.am/post/2011/12/02/truncating-html-with-python.html
    """

    def __init__(self, maxlength, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self.stack = []
        self.maxlength = maxlength
        self.length = 0
        self.done = False
        self.out = []

    def emit(self, thing, count=False):
        if count and len(thing.strip()) > 0:
            self.length += 1
        if self.length <= self.maxlength:
            self.out.append(thing)
        elif not self.done:
            # trim trailing whitespace
            self.out[-1] = self.out[-1].rstrip()

            # close out tags on the stack
            for tag in reversed(self.stack[1:]):
                self.out.append('</%s>' % tag)
            self.out.append('…</%s>' % self.stack[0])
            self.done = True

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)
        attrs = ' '.join('%s="%s"' % (k, v) for k, v in attrs)
        self.emit('<%s%s>' % (tag, (' ' + attrs).rstrip()))

    def handle_endtag(self, tag):
        if tag == self.stack[-1]:
            self.emit('</%s>' % tag)
            del self.stack[-1]
        else:
            raise Exception('end tag %r does not match stack: %r' % (tag, self.stack))

    def handle_startendtag(self, tag, attrs):
        attrs = ' '.join('%s="%s"' % (k, v) for k, v in attrs)
        self.emit('<%s%s/>' % (tag, (' ' + attrs).rstrip()))

    def handle_data(self, data):
        for word in whitespace.split(data):
            self.emit(word, count=True)

    def handle_entityref(self, name):
        self.emit('&%s;' % name)

    def handle_charref(self, name):
        return self.handle_entityref('#%s' % name)

    def close(self):
        return ''.join(self.out)


class ReverseProxied:
    '''Wrap the application in this middleware and configure the 
    front-end server to add these headers, to let you quietly bind 
    this to a URL other than / and to an HTTP scheme that is 
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name) :]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


class Timer:
    """Time the execution of sensitive methods."""

    def __enter__(self):
        """Start the timer."""

        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        """End the timer."""
        self.end = time.perf_counter()
        self.interval = self.end - self.start
