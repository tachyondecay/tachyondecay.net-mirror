import json
import logging.config
import os
from lemonade_soapbox.logging_config import logging_config
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ermahgerd'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = 'localhost'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = None
    INSTANCE_PATH = None

    AUTOSAVE_DELAY = 30
    DEFAULT_FEED_FORMAT = 'atom'
    EXCERPT_LEN = 200
    LOGIN_ALLOW_NEW = False
    LOGIN_EMAIL_FLOOD = 10
    LOGIN_TOKEN_EXPIRY = 1500
    REVISION_THRESHOLD = 0.25
    TIMEZONE = 'UTC'

    @classmethod
    def init_app(cls, app):
        if cls.SQLALCHEMY_DATABASE_URI is None:
            app.config['SQLALCHEMY_DATABASE_URI'] = (
                'sqlite:///' + app.instance_path + 'database.sqlite')
        app.config['INDEX_PATH'] = os.path.join(app.instance_path, 'index')
        app.config['LOG_PATH'] = os.path.join(app.instance_path, 'logs')

        # Load user config variables
        try:
            with open(os.path.join(app.instance_path, 'config.json')) as f:
                data = json.load(f)
                app.config.update(data)
        except FileNotFoundError as e:
            app.logger.info('No user config file found, using default.')
        except IOError as e:
            app.logger.error('Could not open user config file: %s', e)
        except Exception as e:
            app.logger.error('Could not load user config: %s', e)

        app.logger.info(f'Config: {cls.__name__} | Instance: {app.instance_path}')

        cls.setup_logging(app)

    @classmethod
    def setup_logging(cls, app):
        data = {}
        # Try loading user logging configuration, if specified.
        try:
            with open(os.path.join(app.instance_path, 'logging.json')) as f:
                data = json.load(f)
        except FileNotFoundError as e:
            app.logger.info(f'No logging config file found, using default: {e}')
        except IOError as e:
            app.logger.error('Could not open logging config file: %s', e)

        # Fall back to default config dict
        if not data:
            data = logging_config

        # Make sure the filename in each handler logs to the correct path
        for k in data.get('handlers', {}):
            h = data['handlers'][k]
            if 'filename' in h:
                h['filename'] = os.path.join(app.config['LOG_PATH'], h['filename'])
        try:
            if not os.path.exists(app.config['LOG_PATH']):
                os.makedirs(app.config['LOG_PATH'])
            logging.config.dictConfig(data)
        except Exception as e:
            app.logger.exception('Could not configure logging: %s', e)


class DevelopmentConfig(Config):
    DEBUG = True
    INSTANCE_PATH = os.path.join(basedir, 'instance/dev/')
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    TESTING = True
    INSTANCE_PATH = os.path.join(basedir, 'instance/tests/')
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    INSTANCE_PATH = os.path.join(basedir, 'instance/production/')

    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        if app.config['SECRET_KEY'] == 'ermahgerd':
            raise Exception('Please configure a unique secret key in your production config file.')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,

    'default': ProductionConfig
}
