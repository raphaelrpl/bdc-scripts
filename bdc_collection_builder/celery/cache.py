#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Cache utilities used on celery context."""

import logging
import redis
from bdc_collection_builder.config import Config


class RedisService:
    """Define an abstraction for Redis interface."""
    _client = None

    def initialize(self, uri=Config.REDIS_URL):
        """Initialize a connection with Redis."""
        self._client = redis.Redis.from_url(Config.REDIS_URL)

    @property
    def client(self):
        """Retrieve redis instance."""
        return self._client


redis_service = RedisService()


class LockHandler:
    """Control the life cycle of Redis Locks on Celery.

    Releases all locks when instance is destroyed
    """

    def __init__(self):
        """Build a lock handler instance."""
        self._locks = []

    def lock(self, name: str, **options):
        """Locks Redis globally.

        Args:
            name - Lock name
            **options - Extra optional parameters
        """
        lock = redis_service.client.lock(name, **options)

        self._locks.append(lock)

        return lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Object exit context.

        Release all locks.
        """
        self.release_all()

    def __del__(self):
        """Release redis locks on destructor."""
        self.release_all()

    def release_all(self):
        """Releases all redis locks."""
        logging.debug('Releasing locks...')
        for lock in self._locks:
            if lock.locked():
                try:
                    lock.release()
                except:
                    logging.debug('Could not release lock!')


lock_handler = LockHandler()
