import click
import os
from flask import Flask
from gettext import gettext, ngettext
from lemonade_soapbox import csrf, db, login_manager
from lemonade_soapbox.config import config
from lemonade_soapbox.helpers import JSONEncoder, truncate_html, weight
from lemonade_soapbox.models import Article, Review, Searchable, User
from werkzeug.middleware.shared_data import SharedDataMiddleware


def create_app():
    """Factory for the application."""
    config_name = os.environ.get('FLASK_ENV', 'production')
    app = Flask('lemonade_soapbox', static_folder='assets',)
    app.instance_path = os.path.join(app.instance_path, app.config['ENV'])
    app.config.from_object(config[config_name])
    app.config.from_json(os.path.join(app.instance_path, 'config.json'))
    config[config_name].init_app(app)

    # Nginx handles proxying the media dir in production
    # This emulates it when developing with Flask's built-in server
    if app.config['ENV'] == 'development':
        app.wsgi_app = SharedDataMiddleware(
            app.wsgi_app, {'/media': os.path.join(app.instance_path, 'media')}
        )

    csrf.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "admin.signin"
    login_manager.login_message_category = "error"

    app.shell_context_processor(
        lambda: {'db': db, 'Article': Article, 'Review': Review, 'User': User}
    )

    @app.cli.command()
    @click.argument("model")
    def reindex(model):
        """Rebuild the search index for a given model."""
        model = globals().get(model)
        if not model:
            click.echo("Invalid model name.")
        elif not issubclass(model, Searchable):
            click.echo("Model is not Searchable.")
        else:
            model.build_index()

    from lemonade_soapbox.views import admin, api, blog, frontend, reviews

    app.register_blueprint(admin.bp, url_prefix='/meta')
    app.register_blueprint(api.bp, url_prefix='/api')
    app.register_blueprint(blog.bp, url_prefix='/blog')
    app.register_blueprint(frontend.bp, url_prefix='')
    app.register_blueprint(reviews.bp, url_prefix='/reviews')

    app.jinja_env.add_extension('jinja2.ext.i18n')
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True
    app.jinja_env.filters.update({'truncate_html': truncate_html, 'weight': weight})
    app.jinja_env.install_gettext_callables(gettext, ngettext, newstyle=True)

    # Override Flask JSON encoder with our own
    app.json_encoder = JSONEncoder

    return app
