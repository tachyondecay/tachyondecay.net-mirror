from datetime import datetime, timezone
from random import randint
from factory import (
    BUILD_STRATEGY,
    Faker,
    LazyAttribute,
    make_factory,
    post_generation,
    SelfAttribute,
    Sequence,
    SubFactory,
)
from factory.alchemy import SQLAlchemyModelFactory
from factory.fuzzy import FuzzyDateTime, FuzzyInteger
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, List, ListItem, Review, Revision, Tag


class ModelFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = db.session


class TagFactory(ModelFactory):
    class Meta:
        model = Tag

    label = Sequence(lambda n: f"tag {n}")


class PostFactory(ModelFactory):
    class Meta:
        abstract = True

    title = Faker("text", max_nb_chars=20)
    body = Faker("paragraph")
    cover = Sequence(lambda n: f"cover-{n}.jpg")
    date_published = FuzzyDateTime(datetime(2004, 1, 1, tzinfo=timezone.utc))
    date_created = LazyAttribute(lambda obj: obj.date_published)
    date_updated = LazyAttribute(lambda obj: obj.date_published)
    show_updated = False
    status = "published"


class RevisionMixinFactory(ModelFactory):
    @post_generation
    def revisions(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.revisions = extracted
        else:
            r = Revision(self, new=self.body, old='')
            self.revisions.append(r)
            self.current_revision_id = r.id
            self.selected_revision = r


class ArticleFactory(PostFactory, RevisionMixinFactory):
    class Meta:
        model = Article


class ReviewFactory(PostFactory, RevisionMixinFactory):
    class Meta:
        model = Review

    book_author = Faker("name")
    book_id = Faker("isbn13")

    date_started = Faker(
        "date_time_between",
        start_date=datetime(2004, 1, 1, tzinfo=timezone.utc),
        end_date=SelfAttribute("..date_published"),
    )

    date_finished = Faker(
        "date_time_between",
        start_date=SelfAttribute("..date_started"),
        end_date=SelfAttribute("..date_published"),
    )

    goodreads_id = FuzzyInteger(100000, 10000000)
    rating = FuzzyInteger(0, 5)
    spoilers = False


class ListItemFactory(ModelFactory):
    class Meta:
        model = ListItem

    post = SubFactory(ReviewFactory)
    position = Sequence(lambda n: n)
    blurb = Faker("paragraph")


class ListFactory(PostFactory):
    class Meta:
        model = List

    owner = "kara.reviews"

    @post_generation
    def items(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.items = extracted
        else:
            self.items = ListItemFactory.build_batch(randint(1, 10))
