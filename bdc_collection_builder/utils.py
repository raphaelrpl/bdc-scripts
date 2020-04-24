import logging
from json import loads as json_parser
from os import path as resource_path
from .config import CURRENT_DIR


def get_credentials():
    """Retrieve global secrets with credentials."""
    file = resource_path.join(resource_path.dirname(CURRENT_DIR), 'secrets.json')

    if not resource_path.exists(file):
        raise FileNotFoundError('The file "{}" does not exists'.format(file))

    with open(file) as f:
        return json_parser(f.read())


def initialize_factories():
    """Initialize Brazil Data Cube Collection Builder factories."""
    from .celery.cache import redis_service
    from .collections.sentinel.clients import sentinel_clients

    redis_service.initialize()
    sentinel_clients.initialize()

    logging.info('Factories loaded.')


def finalize_factories():
    from .celery.cache import lock_handler

    lock_handler.release_all()
