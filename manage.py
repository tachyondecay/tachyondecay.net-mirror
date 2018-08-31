import os

from flask.ext.script import Manager, Shell
from flask.ext.migrate import Migrate, MigrateCommand
from lemonade_soapbox import create_app, db
from lemonade_soapbox.posts import Article

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)


def make_shell_context():
    return dict(app=app, db=db, Article=Article)
manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)


@manager.command
def test():
    """Run the unit tests."""
    # import unittest
    # tests = unittest.TestLoader().discover('tests')
    # unittest.TextTestRunner(verbosity=2).run(tests)
    import nose
    nose.main(argv=[''])


if __name__ == '__main__':
    manager.run()
