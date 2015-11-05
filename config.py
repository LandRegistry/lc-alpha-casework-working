import os


class Config(object):
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'working')
    DATABASE_USER = os.getenv('DATABASE_USER', 'lc-working-data')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'lcalpha')
    DATABASE_HOST = os.getenv('DATABASE_HOST', 'localhost')
    SQLALCHEMY_DATABASE_URI = "postgresql://{}:{}@{}/{}".format(DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_NAME)


class PreviewConfig(Config):
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'working')
    DATABASE_USER = os.getenv('DATABASE_USER', 'lc-working-data')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'lcalpha')
    DATABASE_HOST = os.getenv('DATABASE_HOST', 'localhost')
    SQLALCHEMY_DATABASE_URI = "postgresql://{}:{}@{}/{}".format(DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_NAME)
