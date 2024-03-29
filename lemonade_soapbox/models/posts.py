from datetime import datetime
from uuid import uuid4

import arrow
from diff_match_patch import diff_match_patch
from flask import current_app, url_for
from flask_login import current_user
from markdown import markdown
from markupsafe import Markup
from PIL import Image
from slugify import slugify
from sqlalchemy import asc, desc, event, func, orm
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy_utils import ArrowType
from werkzeug.utils import cached_property
from whoosh import index
from whoosh.analysis import StemmingAnalyzer
from whoosh.fields import Schema, ID, KEYWORD, NUMERIC, TEXT, DATETIME
from whoosh.qparser import GtLtPlugin, MultifieldParser, QueryParser
from whoosh.qparser.dateparse import DateParserPlugin

from lemonade_soapbox import db
from lemonade_soapbox.helpers import GenericPagination, Timer


class Searchable:
    """Mixin for indexing and searching on a class using Whoosh."""

    schema = None

    @staticmethod
    @event.listens_for(db.session, "after_flush")
    def _after_flush(session, flush_context):
        """Index models that are searchable."""
        models = {}
        for obj in session.new | session.dirty | session.deleted:
            if isinstance(obj, Searchable):
                models.setdefault(obj.__class__, [])
                models[obj.__class__].append(obj)

        ix_path = current_app.config["INDEX_PATH"]
        for model, instances in models.items():
            try:
                ix = index.open_dir(
                    ix_path, schema=model.schema, indexname=model.__name__
                )
            except index.EmptyIndexError:
                ix = index.create_in(
                    ix_path, schema=model.schema, indexname=model.__name__
                )
            with ix.writer() as writer:
                for obj in instances:
                    obj_id = getattr(obj, "id")
                    if obj in session.deleted:
                        current_app.logger.info(f"Removing {obj} from index.")
                        writer.delete_by_term("id", str(obj_id))
                    else:
                        current_app.logger.info(f"Indexing {obj}.")
                        obj.add_to_index(writer)

    def add_to_index(self, writer):
        """Index a model instance."""
        idx_info = {}
        filters = self.schema_filters()
        fields = self.schema.names()
        for field in fields:
            value = getattr(self, field)
            if field in filters:
                value = filters[field](value)
            idx_info[field] = value
        writer.update_document(**idx_info)

    @classmethod
    def build_index(cls, per_pass=500):
        """Build a clean index of this model."""

        with Timer() as t:
            current_app.logger.info(
                f"Beginning clean indexing operation of {cls.__name__}."
            )
            ix_path = current_app.config["INDEX_PATH"]
            if not ix_path.exists():
                current_app.logger.info(
                    f"Index directory does not exist, attempting to create it at {ix_path}."
                )
                ix_path.mkdir()

            ix = index.create_in(ix_path, schema=cls.schema, indexname=cls.__name__)
            with ix.writer() as writer:
                with db.session.no_autoflush:
                    total = int(cls.query.order_by(None).count())
                    current_app.logger.info(
                        f"Indexing {cls.__name__}: {total} rows found."
                    )
                    done = 0

                    for m in cls.query.yield_per(per_pass):
                        m.add_to_index(writer)
                        done += 1
                        if done % per_pass == 0:
                            current_app.logger.info(
                                f"Indexed {done}/{total} ({done/total:.1%})."
                            )

                    current_app.logger.info(f"Finished: {done}/{total} indexed.")
        current_app.logger.info(
            f"Built index for {cls.__name__} in {t.interval:.3f} seconds."
        )

    @classmethod
    def get_query_parser(cls, fields=None):
        """Construct a query parser for searching."""
        # Indexer children should define at least one default search field.
        if not fields:
            fields = getattr(cls, '__searchable__', None)

        if isinstance(fields, list):
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
    def search(
        cls,
        query,
        paginate=True,
        fields=None,
        pagenum=1,
        pagelen=50,
        sort_order=None,
        sort_field=None,
        **kwargs,
    ):
        """Execute a Whoosh search against this model's index."""
        try:
            ix = index.open_dir(
                current_app.config['INDEX_PATH'], indexname=cls.__name__
            )
            qparser = cls.get_query_parser(fields)
            parsed_query = qparser.parse(query)
            with ix.searcher() as searcher:
                current_app.logger.debug(f"Sort order: {sort_order}")
                if sort_field in cls.__sortable__:
                    kwargs['sortedby'] = sort_field
                    if sort_order == 'desc':
                        kwargs['reverse'] = True
                current_app.logger.debug(kwargs)
                if paginate:
                    raw_results = searcher.search_page(
                        parsed_query, pagenum, pagelen=pagelen, **kwargs
                    )
                else:
                    raw_results = searcher.search(parsed_query, **kwargs)
                if raw_results.total > 0:
                    query_obj = cls.query.filter(
                        cls.id.in_([r['id'] for r in raw_results])
                    )
                    if sort_field in cls.__sortable__:
                        if sort_order == 'asc':
                            query_obj = query_obj.order_by(
                                getattr(cls, sort_field).asc()
                            )
                        else:
                            query_obj = query_obj.order_by(
                                getattr(cls, sort_field).desc()
                            )
                    results = query_obj.all()

                    return GenericPagination(
                        page=pagenum,
                        per_page=pagelen,
                        items=results,
                        total=raw_results.total,
                    )
                return None
        except Exception as e:
            current_app.logger.info(f"Search error: {e}")
            raise e


class UniqueHandleMixin:
    """
    Mixin for objects that need unique handle fields in DB. Assumes class
    inherits from db.Model and has a column named `handle`.
    """

    @declared_attr
    def handle(self):
        """URL-friendly handle, usually generated from the title."""
        return db.Column(db.String, nullable=False, default='')

    @classmethod
    def unique_check(cls, text=None):
        """Query database to check if handle is unique."""
        if text:
            unique = None
            with db.session.no_autoflush:
                unique = not cls.query.filter_by(handle=text).first()
            return unique
        return False

    def slugify(self, text='', max_length=100, to_lower=True):
        """
        Given any string, transform into URL-friendly handle.
        Also checks for uniqueness.
        """
        slug = ''
        if text:
            slug = original = slugify(text, max_length=max_length, lowercase=to_lower)

            # Check if unique
            i = 1
            while not self.unique_check(slug):
                slug = f'{original}-{i}'
                i += 1
        return slug

    def __init__(self, **kwargs):
        """
        Generate a unique slug for the handle provided or from a
        sensible default field.
        """
        if 'handle' not in kwargs or kwargs['handle'] == '':
            kwargs['handle'] = self.slugify(kwargs.get('title', ''))
        super().__init__(**kwargs)


class AuthorMixin:
    """Many-to-one relationship with the users table."""

    def __json__(self):
        # export = super().__json__()
        export = dict(author=self.author_id)
        return export

    @declared_attr
    def author_id(self):
        """Foreign key to the Users table, automatically insert current user."""
        return db.Column(
            db.Integer,
            db.ForeignKey('users.id'),
            default=lambda: getattr(current_user, 'id', None),
        )

    @declared_attr
    def author(self):
        return db.relationship('User', backref=self.__tablename__)


tag_associations = db.Table(
    'tag_associations',
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete="CASCADE")),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.id', ondelete="CASCADE")),
)


class TagMixin:
    """Any posts that are taggable."""

    def __json__(self):
        export = super().__json__()
        export.update(tags=list(self.tags))
        return export

    @declared_attr
    def _tags(self):
        return db.relationship(
            'Tag',
            secondary=tag_associations,
            sync_backref=False,
            passive_deletes=True,
            backref=db.backref(self.__tablename__, lazy='dynamic', viewonly=True),
        )

    @staticmethod
    def _find_or_create_tag(tag):
        with db.session.no_autoflush:
            q = Tag.query.filter_by(handle=Tag.slugify(tag))
            t = q.first()
            if not t:
                current_app.logger.info(f'Tag "{tag}" does not exist, creating.')
                t = Tag(label=tag)
        return t

    tags = association_proxy('_tags', 'label', creator=_find_or_create_tag.__func__)


class RevisionMixin:
    """Mixin for any post classes that want to handle revisions and autosaves."""

    def __json__(self):
        export = super().__json__()
        export.update(
            revision_id=self.current_revision_id,
            autosave_id=self.autosave_id,
            revisions=[r.__json__() for r in self.revisions],
        )
        return export

    @declared_attr
    def current_revision_id(self):
        """
        This is the id of the Revision that represents the most up to date
        content of this post.
        """
        return db.Column(db.String(32))

    @declared_attr
    def autosave_id(self):
        """This is the id of the autosave Revision for this post, if any."""
        return db.Column(db.String(32))

    @declared_attr
    def revisions(self):
        return db.relationship(
            'Revision',
            back_populates="post",
            cascade='all, delete',
            order_by='Revision.date_created.asc()',
            passive_deletes=True,
        )

    @declared_attr
    def current_revision(self):
        return db.relationship(
            "Revision",
            primaryjoin=f"foreign({self.__name__}.current_revision_id) == Revision.id",
            uselist=False,
            lazy="joined",
            viewonly=True,
        )

    @declared_attr
    def autosave(self):
        return db.relationship(
            'Revision',
            primaryjoin=f"foreign({self.__name__}.autosave_id) == Revision.id",
            uselist=False,
        )

    # @db.reconstructor
    # def __db_init__(self):
    #     super().__init__()
    #     self.selected_revision = self.current_revision

    @property
    def selected_revision(self):
        """
        Represents the Revision that is currently *selected*, i.e., loaded
        into the Post.body. This is, by default, the current_revision but
        can change from the `load_revision()` and `from_revision()` methods.
        """
        if getattr(self, "_selected_revision", None):
            return self._selected_revision
        return self.current_revision

    @selected_revision.setter
    def selected_revision(self, value):
        self._selected_revision = value

    @classmethod
    def from_revision(cls, revision_id):
        """Instantiate a post with a specific revision loaded."""
        try:
            # Load the revision and the post but only if the revision ID
            # belongs to this Post subclass
            r, p = (
                db.session.query(Revision, cls)
                .join(cls)
                .filter(
                    Revision.id == revision_id,
                    Revision.post.has(post_type=cls.__name__.lower()),
                )
                .one()
            )
            # Restore the post's body to the selected revision
            p.load_revision(r)
            return p
        except NoResultFound:
            current_app.logger.warning(
                f"Revision {revision_id} does not exist for {cls.__name__}s."
            )
            return None

    def load_revision(self, target):
        """Restore the article to a previous revision from current."""
        content = self.selected_revision.restore(target, self.body)
        if content:
            self.body = content
            self.selected_revision = target
            current_app.logger.info(
                f"Loaded revision {self.selected_revision.id} for {self}"
            )
        return self

    def new_autosave(self, content):
        """Save a temporary revision."""
        new_save = Revision(
            self,
            new=content,
            old=self.body,
            parent=self.selected_revision,
            major=False,
        )
        if self.id:
            if self.autosave:
                current_app.logger.info(
                    f'Deleting autosave {self.autosave.id} for post {self.id}'
                )
                db.session.delete(self.autosave)

            self.autosave = new_save
            new_save.post_id = self.id
            current_app.logger.info(f'New autosave for post {self.id} is {new_save.id}')
        return new_save

    def new_revision(self, old_content=''):
        """
        Create a revision object representing the diff between current body and
        new body.
        """
        r = None
        if not self.current_revision_id or not self.selected_revision:
            r = Revision(self, new=self.body, old='')
        else:
            # Check Levenshtein distance and generate patches while we're at it.
            distance, patch_text = self.selected_revision.distance(
                self.body, old_content
            )

            if distance > current_app.config['REVISION_THRESHOLD']:
                # Distance percentage trips the threshold for a new revision.
                r = Revision(self, parent=self.selected_revision, patch_text=patch_text)
                current_app.logger.debug(
                    f'Levenshtein percentage difference ({round(distance, 2)}) '
                    f'resulted in new revision {r.id} with parent {r.parent}'
                )
            else:
                # Changes aren't significant enough to merit a new revision.
                self.selected_revision.date_created = arrow.utcnow()
                self.selected_revision.patch_text = patch_text
                try:
                    del self.selected_revision.patches
                except KeyError:
                    pass
                current_app.logger.debug(
                    f'Levenshtein percentage difference ({round(distance, 2)}) is '
                    f'below the threshold ({current_app.config["REVISION_THRESHOLD"]}) '
                    f'for new revision creation.'
                )

        if r:
            self.current_revision_id = r.id
            self.revisions.append(r)
            self.selected_revision = r

        # Delete autosave
        if self.autosave:
            db.session.delete(self.autosave)
        return r or self.selected_revision


class Post(AuthorMixin, UniqueHandleMixin, TagMixin, Searchable, db.Model):
    """Base class from which all post-like objects (articles, reviews) inherit."""

    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    post_type = db.Column(db.String)
    title = db.Column(db.String, nullable=False)
    date_created = db.Column(ArrowType(timezone=True), default=datetime.utcnow)
    date_updated = db.Column(ArrowType(timezone=True), default=datetime.utcnow)
    date_published = db.Column(ArrowType(timezone=True))
    show_updated = db.Column(db.Boolean, default=False)
    status = db.Column(db.String, default='draft')
    cover = db.Column(db.String)
    body = db.Column(db.Text, default='')
    summary = db.Column(db.Text)
    lists = association_proxy("_lists", "list")

    __mapper_args__ = {'polymorphic_identity': 'post', 'polymorphic_on': post_type}

    def format(self, content, escape=False):
        """Accept raw Markdown input and output HTML5."""
        if escape:
            content = Markup.escape(content)

        content = markdown(content, extensions=['extra'], output_format='xhtml5')
        return Markup(content)

    def get_permalink(self, relative=True):
        """Generate a permanent link to the post."""
        raise NotImplementedError

    def get_editlink(self, relative=True):
        """Generate an edit link for this post."""
        raise NotImplementedError

    def __repr__(self):
        return f'<{type(self).__name__} {self.id} "{self.title}">'

    @hybrid_property
    def sort_title(self):
        return self.title.lstrip(' The').lstrip('A ').lstrip('An ')

    @sort_title.expression
    def sort_title(self):
        return func.ltrim(func.ltrim(func.ltrim(self.title, 'The '), 'A '), 'An ')

    @cached_property
    def body_html(self):
        """Return the formatted version of the article contents."""
        return self.format(self.body)

    @cached_property
    def next_post(self):
        """Return the post published after this post."""
        if self.date_published:
            return (
                self.published()
                .filter(self.__class__.date_published > self.date_published)
                .order_by(asc('date_published'))
                .first()
            )
        return None

    @cached_property
    def previous_post(self):
        """Return the post published prior to this post."""
        if self.date_published:
            return (
                self.query.filter(self.__class__.date_published < self.date_published)
                .order_by(desc('date_published'))
                .first()
            )
        return None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cover_path = (
            current_app.instance_path / "media" / self.post_type / "covers"
        )
        if not self.status:
            self.status = 'draft'

    @orm.reconstructor
    def __db_init__(self, **kwargs):
        self.cover_path = (
            current_app.instance_path / "media" / self.post_type / "covers"
        )

    @classmethod
    def published(cls):
        """Filter queries so only published records are shown."""
        return cls.query.filter(
            (cls.status == 'published') & (cls.date_published <= arrow.utcnow())
        )

    def process_cover(self, img_data=None):
        """Save a new cover image for this post."""
        if not img_data:
            return
        cover_name = f"{self.id}-{self.handle}-cover.jpg"

        with Image.open(img_data) as img:
            # Save image as JPEG regardless of original file type
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            img.save(self.cover_path / cover_name)
        self.cover = cover_name

    def save(self, action="saved", old_content=None):
        """Update various attributes of a post when it is being saved to the db."""
        if action == "deleted" and self.status == "deleted":
            # Permanently delete post from database
            self.status = "removed"

            # Remove cover
            if self.cover:
                (self.cover_path / self.cover).unlink(missing_ok=True)

            db.session.delete(self)
            # Need to do this to avoid SQLAlchemy RACE condition
            if issubclass(self.__class__, RevisionMixin):
                db.session.delete(self.selected_revision)
            current_app.logger.info(f"{self} {action}")
            return f"{self.post_type.capitalize()} permanently deleted."

        self.date_updated = arrow.utcnow()
        self.status = self.status if action == "saved" else action

        # Generate a new Revision if applicable
        if issubclass(self.__class__, RevisionMixin) and old_content:
            with db.session.no_autoflush:
                self.new_revision(old_content)

        message = f"{self.post_type.capitalize()} {action}"
        if action == "draft":
            self.date_published = None
            message = f"{self.post_type.capitalize()} moved to drafts."
        if action == "published":
            if self.date_published:
                # Convert publication date to relative time, e.g., "in 1 day"
                message += f" {self.date_published.humanize()}."
            else:
                # If no publication date was set, publish immediately.
                self.date_published = self.date_updated
                message += " just now."

        # Add instance to session but the caller will handle committing
        db.session.add(self)
        current_app.logger.info(f"{self} {action} at {self.date_updated}")
        return message

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
            'tags': lambda x: ', '.join(x),
        }
        return exceptions


class Article(Post, RevisionMixin):
    """Blog posts."""

    __tablename__ = 'articles'
    __searchable__ = ['title', 'body', 'status']
    __sortable__ = ['author', 'date_created', 'date_published', 'date_updated', 'title']
    __mapper_args__ = {'polymorphic_identity': 'article'}

    id = db.Column(db.Integer, db.ForeignKey('posts.id'), primary_key=True)

    schema = Schema(
        id=ID(stored=True, unique=True),
        author=TEXT(phrase=False),
        date_created=DATETIME(sortable=True),
        date_published=DATETIME(sortable=True),
        date_updated=DATETIME(sortable=True),
        body=TEXT(analyzer=StemmingAnalyzer()),
        handle=ID(unique=True),
        status=ID(),
        tags=KEYWORD(commas=True, scorable=True),
        title=TEXT(field_boost=2.0, analyzer=StemmingAnalyzer()),
    )

    def __json__(self):
        export = super().__json__()
        export.update(cover=self.cover, summary=self.summary)
        return export

    def get_permalink(self, relative=True):
        """Generate a permanent link to the article."""
        if not self.id:
            return ""
        kwargs = {'handle': self.handle, '_external': not relative}
        if self.status == 'published':
            kwargs['year'] = self.date_published.year
            kwargs['month'] = self.date_published.strftime('%m')
            route = 'blog.single_article'
        elif self.status == 'draft':
            route = 'blog.show_draft'
        elif self.status == 'deleted':
            route = 'blog.show_deleted'
        return url_for(route, **kwargs)

    def get_editlink(self, relative=True):
        if not self.id:
            return ""
        return url_for(
            'admin.edit_post', id=self.id, post_type="blog", _external=not relative
        )

    @classmethod
    def post_breakdown(cls):
        """Generate a breakdown of post counts by year and month."""
        q = (
            db.session.query(
                func.extract('YEAR', Article.date_published).label('pub_year'),
                func.extract('MONTH', Article.date_published).label('pub_month'),
                func.count(Article.id),
            )
            .filter(Article.status == 'published')
            .group_by('pub_year', 'pub_month')
            .order_by(desc('pub_year'))
            .all()
        )
        breakdown = {}
        for y, m, c in q:
            year = breakdown.setdefault(int(y), {})
            year[int(m)] = c
        return breakdown


class Review(Post, RevisionMixin):
    """Book reviews."""

    __tablename__ = 'reviews'
    __searchable__ = [
        'body',
        'title',
        'book_author',
        'date_created',
        'date_published',
        'date_updated',
        'date_finished',
        'tags',
        'rating',
        'status',
    ]
    __sortable__ = [
        'date_created',
        'date_published',
        'date_read',
        'title',
        'date_updated',
        'date_finished',
        'date_started',
        'book_author',
        'book_author_sort',
    ]
    __mapper_args__ = {'polymorphic_identity': 'review'}

    id = db.Column(db.Integer, db.ForeignKey('posts.id'), primary_key=True)
    book_author = db.Column(db.String)
    book_author_sort = db.Column(db.String)
    book_id = db.Column(db.String)  # ISBN or ASIN

    date_started = db.Column(ArrowType(timezone=True))
    date_finished = db.Column(ArrowType(timezone=True))
    goodreads_id = db.Column(db.String)
    storygraph_id = db.Column(db.String)
    rating = db.Column(db.Integer, info={'min': 0, 'max': 5}, default=0)
    spoilers = db.Column(db.Boolean, default=False)

    schema = Schema(
        id=ID(stored=True, unique=True),
        book_author=TEXT(),
        book_author_sort=TEXT(sortable=True),
        title=TEXT(field_boost=10.0, analyzer=StemmingAnalyzer(), sortable=True),
        date_created=DATETIME(sortable=True),
        date_published=DATETIME(sortable=True),
        date_updated=DATETIME(sortable=True),
        date_finished=DATETIME(sortable=True),
        body=TEXT(analyzer=StemmingAnalyzer()),
        rating=NUMERIC(),
        handle=ID(unique=True),
        status=ID(),
        tags=KEYWORD(commas=True, scorable=True),
    )

    def __json__(self):
        export = super().__json__()
        export.update(
            book_author=self.book_author,
            book_author_sort=self.book_author_sort,
            book_id=self.book_id,
            cover=self.cover,
            date_started=self.date_started,
            date_finished=self.date_finished,
            goodreads_id=self.goodreads_id,
            rating=self.rating,
            spoilers=self.spoilers,
            summary=self.summary,
        )
        return export

    @hybrid_property
    def dates_read(self):
        """Formats the start/finished date into a string for us."""
        return (
            f"{self.date_started.format('YYYY-MM-DD')} - "
            f"{self.date_finished.format('YYYY-MM-DD')}"
        )

    @dates_read.setter
    def dates_read(self, value):
        """Sets the start/finished date when given an appropriate string."""
        try:
            start, end = [arrow.get(x.strip()) for x in value.split('-')]
            if end < start:
                raise Exception
            self.date_started = start
            self.date_finished = end
        except Exception as e:
            raise Exception('Dates read must be a valid date range.') from e

    @property
    def short_title(self):
        """Returns the shortened book title without subtitle."""
        return self.title.split(":")[0]

    def get_permalink(self, relative=True):
        """Generate a permanent link to the review."""
        if not self.id:
            return ""
        kwargs = {
            'handle': self.handle,
            '_external': not (relative),
        }
        return url_for('reviews.show_review', **kwargs)

    def get_editlink(self, relative=True):
        if not self.id:
            return ""
        return url_for(
            'admin.edit_post',
            id=self.id,
            post_type="reviews",
            _external=not (relative),
        )

    def schema_filters(self):
        exceptions = super().schema_filters()
        exceptions['date_finished'] = lambda x: getattr(x, 'datetime', None)
        return exceptions


class List(Post):
    """Lists of posts."""

    __tablename__ = "lists"
    __searchable__ = [
        "body",
        "title",
        "date_created",
        "date_published",
        "date_updated",
        "tags",
        "status",
    ]
    __sortable__ = [
        "date_created",
        "date_published",
        "date_read",
        "title",
        "date_updated",
    ]
    __mapper_args__ = {"polymorphic_identity": "list"}

    schema = Schema(
        id=ID(stored=True, unique=True),
        author=TEXT(phrase=False),
        date_created=DATETIME(sortable=True),
        date_published=DATETIME(sortable=True),
        date_updated=DATETIME(sortable=True),
        body=TEXT(analyzer=StemmingAnalyzer()),
        handle=ID(unique=True),
        status=ID(),
        tags=KEYWORD(commas=True, scorable=True),
        title=TEXT(field_boost=2.0, analyzer=StemmingAnalyzer()),
    )

    id = db.Column(db.Integer, db.ForeignKey('posts.id'), primary_key=True)
    owner = db.Column(
        db.Enum("tachyondecay.net", "kara.reviews", name="owner"),
    )
    # If true, the list should count down (e.g., top 10 list) instead of up
    reverse_order = db.Column(db.Boolean, default=False)
    show_numbers = db.Column(db.Boolean, default=True)

    def get_permalink(self, relative=True):
        """Generate a permanent link to the post."""
        if not self.id:
            return ""
        return url_for(
            "frontend.lists.show_list"
            if self.owner == "tachyondecay.net"
            else "reviews.lists.show_list",
            handle=self.handle,
            _external=(not relative),
        )

    def get_editlink(self, relative=True):
        """Generate an edit link for this post."""
        return url_for("admin.edit_post", post_type="lists", id=self.id)

    def process_cover(self, img_data=None):
        """
        Update various attributes of a list when it is being saved to the db.
        This is overridden to provide logic specific to generating list covers.
        """
        if img_data:
            super().process_cover(img_data)
        elif not self.cover:
            current_app.logger.debug("Generating cover")
            if len(self.items) == 1:
                # There is only one item in the list, so its cover is the cover image
                self.cover = self.items[0].post.cover
            elif len(self.items) > 1:
                # There are multiple items in the list, so generate a cover
                input_imgs = []
                for item in self.items:
                    if item.post.cover:
                        try:
                            current_app.logger.debug(f"Opening cover for {item.post}")
                            img = Image.open(item.post.cover_path / item.post.cover)
                        except FileNotFoundError:
                            current_app.logger.debug("Cover image not found")
                            continue
                        if img.height != 400:
                            current_app.logger.debug(f"Resizing cover from {item.post}")
                            img.resize((round((img.width / img.height) * 400), 400))
                        input_imgs.append(img)
                cover_width = min(1200, sum([img.width for img in input_imgs]))
                if cover_width:
                    new_cover = Image.new("RGB", (cover_width, 400))
                    x_dist = 0
                    current_app.logger.debug("Generating now...")
                    for img in input_imgs:
                        new_cover.paste(img, (x_dist, 0))
                        x_dist += img.width
                    self.cover = f"{self.id}-{self.handle}-cover.jpg"
                    new_cover.save(self.cover_path / self.cover)


class ListItem(db.Model):
    """Association object that links posts to a list."""

    __tablename__ = "list_items"
    list_id = db.Column(
        db.Integer, db.ForeignKey("lists.id", ondelete="CASCADE"), primary_key=True
    )
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )

    # Posts on a list can be ordered; OrderingList helps us do this automatically
    list = db.relationship(
        "List",
        backref=db.backref(
            "items",
            cascade="all, delete-orphan",
            collection_class=ordering_list("position", count_from=1),
            order_by="ListItem.position",
        ),
        foreign_keys=list_id,
    )
    post = db.relationship("Post", backref="_lists", foreign_keys=post_id)
    position = db.Column(db.Integer)
    blurb = db.Column(db.Text)

    # def __repr__(self):
    #     return self.post.__repr__()


class Revision(AuthorMixin, db.Model):
    """
    Record of a revision of a post as a list of patches to go from current
    revision to previous revision.
    """

    __tablename__ = 'revisions'

    id = db.Column(db.String(32), primary_key=True, unique=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id', ondelete="CASCADE"))
    post = db.relationship("Post")
    date_created = db.Column(ArrowType(timezone=True), default=datetime.utcnow)
    depth = db.Column(db.Integer)
    patch_text = db.Column(db.Text)
    parent_id = db.Column(db.String, db.ForeignKey('revisions.id', ondelete='SET NULL'))
    parent = db.relationship('Revision', remote_side=[id])
    major = db.Column(db.Boolean, default=True)

    def __init__(self, post, new='', old='', **kwargs):
        """
        Create a new Revision object.

        Expects in kwargs a `patch_text` containing previously made
        patches, or `new` and `old` text for generating the patches.
        """
        super().__init__(author_id=post.author_id, **kwargs)

        self.differ = diff_match_patch()
        self.id = uuid4().hex
        self.depth = getattr(self.parent, 'depth', -1) + 1
        self.parent_id = getattr(self.parent, 'id', None)

        if not self.patch_text:
            self.patch_text = self.differ.patch_toText(self.differ.patch_make(new, old))

    @db.reconstructor
    def __db_init__(self):
        super().__init__()
        self.differ = diff_match_patch()

    def distance(self, new, old):
        """
        Calculates Levenshtein distance between provided texts, returns
        distance and patch_text as a tuple.
        """
        diffs = self.differ.diff_main(new, old)
        distance = self.differ.diff_levenshtein(diffs) / max(len(old), len(new))
        patches = self.differ.patch_make(new, diffs)
        patch_text = self.differ.patch_toText(patches)
        return (distance, patch_text)

    @cached_property
    def patches(self):
        """Unpacks patch text into a patches object for the first time."""
        return self.differ.patch_fromText(self.patch_text)

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
            p.diffs = [(d[0] * -1, d[1]) for d in p.diffs]
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
    """Flexible categories for posts."""

    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    handle = db.Column(db.String(100), unique=True)
    label = db.Column(db.String(100))

    def __init__(self, *args, **kwargs):
        """Create a handle for a tag based on the supplied label."""
        super().__init__(*args, **kwargs)
        self.handle = self.slugify(self.label)

    def __repr__(self):
        return f'<Tag "{self.label}">'

    @classmethod
    def frequency(
        cls,
        match=None,
        post_types=None,
        status=None,
        sort_by="label",
        order_desc=False,
        page=1,
        per_page=None,
    ):
        """Returns tuples of tags and their frequencies."""
        if not post_types:
            post_types = ["article", "review"]
        if not status:
            status = ["published"]

        # Start building subqueries—going to select the Tag class
        subqueries = [cls]
        # Iterate over the post types included in this query
        for p in post_types:
            q = (
                db.select(db.func.count(tag_associations.c.post_id))
                .join(Post)
                .where(Post.post_type == p, tag_associations.c.tag_id == cls.id)
            )
            if status:
                q = q.where(Post.status.in_(status))
            subqueries.append(q.scalar_subquery().label(f'{p}_count'))
        # Build the main query, adding on sorting and filtering on label
        main_query = (
            db.select(*subqueries)
            .group_by(cls.id)
            .order_by(getattr(db, "desc" if order_desc else "asc")(sort_by))
        )
        if match:
            main_query = main_query.where(Tag.label.ilike(f"%{match}%"))

        total = db.session.execute(
            db.select(func.count()).select_from(main_query.subquery())
        ).scalar()

        if per_page:
            limited_query = main_query.limit(per_page).offset((page - 1) * per_page)
            return GenericPagination(
                page=page,
                per_page=per_page,
                items=list(db.session.execute(limited_query)),
                total=total,
            )
        return list(db.session.execute(main_query))

    @classmethod
    def slugify(cls, text):
        """Create a unique handle for this tag."""
        return slugify(text, lowercase=True, max_length=100)
