"""STAC discovery and validated atomic downloads."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import time
from datetime import date

import rasterio
import requests
from pystac_client import Client
from pystac_client.stac_api_io import StacApiIO

TARGET_BANDS = {'B04': 'red', 'B08': 'nir', 'SCL': 'scl'}


class SentinelDownloader:
    def __init__(self, download_dir='data/01_raw', catalog=None, retries=3):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.catalog = catalog
        self.retries = retries
        if retries < 1:
            raise ValueError('retries must be positive')

    def search(self, bbox, time_range, cloud_cover=20, target_date=None, max_day_gap=3):
        if (len(bbox) != 4 or not -180 <= bbox[0] < bbox[2] <= 180
                or not -90 <= bbox[1] < bbox[3] <= 90):
            raise ValueError('bbox must be west south east north in WGS84')
        if not 0 <= cloud_cover <= 100:
            raise ValueError('cloud_cover must be in [0, 100]')
        target = date.fromisoformat(target_date) if target_date else None
        if max_day_gap < 0:
            raise ValueError('max_day_gap must be nonnegative')
        if self.catalog is None:
            self.catalog = Client.open('https://earth-search.aws.element84.com/v1',
                                       stac_io=StacApiIO(timeout=60, max_retries=3))
        search = self.catalog.search(
            collections=['sentinel-2-l2a'], bbox=bbox, datetime=time_range,
            query={'eo:cloud_cover': {'lte': cloud_cover}},
            sortby=[{'field': 'properties.eo:cloud_cover', 'direction': 'asc'}])
        selected = {}
        for item in search.items():
            p = item.properties
            tile = p.get('grid:code') or p.get('s2:mgrs_tile')
            if not tile:
                parts = item.id.split('_')
                if len(parts) < 2 or not re.fullmatch(r'\d{2}[A-Z]{3}', parts[1]):
                    raise ValueError(f'Cannot determine tile for {item.id}')
                tile = parts[1]
            gap = 0
            if target:
                acquired = date.fromisoformat(p['datetime'][:10])
                gap = abs((acquired-target).days)
                if gap > max_day_gap:
                    continue
            rank = (gap, p.get('eo:cloud_cover', 100), item.id)
            if tile not in selected or rank < selected[tile][0]:
                selected[tile] = (rank, item)
        if not selected:
            raise ValueError('No satellite data matching the parameters was found')
        return [selected[t][1] for t in sorted(selected)]

    def search_and_download(self, bbox, time_range, cloud_cover=20):
        items = self.search(bbox, time_range, cloud_cover)
        if len(items) != 1:
            raise ValueError('Multiple tiles found; use download_scenes or run CLI')
        return self.download_item(items[0])['bands']

    def download_scenes(self, bbox, time_range, cloud_cover=20, target_date=None, max_day_gap=3):
        for item in self.search(bbox, time_range, cloud_cover, target_date, max_day_gap):
            logging.info('Selected scene %s', item.id)
            yield self.download_item(item)

    def download_item(self, item):
        missing = set(TARGET_BANDS.values()) - item.assets.keys()
        if missing:
            raise ValueError(f'Scene {item.id} missing assets: {sorted(missing)}')
        if not re.fullmatch(r'[\w.-]+', item.id) or item.id in ('.', '..'):
            raise ValueError('Unsafe scene identifier')
        scene = {'id': item.id, 'bands': {}, 'calibration': {},
                 'datetime': item.properties.get('datetime'),
                 'cloud_cover': item.properties.get('eo:cloud_cover')}
        for band, key in TARGET_BANDS.items():
            asset = item.assets[key]
            path = self.download_dir / f'{item.id}_{band}.tif'
            self._download_file(asset.href, path)
            scene['bands'][band] = str(path.resolve())
            metadata = asset.extra_fields.get('raster:bands', [{}])[0]
            scene['calibration'][band] = {'scale': metadata.get('scale', 1),
                                         'offset': metadata.get('offset', 0)}
        self._write_json(self.download_dir / f'{item.id}.json', scene)
        return scene

    @staticmethod
    def _write_json(path, value):
        fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.part')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(value, stream, indent=2, allow_nan=False)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _digest(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest()

    def _download_file(self, url, dest_path):
        path = Path(dest_path)
        receipt = path.with_suffix(path.suffix + '.json')
        if path.exists() and receipt.exists():
            try:
                info = json.loads(receipt.read_text(encoding='utf-8'))
                if info['url'] == url and info['sha256'] == self._digest(path):
                    logging.info('Verified cache: %s', path)
                    return
            except (ValueError, KeyError):
                pass
        for attempt in range(self.retries):
            logging.info('Downloading %s (attempt %s/%s)', path, attempt + 1, self.retries)
            fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.part')
            os.close(fd)
            try:
                with requests.get(url, stream=True, timeout=(15, 120),
                                  headers={'Accept-Encoding': 'identity'}) as response:
                    response.raise_for_status()
                    size = 0
                    with open(temporary, 'wb') as stream:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            stream.write(chunk)
                            size += len(chunk)
                    expected = response.headers.get('Content-Length')
                    if not size or (expected is not None and size != int(expected)):
                        raise IOError('Incomplete download')
                with rasterio.Env(GDAL_CACHEMAX=32 * 1024 * 1024), rasterio.open(temporary) as dataset:
                    if dataset.count != 1 or dataset.crs is None:
                        raise ValueError('Expected georeferenced single-band raster')
                    for _, window in dataset.block_windows(1):
                        dataset.read(1, window=window)
                digest = self._digest(temporary)
                os.replace(temporary, path)
                self._write_json(receipt, {'url': url, 'sha256': digest, 'bytes': size})
                return
            except (requests.RequestException, OSError) as exc:
                logging.warning('Download failed for %s: %s', path, exc)
                if attempt + 1 == self.retries:
                    raise
                time.sleep(2 ** attempt)
            finally:
                Path(temporary).unlink(missing_ok=True)
