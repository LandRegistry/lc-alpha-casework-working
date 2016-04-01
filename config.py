import os


class Config(object):
    DEBUG = os.getenv('DEBUG', True)
    APPLICATION_NAME = 'lc-casework-api'

    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "postgresql://lc-working-data:lcalpha@localhost/working")
    AMQP_URI = os.getenv("AMQP_URI", "amqp://mquser:mqpassword@localhost:5672")
    PSQL_CONNECTION = os.getenv("PSQL_CONNECTION", "dbname='working' user='lc-working-data' host='localhost' password='lcalpha'")

    ALLOW_DEV_ROUTES = os.getenv('ALLOW_DEV_ROUTES', True)
    ERROR_QUEUE_NAME = os.getenv('ERROR_QUEUE_NAME', "errors")
    TEMP_DIRECTORY = os.getenv('TEMP_DIRECTORY', '/tmp')
    TEMP_DIR = os.getenv('TMPDIR', '/tmp')
    LAND_CHARGES_URI = os.getenv('LAND_CHARGES_URL', 'http://localhost:5004')
    LEGACY_ADAPTER_URI = os.getenv('LEGACY_ADAPTER_URL', 'http://localhost:5007')  # VM
    #LEGACY_ADAPTER_URI = os.getenv('LEGACY_ADAPTER_URL', 'http://10.0.2.2:15007')   # Development IDE
    RESULT_GENERATE_URI = os.getenv('RESULTS_GENERATE_URL', 'http://10.0.2.2:5016')
    # IMAGE_DIRECTORY = '/home/vagrant/interim/'
    AUDIT_LOG_FILENAME = os.getenv("AUDIT_LOG_FILENAME", "/vagrant/logs/casework-api/audit.log")
