from flask import current_app

class SearchAPI():
    def __init__(self):
        self.commands = {}

    def command(self, inputs):
        def decorated_function(f):
            if isinstance(inputs, list):
                self.commands.update({n: f for n in inputs})
            else:
                self.commands[inputs] = f
            return f
        return decorated_function

    def run(self, name=None, *args, **kwargs):
        func = self.commands.get(name, None)
        if func:
            return func(*args, **kwargs)
