import datetime
import factory

from diff_match_patch import diff_match_patch
from factory.alchemy import SQLAlchemyModelFactory as ModelFactory
from factory.fuzzy import FuzzyNaiveDateTime, FuzzyText
from lemonade_soapbox import db
from lemonade_soapbox.posts import Article, Revision, Tag
from lemonade_soapbox.models.users import User
from uuid import uuid4

differ = diff_match_patch()


class TagFactory(ModelFactory):
    class Meta:
        model = Tag
        sqlalchemy_session = db.session

    id = factory.Sequence(lambda n: n)
    label = FuzzyText(8)


class RevisionFactory(ModelFactory):
    class Meta:
        model = Revision
        sqlalchemy_session = db.session


class ArticleFactory(ModelFactory):
    class Meta:
        model = Article
        sqlalchemy_session = db.session

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
        sqlalchemy_session = db.session

    id = factory.Sequence(lambda n: n)
    name = FuzzyText()
    email = FuzzyText()
