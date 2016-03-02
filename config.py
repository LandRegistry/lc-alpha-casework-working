import os


class Config(object):
    DEBUG = os.getenv('DEBUG', True)
    APPLICATION_NAME = 'lc-casework-api'
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'working')
    DATABASE_USER = os.getenv('DATABASE_USER', 'lc-working-data')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'lcalpha')
    DATABASE_HOST = os.getenv('DATABASE_HOST', 'localhost')
    SQLALCHEMY_DATABASE_URI = "postgresql://{}:{}@{}/{}".format(DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST, DATABASE_NAME)
    ALLOW_DEV_ROUTES = os.getenv('ALLOW_DEV_ROUTES', True)
    MQ_USERNAME = os.getenv("MQ_USERNAME", "mquser")
    MQ_PASSWORD = os.getenv("MQ_PASSWORD", "mqpassword")
    MQ_HOSTNAME = os.getenv("MQ_HOST", "localhost")
    MQ_PORT = os.getenv("MQ_PORT", "5672")
    ERROR_QUEUE_NAME = os.getenv('ERROR_QUEUE_NAME', "errors")
    TEMP_DIRECTORY = os.getenv('TEMP_DIRECTORY', '/vagrant')
    LAND_CHARGES_URI = os.getenv('LAND_CHARGES_URL', 'http://localhost:5004')
    LEGACY_ADAPTER_URI = os.getenv('LEGACY_ADAPTER_URL', 'http://localhost:5007')
    RESULT_GENERATE_URI = os.getenv('RESULTS_GENERATE_URL', 'http://10.0.2.2:5016')
    # IMAGE_DIRECTORY = '/home/vagrant/interim/'
