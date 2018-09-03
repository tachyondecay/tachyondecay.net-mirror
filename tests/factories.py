import datetime
import factory
import pytest

from diff_match_patch import diff_match_patch
from factory.alchemy import SQLAlchemyModelFactory
from factory.fuzzy import FuzzyNaiveDateTime, FuzzyText
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, Revision, Tag, User
# from sqlalchemy.orm.scoping import scoped_session
from uuid import uuid4

differ = diff_match_patch()


class ModelFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = db.session


class TagFactory(ModelFactory):
    class Meta:
        model = Tag

    id = factory.Sequence(lambda n: n)
    label = FuzzyText(8)


class RevisionFactory(ModelFactory):
    class Meta:
        model = Revision


class ArticleFactory(ModelFactory):
    class Meta:
        model = Article

    id = factory.Sequence(lambda n: n)
    title = 'Hello World'
    handle = factory.Sequence(lambda n: 'article-%d' % n)
    body = 'This is a test post. Nothing to see here. Move along.'
    date_published = FuzzyNaiveDateTime(datetime.datetime(2004, 1, 1))
    status = 'published'

    @factory.post_generation
    def revisions(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.revisions = extracted
        else:
            r = Revision(new=self.body, old='')
            self.revisions.append(r)
            self.revision_id = r.id
            self.selected_revision = r

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of tags were passed in, use them
            self.tags = extracted


class UserFactory(ModelFactory):
    class Meta:
        model = User

    id = factory.Sequence(lambda n: n)
    name = FuzzyText()
    email = FuzzyText()
