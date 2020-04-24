#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Defines a structure component to run celery worker."""

# Python Native
import logging
# 3rdparty
from celery.signals import celeryd_after_setup, worker_shutdown
# Builder
from bdc_collection_builder import create_app
from bdc_collection_builder.celery import create_celery_app
from ..utils import finalize_factories, initialize_factories


app = create_app()
celery = create_celery_app(app)


@celeryd_after_setup.connect
def on_celery_ready(*args, **kwargs):
    """Signal handler to identify when celery is loaded.

    Tries to initialize Collection Builder factories.
    """
    initialize_factories()


@worker_shutdown.connect
def on_shutdown_release_locks(sender, **kwargs):
    """Signal handler of Celery Worker shutdown.

    Tries to release Redis Lock if there is.
    """
    logging.info('Turning off Celery...')
    finalize_factories()
