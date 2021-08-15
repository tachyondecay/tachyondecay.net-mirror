from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from sqlalchemy import MetaData

# From Flask-SQLAlchemy docs, this makes sure that SQLAlchemy names all
# foreign key constraints. This is required for db.drop_all() to
# work properly.
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

csrf = CSRFProtect()
db = SQLAlchemy(metadata=MetaData(naming_convention=convention))
login_manager = LoginManager()
