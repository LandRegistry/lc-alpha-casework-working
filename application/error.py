from application import app
import kombu
import logging


class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
        super(ValidationError, self).__init__(value)

    def __str__(self):
        return repr(self.value)


class CaseworkAPIError(Exception):
    def __init__(self, value):
        self.value = value
        super(CaseworkAPIError, self).__init__(value)

    def __str__(self):
        return self.value


def raise_error(error):
    hostname = "amqp://{}:{}@{}:{}".format(app.config['MQ_USERNAME'], app.config['MQ_PASSWORD'],
                                           app.config['MQ_HOSTNAME'], app.config['MQ_PORT'])
    connection = kombu.Connection(hostname=hostname)
    producer = connection.SimpleQueue('errors')
    producer.put(error)
    logging.warning('Error successfully raised.')
