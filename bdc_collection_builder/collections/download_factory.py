import logging
from pathlib import Path
from requests.exceptions import RequestException, HTTPError
from typing import Tuple


class DownloadFactory:
    """Define a factory to download from the well-known providers.

    Basically, it consists in a cached list grouped by scene types.
    Currently, it supports both Sentinel 2 and Landsat 8.
    """

    downloaders = dict(
        sentinel=list(),
        landsat=list()
    )

    def initialize(self):
        from .sentinel.download import CopernicusProvider, CREODIASProvider
        from .sentinel.onda import ONDAProvider
        from .landsat.aws import AWSProvider
        from .landsat.download import EarthExplorerProvider

        if len(self.downloaders) == 0:
            # By default, use Copernicus
            self.downloaders['sentinel'].append(CopernicusProvider())
            # On error, try on ONDA
            self.downloaders['sentinel'].append(ONDAProvider())
            # Download from CREODIAS only when not found previous providers
            self.downloaders['sentinel'].append(CREODIASProvider())
            # Download Landsat from AWS Planet
            self.downloaders['landsat'].append(AWSProvider())
            # Download Landsat from EarthExplorer
            self.downloaders['landsat'].append(EarthExplorerProvider())

    def download(self, scene_id: str, destination: str, **kwargs) -> Tuple[str, str]:
        """Try to download a scene from well-known providers.

        Raises:
            HTTPError when scene is not found on the well-known providers.

        Args:
            scene_id: Product scene identifier
            destinaton: Path to store file
            kwargs: Extra parameters used along downloaders.

        Returns:
            A tuple of str representing both link used and path to the file.
        """
        destination = Path(destination)
        for downloader in self.downloaders:
            try:
                logging.info('Trying to download {} from {}'.format(scene_id, downloader.name()))
                downloader(scene_id, destination, **kwargs)
            except RequestException:
                continue
            except BaseException as e:
                logging.warning('Unexpected exception on downloader: {}'.format(str(e)))
                continue

            if destination.exists():
                break  # file has been downloaded.

        if not destination.exists():
            raise HTTPError('Could not download {} from well-known providers.'.format(scene_id))


factory = DownloadFactory()
