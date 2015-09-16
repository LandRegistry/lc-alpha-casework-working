

class Config(object):
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_NAME = 'working'
    DATABASE_USER = 'landcharges'
    DATABASE_PASSWORD = 'lcalpha'
    DATABASE_HOST = 'localhost'


class PreviewConfig(Config):
    DATABASE_NAME = 'working'
    DATABASE_USER = 'landcharges'
    DATABASE_PASSWORD = 'lcalpha'
    DATABASE_HOST = 'localhost'
