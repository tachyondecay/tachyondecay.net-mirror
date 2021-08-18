from sqlalchemy_utils import auto_delete_orphans

from lemonade_soapbox.models.posts import (
    Article,
    List,
    ListItem,
    Post,
    Review,
    Revision,
    Searchable,
    Tag,
    tag_associations,
)
from lemonade_soapbox.models.users import User

# Automatically delete tags that are no longer associated
# with any Post objects.
auto_delete_orphans(Post._tags)
