import re
import time
from decimal import Decimal
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path

import arrow
from bs4 import BeautifulSoup
from flask import current_app, Markup
from flask.blueprints import (
    Blueprint as FlaskBlueprint,
    BlueprintSetupState as FlaskBlueprintSetupState,
)
from flask.json.provider import DefaultJSONProvider
from flask_sqlalchemy.pagination import Pagination
from markdown import markdown
from slugify import slugify


def read_changelog(site):
    logfile = Path(current_app.root_path).parent / f"CHANGELOG-{site}.md"
    contents = ""
    toc_dict = {}
    date_expr = re.compile(r"\(.*?\)")
    try:
        with open(logfile, encoding="utf-8") as f:
            contents = markdown(f.read(), extensions=["extra"], output="html5")

        # Do some extra parsing to grab a TOC based on H2
        # And wrap the release dates in <small> tags within the headings
        contents = BeautifulSoup(contents, "html.parser")
        contents.h1.decompose()  # Remove the "Changelog" title
        for heading in contents.find_all("h2"):
            text = heading.get_text()
            handle = slugify(text)
            toc_dict[handle] = text
            heading["id"] = handle

            if date := date_expr.search(heading.string):
                heading.string = heading.string[: date.start()]
                date_tag = contents.new_tag("small")
                date_tag.string = date.group(0)
                heading.append(date_tag)

    except (FileNotFoundError, PermissionError) as e:
        current_app.logger.error(f"Could not load changelog: {e}")
    return contents, toc_dict


def truncate_html(content, max_length=None):
    """Truncate HTML content to a certain number of words."""
    if not max_length:
        max_length = current_app.config['EXCERPT_LEN']
    bs = BeautifulSoup(str(content), "html.parser")
    parser = HTMLAbbrev(max_length)
    parser.feed(str(bs))
    return Markup(parser.close())


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


class BlueprintSetupState(FlaskBlueprintSetupState):
    """Adds the ability to set a hostname on all routes when registering the blueprint."""

    def __init__(self, blueprint, app, options, first_registration):
        super().__init__(blueprint, app, options, first_registration)

        host = self.options.get("host")
        # if host is None:
        #     host = self.blueprint.host

        self.host = host

        # This creates a 'blueprint_name.static' endpoint.
        # The location of the static folder is shared with the app static folder,
        # but all static resources will be served via the blueprint's hostname.
        if app.url_map.host_matching and not self.blueprint.has_static_folder:
            url_prefix = self.url_prefix
            self.url_prefix = None
            self.add_url_rule(
                f"{app.static_url_path}/<path:filename>",
                view_func=app.send_static_file,
                endpoint="static",
            )
            self.url_prefix = url_prefix

    def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
        # Ensure that every route registered by this blueprint has the host parameter
        options.setdefault('host', self.host)
        super().add_url_rule(rule, endpoint, view_func, **options)


class Blueprint(FlaskBlueprint):
    def make_setup_state(self, app, options, first_registration=False):
        return BlueprintSetupState(self, app, options, first_registration)


class JSONProvider(DefaultJSONProvider):  # pragma: no cover
    def dumps(self, obj, **kwargs):
        if hasattr(obj, "__json__"):
            return obj.__json__()
        if isinstance(obj, arrow.Arrow):
            return obj.isoformat()
        return super().dumps(obj, **kwargs)


whitespace = re.compile(r'(\S+)')


class HTMLAbbrev(HTMLParser):  # pragma: no cover
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


class GenericPagination(Pagination):
    """Extends the Flask-SQLAlchemy Pagination class to work with Whoosh search
    results."""

    def _query_items(self):
        return self._query_args["items"]

    def _query_count(self):
        return self._query_args["total"]
