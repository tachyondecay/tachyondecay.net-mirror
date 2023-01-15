from datetime import datetime, timezone
from random import randint
from factory import (
    Faker,
    LazyAttribute,
    post_generation,
    SelfAttribute,
    Sequence,
    SubFactory,
)
from factory.alchemy import SQLAlchemyModelFactory
from factory.fuzzy import FuzzyDateTime, FuzzyInteger
from lemonade_soapbox import db
from lemonade_soapbox.models import Article, List, ListItem, Review, Revision, Tag, User


class UniqueFaker(Faker):
    def evaluate(self, instance, step, extra):
        locale = extra.pop('locale')
        subfaker = self._get_faker(locale)
        unique_proxy = subfaker.unique
        return unique_proxy.format(self.provider, **extra)


class ModelFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"


class UserFactory(ModelFactory):
    class Meta:
        model = User

    email = UniqueFaker("email")
    name = Faker("name")
    password = Faker("password")


class TagFactory(ModelFactory):
    class Meta:
        model = Tag

    label = Sequence(lambda n: f"tag {n}")


class PostFactory(ModelFactory):
    class Meta:
        abstract = True

    author = SubFactory(UserFactory)
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
            r = Revision(self, new=self.body, old='', author=self.author)
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
        print("ROGER ROGER")
        if not create:
            print("NObody")
            return
        if extracted:
            print("hello WORLD")
            self.items = extracted
        else:
            print("Making list item")
            self.items = ListItemFactory.build_batch(randint(1, 10), list=self)
