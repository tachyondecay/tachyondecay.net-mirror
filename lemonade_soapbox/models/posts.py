import arrow
import os
from datetime import datetime
from diff_match_patch import diff_match_patch
from flask import current_app, Markup, url_for
from lemonade_soapbox import db
from lemonade_soapbox.helpers import Timer
from lemonade_soapbox.models.users import User
from markdown import markdown
from slugify import slugify
from sqlalchemy import asc, desc, event, func, orm
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy_utils import ArrowType, auto_delete_orphans, DateRangeType
from werkzeug.utils import cached_property
from whoosh import index, writing
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import Schema, ID, KEYWORD, NUMERIC, TEXT, DATETIME
from whoosh.qparser import GtLtPlugin, MultifieldParser, QueryParser
from whoosh.qparser.dateparse import DateParserPlugin
from uuid import uuid4


tag_relationships = {
    'Article': db.Table('tag_associations',
                        db.Column('tag_id', db.Integer, db.ForeignKey('tags.id')),
                        db.Column('article_id', db.Integer, db.ForeignKey('articles.id'))),
    'Review': db.Table('shelf_associations',
                       db.Column('tag_id', db.Integer, db.ForeignKey('tags.id')),
                       db.Column('review_id', db.Integer, db.ForeignKey('reviews.id')))
}


class Searchable():
    """Mixin for indexing and searching on a class using Whoosh."""

    schema = None

    @staticmethod
    @event.listens_for(db.session, 'after_flush')
    def _after_flush(session, flush_context):
        """Index models that are searchable."""
        models = {}
        for obj in session.new | session.dirty | session.deleted:
            if isinstance(obj, Searchable):
                models.setdefault(obj.__class__, [])
                models[obj.__class__].append(obj)

        ix_path = current_app.config['INDEX_PATH']
        # Create index if it does not exist.
        for model, instances in models.items():
            if not(index.exists_in(ix_path, indexname=model.__name__)):
                model.build_index()
            ix = index.open_dir(ix_path, indexname=model.__name__)
            with ix.writer() as writer:
                for obj in instances:
                    id = getattr(obj, 'id')
                    if obj in session.deleted:
                        current_app.logger.info('Removing {} {} from index.'.format(model, id))
                        writer.delete_by_term('id', str(id))
                    else:
                        current_app.logger.info('Indexing {} {}'.format(model, id))
                        obj.add_to_index(writer)

    def add_to_index(self, writer):
        """Index a model instance."""
        idx_info = {}
        filters = self.schema_filters()
        fields = self.schema.names()
        current_app.logger.debug(fields)
        for field in fields:
            current_app.logger.debug('Processing {}'.format(field))
            value = getattr(self, field)
            if field in filters:
                value = filters[field](value)
            idx_info[field] = value
            current_app.logger.debug(value)
        current_app.logger.debug(idx_info)
        writer.update_document(**idx_info)

    @classmethod
    def build_index(cls, per_pass=500):
        """Build a clean index of this model."""
        with Timer() as t:
            current_app.logger.info('Beginning clean indexing operation of {}'.format(cls.__name__))
            try:
                ix_path = current_app.config['INDEX_PATH']
                if not os.path.exists(ix_path):
                    current_app.logger.info('Index directory does not exist, '
                                            'attempting to create it at {}'.format(ix_path))
                    os.mkdir(ix_path)

                ix = index.create_in(ix_path, schema=cls.schema, indexname=cls.__name__)
                with ix.writer() as writer:
                    total = int(cls.query.order_by(None).count())
                    current_app.logger.info('Indexing {}: {} rows found.'.format(cls.__name__, total))
                    done = 0

                    for m in cls.query.yield_per(per_pass):
                        m.add_to_index(writer)
                        done += 1
                        if done % per_pass == 0:
                            current_app.logger.info('Indexed {}/{} ({:.1%})'
                                                    .format(done, total, done/total))

                    current_app.logger.info('Finished: {}/{} indexed.'.format(done, total))
            except Exception:
                raise
        current_app.logger.info('Built index for {} in {:.3f} seconds'.format(cls.__name__, t.interval))

    @classmethod
    def get_query_parser(cls, fields=None):
        """Construct a query parser for searching."""
        # Indexer children should define at least one default search field.
        if not fields:
            fields = getattr(cls, '__searchable__', None)

        current_app.logger.debug(fields)
        if(isinstance(fields, list)):
            qparser = MultifieldParser(fields, schema=cls.schema)
        else:
            qparser = QueryParser(fields, schema=cls.schema)
        qparser.add_plugin(DateParserPlugin(free=True))
        qparser.add_plugin(GtLtPlugin())
        return qparser

    def schema_filters(self):
        """Return a dict of attr => func pairs, where func is applied to the
        value of attr to process it before indexing."""
        raise NotImplementedError

    @classmethod
    def search(cls, query, paginate=True, fields=None, pagenum=1, pagelen=50,
               sort_order=None, sort_field=None, **kwargs):
        """Execute a Whoosh search against this model's index."""
        try:
            ix = index.open_dir(current_app.config['INDEX_PATH'], indexname=cls.__name__)
            qparser = cls.get_query_parser(fields)
            parsed_query = qparser.parse(query)
            with ix.searcher() as searcher:
                if sort_field in cls.__sortable__:
                    kwargs['sortedby'] = sort_field
                    if sort_order == 'desc':
                        kwargs['reverse'] = True
                if paginate:
                    raw_results = searcher.search_page(parsed_query,
                                                       pagenum,
                                                       pagelen=pagelen,
                                                       **kwargs)
                else:
                    raw_results = searcher.search(parsed_query, **kwargs)
                if raw_results.total > 0:
                    query_obj = cls.query.filter(cls.id.in_([r['id'] for r in raw_results]))
                    if sort_field in cls.__sortable__:
                        if sort_order == 'asc':
                            query_obj = query_obj.order_by(getattr(cls, sort_field).asc())
                        else:
                            query_obj = query_obj.order_by(getattr(cls, sort_field).desc())

                else:
                    query_obj = None
                results = {
                    'query': query_obj,
                    'offset': raw_results.offset,
                    'pagecount': raw_results.pagecount,
                    'pagelen': raw_results.pagelen,
                    'pagenum': raw_results.pagenum,
                    'total': raw_results.total
                }
                return results
        except Exception as e:
            current_app.logger.info('Search error: {}'.format(e))


class UniqueHandleMixin():
    """
    Mixin for objects that need unique handle fields in DB. Assumes class
    inherits from db.Model and has a column named `handle`.
    """

    @classmethod
    def unique_check(cls, text):
        """Query database to check if handle is unique."""
        return not cls.query.filter_by(handle=text).first()

    def slugify(self, text, max_length=100, to_lower=True, **kwargs):
        slug = original = slugify(text, max_length=max_length, lowercase=to_lower)

        # Check if unique
        i = 1
        while not self.unique_check(slug):
            slug = f'{original}-{i}'
            i += 1

        return slug


    def __init__(self, **kwargs):
        # If handle passed into init, verify it is unique
        if 'handle' in kwargs and not self.unique_check(kwargs['handle']):
            current_app.logger.info('Non-unique handle, "{}" requested.'.format(kwargs['handle']))
            kwargs['handle'] = self.slugify(kwargs['handle'])
            current_app.logger.info('New handle: {}'.format(kwargs['handle']))
        super().__init__(**kwargs)


class AuthorMixin():
    """Many-to-one relationship with the users table."""
    @declared_attr
    def author_id(cls):
        return db.Column(db.Integer, db.ForeignKey('users.id'))

    @declared_attr
    def author(cls):
        return db.relationship('User', backref=cls.__tablename__)


class TagMixin():
    """Any posts that are taggable."""
    tag_list = association_proxy('_tags', 'label')

    @declared_attr
    def _tags(cls):
        return db.relationship('Tag', secondary=tag_relationships[cls.__name__], backref=cls.__tablename__)

    def _find_or_create_tag(self, tag):
        with db.session.no_autoflush:
            q = Tag.query.filter_by(handle=Tag.slugify(tag))
            t = q.first()
            if not(t):
                current_app.logger.info('Tag "{}" does not exist, creating.'.format(tag))
                t = Tag(tag)
        return t

    @property
    def tags(self):
        """Return list of tag objects associated with this article."""
        tag_list = getattr(self, 'tag_list', [])
        return tag_list if (tag_list != ['']) else []

    @tags.setter
    def tags(self, tag_list):
        """Set list of tag objects associated with this article."""
        self._tags = [self._find_or_create_tag(t) for t in tag_list]


class PostMixin(AuthorMixin):
    """Base class from which all post-liked objects (articles, comments) inherit."""

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, default='')
    date_created = db.Column(ArrowType, default=datetime.utcnow)
    date_updated = db.Column(ArrowType)
    date_published = db.Column(ArrowType)
    show_updated = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(25), default='draft')
    _body_html = None


    def format(self, content, escape=False):
        """Accept raw Markdown input and output HTML5."""
        if escape:
            content = Markup.escape(content)

        content = markdown(content, extensions=['extra'], output_format='xhtml5')
        return Markup(content)

    def get_permalink(self, relative=True):
        """Generate a permanent link to the post."""
        raise NotImplementedError

    @property
    def body_html(self):
        """Return the formatted version of the article contents."""
        if not self._body_html:
            self._body_html = self.format(self.body)
        return self._body_html

    @cached_property
    def next_post(self):
        """Return the post published after this post."""
        if self.date_published:
            return self.query.filter(self.__class__.date_published > self.date_published).order_by(asc('date_published')).first()
        return None

    @cached_property
    def previous_post(self):
        """Return the post published prior to this post."""
        if self.date_published:
            return self.query.filter(self.__class__.date_published < self.date_published).order_by(desc('date_published')).first()
        return None

    @classmethod
    def published(cls):
        """Filter queries so only published records are shown."""
        return cls.query.filter((cls.status == 'published') & (cls.date_published <= arrow.utcnow()))

    def publish_post(self):
        """Set a post's status to "published" and set date published if null."""
        self.status = 'published'
        self.date_updated = arrow.utcnow()
        timing = ''
        if not self.date_published:
            self.date_published = arrow.utcnow()
            timing = 'just now'
        elif self.date_published > arrow.utcnow():
            timing = self.date_published.humanize()
        current_app.logger.info('Post {} published at {} (publication date: {}'
                                .format(self.id, arrow.utcnow(), self.date_published))
        return f'Post published {timing}. <a href="{self.get_permalink()}">View live version</a>.'

    def update_post(self):
        """Save changes to a post without altering its publication status."""
        self.date_updated = arrow.utcnow()
        current_app.logger.info('Post {} updated at {}'.format(self.id, self.date_updated))
        message = 'Article saved.'
        if self.status == 'published':
            message += ' <a href="{0}">View post.</a>'.format(self.get_permalink())
        return message


class Article(PostMixin, UniqueHandleMixin, TagMixin, Searchable, db.Model):
    """Blog posts."""

    __tablename__ = 'articles'
    __searchable__ = ['title', 'body']
    __sortable__ = ['author', 'date_created', 'date_published', 'date_updated', 'title']

    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text)
    handle = db.Column(db.String(255), unique=True)

    revisions = db.relationship('Revision',
                                backref='article',
                                foreign_keys='Revision.article_id',
                                lazy='dynamic',
                                post_update=True)
    revision_id = db.Column(db.String(32),
                            db.ForeignKey('revisions.id', use_alter=True))
    current_revision = db.relationship('Revision',
                                       foreign_keys='Article.revision_id',
                                       uselist=False,
                                       lazy='joined',
                                       post_update=True)
    autosave_id = db.Column(db.String(32), db.ForeignKey('revisions.id'))
    autosave = db.relationship('Revision',
                               foreign_keys='Article.autosave_id',
                               uselist=False,
                               post_update=True)

    schema = Schema(id=ID(stored=True, unique=True),
                    author=TEXT(phrase=False),
                    date_created=DATETIME(sortable=True),
                    date_published=DATETIME(sortable=True),
                    date_updated=DATETIME(sortable=True),
                    body=TEXT(analyzer=StemmingAnalyzer()),
                    handle=ID(unique=True),
                    status=ID(),
                    tags=KEYWORD(commas=True, scorable=True),
                    title=TEXT(analyzer=StemmingAnalyzer()))

    def __init__(self, **kwargs):
        """Extend init function to set sensible defaults."""
        super().__init__(**kwargs)
        if not self.body:
            self.body = ''
        if not self.status:
            self.status = 'draft'

        # Create handle from title if present
        if self.title and not self.handle:
            self.handle = self.slugify(self.title)

    @orm.reconstructor
    def __db_init__(self):
        super().__init__()
        self.selected_revision = self.current_revision

    def get_permalink(self, relative=True):
        """Generate a permanent link to the article."""
        if not self.id:
            return ""
        kwargs = {
            'handle': self.handle,
            '_external': not(relative)
        }
        if self.status == 'published':
            kwargs['year'] = self.date_published.year
            kwargs['month'] = self.date_published.strftime('%m')
            route = 'blog.single_article'
        elif self.status == 'draft':
            route = 'blog.show_draft'
        elif self.status == 'deleted':
            route = 'blog.show_deleted'
        return url_for(route, **kwargs)

    @classmethod
    def from_revision(cls, revision_id):
        """Instantiate an article with a specific revision loaded."""
        r = Revision.query.get(revision_id)
        if r:
            if r.article.revision_id != revision_id:
                r.article.load_revision(r)
            return r.article
        else:
            current_app.logger.warn('Revision {} does not exist.'.format(revision_id))
            return None

    def load_revision(self, target):
        """Restore the article to a previous revision from current."""
        content = self.selected_revision.restore(target, self.body)
        if content:
            self.body = content
            self._body_html = None
            self.selected_revision = target
            current_app.logger.info('Loaded revision {} for post {}'.format(
                                    self.selected_revision.id,
                                    self.id))
        return self

    def new_autosave(self, content):
        """Save a temporary revision."""
        new_save = Revision(new=content, old=self.body,
                            parent=self.selected_revision, author=self.author,
                            major=False)
        if self.id:
            if self.autosave:
                current_app.logger.info('Deleting autosave {} for post {}'.format(
                                        self.autosave.id,
                                        self.id))
            new_save.article_id = self.id
            self.autosave = new_save
            db.session.commit()
            current_app.logger.info('New autosave for post {} is {}'.format(
                                    self.id,
                                    new_save.id))
        return new_save

    def new_revision(self, new, old=None, parent=None):
        """
        Create a revision object representing the diff between current body and
        new body.
        """
        if parent is None:
            parent = getattr(self, 'selected_revision', None)
        if old is None:
            old = self.body
        r = Revision(new=new, old=old, parent=parent, author=self.author)
        self.body = new
        self._body_html = None  # Will regenerate body HTML next time it's needed
        self.revision_id = r.id
        self.revisions.append(r)
        self.selected_revision = r
        parent_id = getattr(parent, 'id', None)
        current_app.logger.info('Created new revision {} (parent: {}) for post {}.'
                                .format(r.id, parent_id, self.id))
        return r

    @classmethod
    def post_breakdown(cls):
        """Generate a breakdown of post counts by year and month."""
        q = db.session.query(func.strftime('%Y',
                             Article.date_published).label('pub_year'),
                             func.strftime('%m', Article.date_published).label('pub_month'),
                             func.count(Article.id)).filter(Article.status == 'published').group_by('pub_year', 'pub_month').order_by(desc('pub_year')).all()
        breakdown = {}
        for (y, m, c) in q:
            year = breakdown.setdefault(y, {})
            year[int(m)] = c
        return breakdown

    def schema_filters(self):
        """Return a dict of attr => func pairs, where func is applied to the
        value of attr to process it before indexing."""
        def get_datetime(d):
            return getattr(d, 'datetime', None)

        exceptions = {
            'id': str,
            'author': lambda x: getattr(x, 'name', None),
            'date_created': get_datetime,
            'date_published': get_datetime,
            'date_updated': get_datetime,
            'tags': lambda x: ', '.join(x)
        }
        return exceptions


class Review(PostMixin, UniqueHandleMixin, TagMixin, Searchable, db.Model):
    """Book reviews."""
    __tablename__ = 'reviews'
    __searchable__ = ['body', 'book_title', 'book_author']
    __sortable__ = ['date_created', 'date_published', 'date_read', 'book_title']

    book_author = db.Column(db.String(255), nullable=False)
    book_cover = db.Column(db.String(255))
    book_id = db.Column(db.String(255)) #ISBN or ASIN
    book_title = db.Column(db.String(255), nullable=False)

    dates_read = db.Column(DateRangeType)
    goodreads_id = db.Column(db.Integer)
    handle = db.Column(db.String(255), nullable=False)
    rating = db.Column(db.Integer, info={'min': 0, 'max': 5}, default=0)
    spoilers = db.Column(db.Boolean, default=False)
    summary = db.Column(db.Text)

    schema = Schema(id=ID(stored=True, unique=True),
                    book_author=TEXT(),
                    book_title=TEXT(),
                    date_created=DATETIME(sortable=True),
                    date_published=DATETIME(sortable=True),
                    date_updated=DATETIME(sortable=True),
                    date_read=DATETIME(sortable=True),
                    body=TEXT(analyzer=StemmingAnalyzer()),
                    rating=NUMERIC(),
                    handle=ID(unique=True),
                    status=ID(),
                    tags=KEYWORD(commas=True, scorable=True))

    @property
    def date_started(self):
        """Date started from date_read interval"""
        return self.dates_read.lower

    @property
    def date_finished(self):
        """Date finished from date_read interval"""
        return self.dates_read.upper

    def __init__(self, **kwargs):
        """Extend init function to set sensible defaults."""
        super().__init__(**kwargs)
        if not self.body:
            self.body = ''
        if not self.status:
            self.status = 'draft'

    def get_permalink(self, relative=True):
        """Generate a permanent link to the review."""
        if not self.id:
            return ""
        kwargs = {
            'handle': self.handle,
            '_external': not(relative),
        }
        return url_for(f'reviews.{self.status}', **kwargs)

    def schema_filters(self):
        """Return a dict of attr => func pairs, where func is applied to the
        value of attr to process it before indexing."""
        def get_datetime(d):
            return getattr(d, 'datetime', None)

        exceptions = {
            'id': str,
            'date_created': get_datetime,
            'date_published': get_datetime,
            'date_updated': get_datetime,
            'date_read': self.date_finished,
            'tags': lambda x: ', '.join(x)
        }
        return exceptions


class Revision(AuthorMixin, db.Model):
    """
    Record of a revision of a post as a list of patches to go from current
    revision to previous revision.
    """

    __tablename__ = 'revisions'

    id = db.Column(db.String(32), primary_key=True, unique=True)
    date_created = db.Column(ArrowType, default=datetime.utcnow)
    depth = db.Column(db.Integer)
    patch_text = db.Column(db.Text)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id', use_alter=True))
    parent_id = db.Column(db.String(32), db.ForeignKey('revisions.id'))
    parent = db.relationship('Revision', remote_side=[id])
    major = db.Column(db.Boolean, default=True)

    def __init__(self, new, old, parent=None, author=None, major=True):
        self.author = author
        self.major = major
        self.depth = getattr(parent, 'depth', -1) + 1
        self.differ = diff_match_patch()
        self.id = uuid4().hex
        self.parent = parent
        self.parent_id = getattr(parent, 'id', None)
        self.patches = self.differ.patch_make(new, old)
        self.patch_text = self.differ.patch_toText(self.patches)

    @orm.reconstructor
    def __db_init__(self):
        self.differ = diff_match_patch()
        self.patches = self.differ.patch_fromText(self.patch_text)

    def restore(self, target, content):
        """
        Restore the content represented by the patches in the target node given
        the content of this revision.
        """
        # Find lowest common ancestor of current revision and target revision
        lca = self.lca([target, self])
        if not lca:
            raise Exception("Could not determine LCA of current and target nodes.")
        current = self
        # Patch backwards from current revision to LCA
        while current is not lca:
            content = self.differ.patch_apply(current.patches, content)[0]
            current = current.parent
        # Patch forwards from LCA to target
        if target is not lca:
            parents = []
            while target is not lca:
                parents.append(target)
                target = target.parent
            for p in parents:
                content = self.differ.patch_apply(p.reverse_patch(), content)[0]
        return content

    def reverse_patch(self):
        """Reverse the insertions/deletions in a patch to move forward in time."""
        reverse_patches = self.differ.patch_deepCopy(self.patches)
        for p in reverse_patches:
            p.diffs = [(d[0]*-1, d[1]) for d in p.diffs]
        return reverse_patches

    @staticmethod
    def lca(nodes):
        """Given a list of nodes, find their lowest common ancestor."""
        nodes = set(nodes)
        tree = set()
        while len(nodes) > 0:
            current = nodes.pop()
            parents = set()
            while current not in tree and current is not None:
                parents.add(current)
                current = current.parent
            if tree:
                # If current node is None but a trace tree already exists, then
                # one or more of these nodes does not share common ancestors.
                if current is None:
                    return None
                tree = {t for t in tree if t.depth <= current.depth}
            else:
                tree = parents
        return max(tree, key=lambda x: x.depth, default=None)


class Tag(db.Model):
    """Flexible categories for articles."""

    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(100), unique=True)
    label = db.Column(db.String(100))

    def __init__(self, label):
        """Create a handle for a tag based on the supplied label."""
        self.label = label
        self.handle = self.slugify(label)

    @classmethod
    def frequency(cls, parent, order_by='handle'):
        """Returns tuples of tags and their frequencies."""
        rel = tag_relationships[parent.__name__]
        if order_by == 'count':
            order_by = func.count().desc()
        else:
            order_by = cls.handle
        return db.session.query(cls, func.count()) \
                         .outerjoin((rel, rel.c.tag_id == cls.id),
                                    (parent, parent.id == rel.c.article_id)) \
                         .filter(parent.status == 'published') \
                         .group_by(cls.id) \
                         .order_by(order_by)

    @classmethod
    def slugify(cls, text):
        """Create a unique handle for this tag."""
        return slugify(text, lowercase=True, max_length=100)


# Tags no longer associated with any article should be removed
auto_delete_orphans(Article._tags)
auto_delete_orphans(Review._tags)
