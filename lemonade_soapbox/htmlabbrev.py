import re
from html.parser import HTMLParser

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
