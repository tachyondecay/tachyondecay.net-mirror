import json
import logging.config
import os
from lemonade_soapbox.logging_config import logging_config


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ermahgerd'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    INSTANCE_PATH = None

    AUTOSAVE_DELAY = 30
    DEFAULT_FEED_FORMAT = 'atom'
    EXCERPT_LEN = 200
    LOGIN_ALLOW_NEW = False
    LOGIN_EMAIL_FLOOD = 10
    LOGIN_TOKEN_EXPIRY = 1500
    TIMEZONE = 'UTC'

    @classmethod
    def init_app(cls, app):
        if cls.SQLALCHEMY_DATABASE_URI is None:
            app.config['SQLALCHEMY_DATABASE_URI'] = (
                'sqlite:///' + app.instance_path + '/database.sqlite'
            )
        app.config['INDEX_PATH'] = os.path.join(app.instance_path, 'index')
        app.config['LOG_PATH'] = os.path.join(app.instance_path, 'logs')

        # Make sure the filename in each handler logs to the correct path
        for k in logging_config.get('handlers', {}):
            h = logging_config['handlers'][k]
            if 'filename' in h:
                h['filename'] = os.path.join(app.config['LOG_PATH'], h['filename'])
        try:
            if not os.path.exists(app.config['LOG_PATH']):
                os.makedirs(app.config['LOG_PATH'])
            logging.config.dictConfig(logging_config)
        except Exception as e:
            app.logger.exception('Could not configure logging: %s', e)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class TestingConfig(Config):
    TESTING = True


class ProductionConfig(Config):
    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        if app.config['SECRET_KEY'] == 'ermahgerd':
            raise Exception(
                'Please configure a unique secret key in your production config file.'
            )


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
