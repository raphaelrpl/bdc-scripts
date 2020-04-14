#
# This file is part of Brazil Data Cube Collection Builder.
# Copyright (C) 2019-2020 INPE.
#
# Brazil Data Cube Collection Builder is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#

"""Define module to download Landsat 8 scenes from AWS."""
# Python
import logging
import os
import tarfile
# 3rdparty
import rasterio
import requests
from bdc_core.decorators.utils import working_directory
from .download import _download_file
from .publish import BAND_MAP_DN


def download_from_aws(scene_id: str, destination: str, compressed_path: str = None, chunk_size: int = 512*1024):
    """Download Landsat 8 from public AWS bucket.

    After files downloaded, it compresses into SCENE_ID.tar.gz to act like USGS provider.

    Further details on https://docs.opendata.aws/landsat-pds/readme.html

    Args:
        scene_id - Lansat 8 scene id. Example: LC08_L1TP_139045_20170304_20170316_01_T1.
        destination - Path to store downloaded file.
        chunk_size - Request chunk size download. Default is 512kb.

    Returns:
        Tuple with path where file was saved and AWS link downloaded.
    """
    from .publish import BAND_MAP_DN

    if compressed_path is None:
        compressed_path = destination

    os.makedirs(compressed_path, exist_ok=True)

    compressed_path = os.path.join(compressed_path, '{}.tar.gz'.format(scene_id))

    files = ['{}_{}.TIF'.format(scene_id, b) for b in BAND_MAP_DN.values()]
    files.append('{}_MTL.txt'.format(scene_id))
    files.append('{}_ANG.txt'.format(scene_id))

    pathrow = scene_id.split('_')[2]

    path, row = pathrow[:3], pathrow[3:]

    os.makedirs(destination, exist_ok=True)

    url = 'https://landsat-pds.s3.amazonaws.com/c1/L8/{}/{}/{}'.format(path, row, scene_id)

    for f in files:
        stream = requests.get('{}/{}'.format(url, os.path.basename(f)), timeout=90, stream=True)

        # Throw for any HTTP error code
        stream.raise_for_status()

        logging.debug('Downloading {}...'.format(f))

        digital_number_file_path = os.path.join(destination, f)
        _download_file(stream, digital_number_file_path, byte_size=chunk_size)

        if f.lower().endswith('.tif'):
            # Remove compression and Tiled order from AWS files in order
            # to espa-science work properly.
            # https://github.com/USGS-EROS/espa-surface-reflectance/issues/76
            remove_tile_compression(digital_number_file_path)

    try:
        logging.debug('Compressing {}'.format(compressed_path))
        # Create compressed file and make available
        with tarfile.open(compressed_path, 'w:gz') as compressed_file:
            with working_directory(destination):
                for f in files:
                    compressed_file.add(f)

    except BaseException:
        logging.error('Could not compress {}.tar.gz'.format(scene_id), exc_info=True)

        raise

    return compressed_path, url


def remove_tile_compression(tiff_file_path: str, destination: str = None) -> str:
    """Generate new data set in disk without compression and mark as ``TILED=NO``.

    Warning:
        Beware when no destination file is set, it overwrites the origin file.
        It may be corrupted on error.

    Args:
        tiff_file_path - Path to the input data set
        destination - Destination file name. Default is input.

    Returns:
        Path to the generated file.
    """
    if destination is None:
        destination = tiff_file_path

    with rasterio.Env():
        with rasterio.open(tiff_file_path, 'r') as source_data_set:
            profile = source_data_set.profile
            raster = source_data_set.read(1)

        profile.pop('compress', '')
        profile.update(dict(
            tiled=False
        ))

        with rasterio.open(destination, 'w', **profile) as target_data_set:
            target_data_set.write_band(1, raster)

    return tiff_file_path


class AWSProvider:
    def name(self):
        return 'AWS Planet'

    def __call__(self, scene_id: str, destination: str, **kwargs):
        digital_number_dir = kwargs['digital_number_dir']
        download_from_aws(scene_id, digital_number_dir, destination)
