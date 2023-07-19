from hashlib import md5
from flask import current_app
from flask_login import UserMixin
from lemonade_soapbox import db, login_manager
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy_utils import force_auto_coercion, PasswordType

force_auto_coercion()  # Needed for use of PasswordType


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(64))
    password = db.Column(PasswordType(schemes=['bcrypt']))
    url = db.Column(db.String(100))

    def __json__(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "password": self.password.hash.decode("utf-8"),
            "url": self.url,
        }

    @property
    def email_hash(self):
        return md5(self.email.encode('UTF-8')).hexdigest()

    @hybrid_property
    def first_name(self):
        return self.name.split(' ')[0]

    @hybrid_property
    def last_name(self):
        return self.name.split(' ')[1]


@login_manager.user_loader
def load_user(userid):
    return db.session.get(User, userid)
