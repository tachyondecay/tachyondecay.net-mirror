import json
import os
from copy import deepcopy
from datetime import timedelta
from gettext import gettext, ngettext
from logging.config import dictConfig
from pathlib import Path

import arrow
import click
from flask import Flask
from werkzeug.middleware.shared_data import SharedDataMiddleware

from lemonade_soapbox import csrf, db, login_manager, migrate
from lemonade_soapbox.logging_config import logging_config
from lemonade_soapbox.helpers import JSONProvider, truncate_html, weight
from lemonade_soapbox.models import (
    Article,
    List,
    ListItem,
    Review,
    Searchable,
    Tag,
    User,
)


def create_app(config_name=None):
    """Factory for the application."""
    config_name = config_name or os.getenv("CONFIG", "production")

    # Configure logging before creating the app
    logging_path = Path("instance", config_name, "logs")
    logging_path.mkdir(exist_ok=True)
    # Create a copy of logging config in case we are calling create_app() more
    # than once.
    logging_config_instance = deepcopy(logging_config)
    for k in logging_config_instance.get("handlers", {}):
        h = logging_config_instance["handlers"][k]
        if "filename" in h:
            h["filename"] = logging_path / h["filename"]
    dictConfig(logging_config_instance)

    app = Flask(
        "lemonade_soapbox",
        static_folder="assets",
        static_host=os.getenv("MAIN_HOST"),
        host_matching=True,
    )

    # Load instance-specific config, create search index dir
    app.instance_path = Path(app.instance_path, config_name)
    app.config["INDEX_PATH"] = app.instance_path / "index"
    app.config["INDEX_PATH"].mkdir(exist_ok=True)
    app.config.from_file(app.instance_path / "config.json", json.load)

    # Nginx handles proxying the media dir in production
    # This emulates it when developing with Flask's built-in server
    if os.getenv("CONFIG") == "development" or app.testing:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
        app.wsgi_app = SharedDataMiddleware(
            app.wsgi_app, {"/media": str(app.instance_path / "media")}
        )

    csrf.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "admin.signin"
    login_manager.login_message_category = "error"
    migrate.init_app(app, db)

    app.shell_context_processor(
        lambda: {
            'db': db,
            'Article': Article,
            'List': List,
            'ListItem': ListItem,
            'Review': Review,
            'Tag': Tag,
            'User': User,
        }
    )

    @app.cli.command()
    @click.argument("model")
    @click.option("--per-pass", default=100)
    def reindex(model, per_pass):
        """Rebuild the search index for a given model."""
        model = globals().get(model)
        if not model:
            click.echo("Invalid model name.")
        elif not issubclass(model, Searchable):
            click.echo("Model is not Searchable.")
        else:
            model.build_index(per_pass=per_pass)
            click.echo("Indexing complete.")

    # Lists blueprint must be imported here so that it registers on admin and frontend
    from lemonade_soapbox.views import admin, api, blog, frontend, lists, reviews

    # Register admin and API blueprints on both domains so we can log in to both
    app.register_blueprint(admin.bp, host=os.getenv('MAIN_HOST'), url_prefix='/meta')
    app.register_blueprint(api.bp, host=os.getenv('MAIN_HOST'), url_prefix='/api')
    app.register_blueprint(blog.bp, host=os.getenv('MAIN_HOST'), url_prefix='/blog')
    app.register_blueprint(frontend.bp, host=os.getenv('MAIN_HOST'), url_prefix='/')
    app.register_blueprint(reviews.bp, host=os.getenv('REVIEW_HOST'), url_prefix='/')

    # Configure Jinja env
    app.jinja_env.add_extension('jinja2.ext.i18n')
    app.jinja_env.filters.update({'truncate_html': truncate_html, 'weight': weight})
    app.jinja_env.globals.update({'arrow': arrow, 'timedelta': timedelta})
    app.jinja_env.install_gettext_callables(gettext, ngettext, newstyle=True)
    app.jinja_env.lstrip_blocks = True
    app.jinja_env.trim_blocks = True

    # Override Flask JSON provider with our own
    app.json = JSONProvider(app)

    return app
