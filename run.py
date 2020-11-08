from flask.cli import load_dotenv
from lemonade_soapbox.create_app import create_app
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()  # Load environment vars
app = create_app()
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2)
