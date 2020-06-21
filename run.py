import os

from lemonade_soapbox import create_app
from werkzeug.middleware import SharedDataMiddleware
from werkzeug.middleware.proxy_fix import ProxyFix


app = create_app(os.getenv('FLASK_CONFIG') or 'default')
app.wsgi_app = ProxyFix(app)

# Nginx handles proxying the media dir in production
# This emulates it when developing with Flask's built-in server
if app.config['ENV'] == 'development':
    app.wsgi_app = SharedDataMiddleware(
        app.wsgi_app, {'/media': os.path.join(app.instance_path, 'media')}
    )
