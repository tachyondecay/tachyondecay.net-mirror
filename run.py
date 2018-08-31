import os

# from flask_migrate import Migrate
from lemonade_soapbox import create_app, db
from lemonade_soapbox.helpers import ReverseProxied


app = create_app(os.getenv('FLASK_CONFIG') or 'default')
app.wsgi_app = ReverseProxied(app.wsgi_app)

# migrate = Migrate(app, db)
