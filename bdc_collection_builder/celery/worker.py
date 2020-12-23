#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Defines a structure component to run celery worker."""

# Builder
from copy import deepcopy

from .. import create_app
from . import create_celery_app


app = create_app()
celery = create_celery_app(app)


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Calls test('hello') every 10 seconds.
    from .tasks import check_download_periodic
    from ..collections.models import PeriodicTask
    from celery.schedules import crontab

    with app.app_context():
        tasks = PeriodicTask.query().filter(PeriodicTask.enabled).all()

        for task in tasks:
            cron = crontab(**task.crontab) if isinstance(task.crontab, dict) else task.crontab

            sender.add_periodic_task(cron, check_download_periodic.s(periodic_id=task.id), name=f'add every {task.name}')
