import os

from lemonade_soapbox.create_app import create_app
from werkzeug.middleware.proxy_fix import ProxyFix


app = create_app()
app = ProxyFix(app)
