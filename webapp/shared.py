_bot_app = None


def set_bot_app(app):
    global _bot_app
    _bot_app = app


def get_bot_app():
    return _bot_app
