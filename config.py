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
    LAND_CHARGES_URI = 'http://localhost:5004'
    DOCUMENT_API_URI = 'http://localhost:5014'
    LEGACY_ADAPTER_URI = 'http://localhost:5007'
    ALLOW_DEV_ROUTES = True


class PreviewConfig(Config):
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'working')
    DATABASE_USER = os.getenv('DATABASE_USER', 'lc-working-data')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'lcalpha')
    DATABASE_HOST = os.getenv('DATABASE_HOST', 'localhost')
    SQLALCHEMY_DATABASE_URI = "postgresql://{}:{}@{}/{}".format(DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_NAME)
    LAND_CHARGES_URI = 'http://localhost:5004'
    LEGACY_ADAPTER_URI = 'http://localhost:5007'
    DOCUMENT_API_URI = 'http://localhost:5014'
    ALLOW_DEV_ROUTES = True
