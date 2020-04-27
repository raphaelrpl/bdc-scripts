#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Define global functions used in Collection Builder."""

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
    """Finalize the Collection Builder factories."""
    from .celery.cache import lock_handler

    lock_handler.release_all()
