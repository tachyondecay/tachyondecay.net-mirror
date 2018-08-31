from hashlib import md5
from flask import current_app
from flask_login import UserMixin
from itsdangerous import (
    BadSignature,
    SignatureExpired,
    TimedJSONWebSignatureSerializer as Serializer
)
from lemonade_soapbox import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(64))
    url = db.Column(db.String(100))

    @property
    def email_hash(self):
        return md5(self.email.encode('UTF-8')).hexdigest()

    @classmethod
    def serializer(cls):
        """Return an itsdangerous JSON Web Signature Token serializer."""
        return Serializer(current_app.config['SECRET_KEY'],
                          expires_in=current_app.config['LOGIN_TOKEN_EXPIRY'])

    @classmethod
    def generate_token(cls, **kwargs):
        """Create a verification token to sign in/register."""
        token = cls.serializer().dumps(kwargs)
        return token

    @classmethod
    def verify(cls, token):
        s = cls.serializer()
        try:
            data = s.loads(token)
        except BadSignature as e:
            current_app.logger.info(e)
            raise Exception('Invalid signin token.')
        except SignatureExpired as e:
            current_app.logger.info(e)
            raise Exception('Expired signin token.')
        except Exception as e:
            current_app.logger.info(e)
        else:
            u = User.query.get(data.get('id', 0))
            current_app.logger.debug('hello')
            if u and u.email == data['email']:
                return u
            elif data.get('register', False):
                email = data['email']
                name = email.split('@')[0]
                return User(email=email, name=name)
            return None


@login_manager.user_loader
def load_user(userid):
    return User.query.get(userid)
