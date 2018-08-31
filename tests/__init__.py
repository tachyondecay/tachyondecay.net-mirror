import shutil

from nose.tools import assert_equal, assert_false, assert_true, raises

from flask import current_app
from lemonade_soapbox import create_app, db
from lemonade_soapbox.helpers import truncate_html
from lemonade_soapbox.posts import *
from tests.factories import *

app = create_app('testing')
app_context = app.app_context()


def setup():
    app_context.push()
    db.create_all()


def teardown():
    db.session.remove()
    db.drop_all()
    app_context.pop()


class TestMixin(object):
    @classmethod
    def setup(cls):
        pass

    @classmethod
    def teardown(cls):
        db.session.remove()
        try:
            shutil.rmtree(app.config['INDEX_PATH'])
        except FileNotFoundError:
            pass


class TestArticles(TestMixin):
    def test_author_assignment(self):
        """Make sure article can be associated with an author."""
        u = UserFactory()
        a = ArticleFactory(author=u)
        assert_equal(a.author, u)

    def test_default_handle(self):
        """An article with no handle specified creates one from the title."""
        a = ArticleFactory(title='Hello World', handle=None)
        assert_equal(a.handle, 'hello-world')

    def test_truncate(self):
        """Make sure the truncation script doesn't choke on image tags."""
        a = ArticleFactory(body='This is a no-no. <img src="" alt=""/>')
        truncate_html(a.body_html)

    def test_unique_handles(self):
        """Article handles must be unique."""
        a = ArticleFactory.create(handle='hello')
        b = ArticleFactory(handle='hello')
        assert_equal(b.handle, 'hello-1')


class TestRevisions(TestMixin):
    @classmethod
    def setup(cls):
        cls.start = 'The quick brown fox jumped over the lazy dog.'
        cls.article = ArticleFactory(body=cls.start)
        cls.article.new_revision('The slow brown fox leaped over the lazy cat.')
        cls.article.new_revision('A slow red fox leaped over the lazy cat.')

    def test_restore(self):
        """Restoring a previous revision from current revision."""
        r0 = self.article.revisions.order_by(Revision.date_created.asc()).first()
        current_app.logger.debug(self.article.date_created)
        assert_equal(self.article.load_revision(r0).body, self.start)

    def test_branched(self):
        """Restore a revision from abandoned tree from current revision."""
        r1 = self.article.revisions[1]
        r2 = self.article.revisions[2]
        self.article.load_revision(r1).new_revision('Hey you brown fox who leaped over the lazy cat.')
        self.article.new_revision('Hey you, brown fox, who jumped over the lazy cat-dog?')
        assert_equal(self.article.load_revision(r2).body, 'A slow red fox leaped over the lazy cat.')


class TestSearch(TestMixin):

    @classmethod
    def setup(cls):
        cls.article = ArticleFactory(title='Hello')
        db.session.commit()

    def test_add_to_index(self):
        """Make sure a new article is indexed."""
        assert_equal(Article.search('Hello')['total'], 1)

    def test_update_index(self):
        """Make sure article is re-indexed after changed."""
        self.article.title = 'World'
        db.session.commit()
        assert_equal(Article.search('World')['total'], 1)

    def test_remove_index(self):
        """Make sure article is removed from index after deletion."""
        db.session.delete(self.article)
        db.session.commit()
        assert_equal(Article.search('World')['total'], 0)


class TestTags(TestMixin):

    def test_frequency(self):
        """Obtain a list of tags and their frequencies."""
        ArticleFactory(tags=['Gauss', 'Euler'])
        ArticleFactory(tags=['Gauss', 'Cantor'])
        ArticleFactory(tags=['Gauss', 'Euler', 'Hilbert'])
        assert(Tag.frequency().all())

    def test_no_duplicates(self):
        """Tags inserted with the same label should not create a duplicate entry."""
        ArticleFactory(tags=['Gauss', 'Euler'])
        ArticleFactory(tags=['Gauss'])
        assert_equal(2, db.session.query(Tag).count())

    def test_no_duplicates_case_insensitive(self):
        """Tag labels should be case insensitive."""
        ArticleFactory(tags=['Euler'])
        ArticleFactory(tags=['euler'])
        assert_equal(1, db.session.query(Tag).count())

    def test_no_orphans(self):
        """Orphaned tags should be deleted after article deletes/updates."""
        ArticleFactory(tags=['Austen'])
        delete_me = ArticleFactory.create(tags=['Austen', 'Bronte'])
        db.session.commit()
        db.session.delete(delete_me)
        db.session.commit()
        assert_equal(1, db.session.query(Tag).count())
