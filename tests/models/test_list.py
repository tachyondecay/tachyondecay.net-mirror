import shutil
import pytest
from lemonade_soapbox.models import List
from PIL import Image
from tests.factories import ListFactory, ListItemFactory, ReviewFactory

pytestmark = pytest.mark.usefixtures("app", "db")


@pytest.fixture
def cover_dir(app):
    """Creates a temporary directory for covers."""

    _media_dir = app.instance_path / "media"
    _media_dir.mkdir(parents=True, exist_ok=True)
    for p in ["review", "list"]:
        (_media_dir / p / "covers").mkdir(parents=True)
    yield _media_dir
    shutil.rmtree(_media_dir)


def test_generate_cover_one_cover(app):
    """Test creating a list cover when there is only 1 item."""
    r = ReviewFactory()
    l = ListFactory(cover="", items=[ListItemFactory(post=r)])
    l.save()
    l.process_cover()
    assert l.cover == r.cover


def test_generate_cover(cover_dir):
    """Test generating a list cover from item covers."""
    reviews = []
    for i in range(3):
        r = ReviewFactory()
        cover = Image.new("RGB", (200, 400 if i <= 1 else 600))
        cover.save(r.cover_path / r.cover)
        reviews.append(r)
    reviews.append(ReviewFactory())
    l = ListFactory(cover="", items=[ListItemFactory(post=r) for r in reviews])
    l.save()
    l.process_cover()
    assert l.cover == f"{l.id}-{l.handle}-cover.jpg"
    assert (l.cover_path / l.cover).is_file()
