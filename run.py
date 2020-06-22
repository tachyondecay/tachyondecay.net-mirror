import os

from lemonade_soapbox import create_app
from werkzeug.middleware.proxy_fix import ProxyFix


app = create_app()
app.wsgi_app = ProxyFix(app)
