from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from gettext import gettext, ngettext
from config import config
from lemonade_soapbox.helpers import JSONEncoder, truncate_html, weight

csrf = CSRFProtect()
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()


def create_app(config_name='default'):
    """Factory for the application."""
    app = Flask(__name__,
                instance_path=config[config_name].INSTANCE_PATH,
                static_folder='assets')
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    csrf.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "admin.signin"
    login_manager.login_message_category = "error"
    mail.init_app(app)

    from lemonade_soapbox.views import admin, api, blog, frontend
    app.register_blueprint(admin.bp, url_prefix='/meta')
    app.register_blueprint(api.bp, url_prefix='/api')
    app.register_blueprint(blog.bp, url_prefix='/blog')
    app.register_blueprint(frontend.bp, url_prefix='')

    app.jinja_env.add_extension('jinja2.ext.i18n')
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True
    app.jinja_env.filters.update({
        'truncate_html': truncate_html,
        'weight': weight
    })
    app.jinja_env.install_gettext_callables(gettext, ngettext, newstyle=True)

    # Override Flask JSON encoder with our own
    app.json_encoder = JSONEncoder

    return app
