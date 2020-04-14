#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Handle Sentinel Download interface."""

import logging
import os
import requests
import time

# Builder
from ...celery.cache import lock_handler
from ..utils import get_credentials
from .clients import sentinel_clients


lock = lock_handler.lock('sentinel_download_lock_4')


def _download(file_path: str, response: requests.Response):
    """Write compressed sentinel output to disk.

    Args:
        file_path - Path to store compressed data
        response - HTTP Response object
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # May throw exception for read-only directory
    stream = open(file_path, 'wb')

    # Read chunks of 2048 bytes
    chunk_size = 2048

    for chunk in response.iter_content(chunk_size):
        stream.write(chunk)

    stream.close()


def get_user():
    """Try to get an idle user to download images.

    Since we are downloading images from Copernicus, you can only have
    two concurrent download per account. In this way, we should handle the
    access to the stack of SciHub accounts defined in `secrets_s2.json`
    in order to avoid download interrupt.

    Returns:
        AtomicUser An atomic user
    """
    user = None

    while lock.locked():
        logging.info('Resource locked....')
        time.sleep(1)

    lock.acquire(blocking=True)
    while user is None:
        user = sentinel_clients.use()

        if user is None:
            logging.info('Waiting for available user to download...')
            time.sleep(5)

    lock.release()

    return user


def download_sentinel_images(scene_id: str, file_path: str, **kwargs):
    """Download sentinel image from Copernicus (compressed data).

    Args:
        scene_id (str) - Sentinel 2 Scene Identifier
        file_path (str) - Path to save download file
    """
    link = kwargs.get('link')

    with get_user() as user:
        try:
            response = requests.get(link, auth=(user.username, user.password), timeout=90, stream=True)
        except requests.exceptions.ConnectionError as e:
            logging.error('Connection error during Sentinel Download')
            raise e

        if response.status_code == 202:
            raise requests.exceptions.HTTPError('Data is offline. {}'.format(response.status_code))

        if response.status_code == 401:
            raise requests.exceptions.RequestException('Invalid credentials for "{}"'.format(user.username))

        if response.status_code >= 403:
            raise requests.exceptions.HTTPError('Invalid sentinel request {}'.format(response.status_code))

        size = int(response.headers['Content-Length'].strip()) / 1024 / 1024

        logging.info('Downloading image {} in {}, user {}, size {} MB'.format(link, file_path, user, size))

        _download(file_path, response)


def download_sentinel_from_creodias(scene_id: str, file_path: str, **kwargs):
    """Download sentinel image from CREODIAS provider.

    Args:
        scene_id Sentinel scene id
        file_path Path to save sentinel
    """
    credentials = get_credentials().get('creodias')

    if credentials is None:
        raise RuntimeError('No credentials set for CREODIAS provider')

    url = 'https://auth.creodias.eu/auth/realms/DIAS/protocol/openid-connect/token'

    params = dict(
        username=credentials.get('username'),
        password=credentials.get('password'),
        client_id='CLOUDFERRO_PUBLIC',
        grant_type='password'
    )

    token_req = requests.post(url, data=params)

    if token_req.status_code != 200:
        raise RuntimeError('Unauthorized')

    token = token_req.json()

    feature_params = dict(
        maxRecords=10,
        processingLevel='LEVEL1C',
        sortParam='startDate',
        sortOrder='descending',
        status='all',
        dataset='ESA-DATASET',
        productIdentifier='%{}%'.format(scene_id)
    )
    feature_url = 'https://finder.creodias.eu/resto/api/collections/Sentinel2/search.json'
    features_response = requests.get(feature_url, params=feature_params)

    if features_response.status_code != 200:
        raise RuntimeError('Invalid request')

    features = features_response.json()

    if len(features.get('features')) > 0:
        link = 'https://zipper.creodias.eu/download/{}?token={}'.format(features['features'][0]['id'], token['access_token'])
        response = requests.get(link, timeout=90, stream=True)

        if response.status_code != 200:
            raise RuntimeError('Could not download {} - {}'.format(response.status_code, scene_id))

        _download(file_path, response)


class CopernicusProvider:
    def name(self):
        return 'Copernicus'

    def __call__(self, scene_id: str, destination: str, **kwargs):
        download_sentinel_images(scene_id, destination, **kwargs)


class CREODIASProvider:
    def name(self):
        return 'CREODIAS'

    def __call__(self, scene_id: str, destination: str, **kwargs):
        download_sentinel_from_creodias(scene_id, destination, **kwargs)
