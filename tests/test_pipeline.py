import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import requests

import numpy as np
import rasterio
from rasterio.transform import from_origin, Affine

from src.core.ndvi_engine import calculate_ndvi
from src.io.downloader import SentinelDownloader
from src.io.raster_wrapper import RasterWrapper
from src.pipeline import process_scene
from src.viz.heatmap_generator import ndvi_to_rgb


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def raster(self, name, data, resolution=10, transform=None):
        path = self.root / name
        with rasterio.open(path, 'w', driver='GTiff', count=1, dtype=data.dtype,
                           height=data.shape[0], width=data.shape[1], crs='EPSG:32648',
                           transform=transform or from_origin(500000, 1100000, resolution, resolution),
                           nodata=0) as dst:
            dst.write(data, 1)
        return str(path)

    def test_ndvi_unsigned_zero_nan_and_mask(self):
        red = np.array([[3, 1, 0, 4]], dtype=np.uint16)
        nir = np.array([[1, 3, 0, 2]], dtype=np.uint16)
        result = calculate_ndvi(red, nir, np.array([[True, True, True, False]]))
        np.testing.assert_allclose(result, [[-.5, .5, np.nan, np.nan]], equal_nan=True)
        self.assertEqual(result.dtype, np.float32)
        np.testing.assert_array_equal(ndvi_to_rgb(result)[:, 0, 2:], 0)
        with self.assertRaises(ValueError):
            calculate_ndvi(red, nir[:, :1])

    def bands(self):
        red = np.full((5, 7), 1000, dtype=np.uint16)
        nir = np.full((5, 7), 3000, dtype=np.uint16)
        scl = np.full((3, 4), 4, dtype=np.uint8)
        scl[0, 0] = 9
        red[4, 6] = 0
        return dict(B04=self.raster('red.tif', red), B08=self.raster('nir.tif', nir),
                    SCL=self.raster('scl.tif', scl, 20))

    def test_windowed_pipeline_matches_expected_and_chunk_sizes(self):
        bands = self.bands()
        expected = np.full((5, 7), .5, dtype=np.float32)
        expected[:2, :2] = np.nan
        expected[4, 6] = np.nan
        for size in (1, 3, 512):
            stats = process_scene(bands, self.root/'out', chunk_size=size)
            self.assertEqual(stats['valid_pixels'], 30)
            self.assertEqual(stats['mean_ndvi'], .5)
            with rasterio.open(stats['ndvi']) as ds:
                np.testing.assert_allclose(ds.read(1), expected, equal_nan=True)
                self.assertEqual(ds.crs.to_epsg(), 32648)
            with rasterio.open(stats['rgb']) as ds:
                self.assertEqual(ds.count, 3)
                np.testing.assert_array_equal(ds.dataset_mask() > 0, np.isfinite(expected))
            self.assertTrue((self.root/'out/local_summary.json').exists())

    def test_scale_offset_and_all_masked(self):
        bands = self.bands()
        stats = process_scene(bands, self.root/'out', calibration={
            k: {'scale': .0001, 'offset': -.05} for k in ('B04', 'B08')})
        self.assertAlmostEqual(stats['mean_ndvi'], 2/3, places=6)
        bands['SCL'] = self.raster('cloud.tif', np.full((3, 4), 9, np.uint8), 20)
        stats = process_scene(bands, self.root/'out')
        self.assertEqual(stats['valid_pixels'], 0)
        self.assertIsNone(stats['mean_ndvi'])
        json.dumps(stats, allow_nan=False)

    def test_grid_mismatch_rejected_and_no_output_published(self):
        bands = self.bands()
        bands['B08'] = self.raster('shift.tif', np.ones((5, 7), np.uint16),
                                   transform=from_origin(500005, 1100000, 10, 10))
        with self.assertRaisesRegex(ValueError, 'grids differ'):
            process_scene(bands, self.root/'out')
        self.assertEqual(list((self.root/'out').iterdir()), [])

    def test_rotated_geometry_and_bad_chunk(self):
        transform = Affine(3, -4, 100, 4, 3, 200)
        path = self.raster('rotated.tif', np.ones((5, 7), np.uint8), transform=transform)
        with RasterWrapper(path) as ds:
            self.assertEqual(ds.get_pixel_size(), (5, 5))
            self.assertEqual(ds.get_bounds(), dict(left=80, right=121, bottom=200, top=243))
            with self.assertRaises(ValueError):
                list(ds.read_chunk(chunk_size=0))
            with self.assertRaises(ValueError):
                ds.pixel_to_coords(0, 0, 'bad')
            self.assertEqual(sum(c.size for c, *_ in ds.read_chunk(chunk_size=3)), 35)

    def item(self, name, tile, cloud):
        item = Mock()
        item.id = name
        item.properties = {'grid:code': tile, 'eo:cloud_cover': cloud}
        return item

    def test_search_all_tiles_and_inclusive_threshold(self):
        catalog = Mock()
        items = [self.item('cloudy', 'A', 20), self.item('clear', 'A', 2), self.item('other', 'B', 10)]
        catalog.search.return_value.items.return_value = items
        d = SentinelDownloader(self.root, catalog=catalog)
        self.assertEqual([i.id for i in d.search([105, 9, 106, 10], '2026-01')], ['clear', 'other'])
        self.assertEqual(catalog.search.call_args.kwargs['query']['eo:cloud_cover'], {'lte': 20})
        with self.assertRaisesRegex(ValueError, 'Multiple tiles'):
            d.search_and_download([105, 9, 106, 10], '2026-01')
        catalog.search.return_value.items.return_value = []
        with self.assertRaisesRegex(ValueError, 'No satellite'):
            d.search([105, 9, 106, 10], '2026-01')

    def test_download_validation_cache_and_corruption(self):
        source = self.raster('source.tif', np.ones((5, 7), np.uint16))
        payload = Path(source).read_bytes()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {'Content-Length': str(len(payload))}
        response.iter_content.side_effect = lambda **kw: iter([payload])
        d = SentinelDownloader(self.root, retries=1)
        target = self.root/'download.tif'
        with patch('src.io.downloader.requests.get', return_value=response) as get:
            d._download_file('https://example.test/a', target)
            d._download_file('https://example.test/a', target)
            self.assertEqual(get.call_count, 1)
            target.write_bytes(b'corrupt')
            d._download_file('https://example.test/a', target)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(target.read_bytes(), payload)
            response.headers['Content-Length'] = str(len(payload)+1)
            with self.assertRaises(OSError):
                d._download_file('https://example.test/b', self.root/'broken.tif')
            self.assertFalse((self.root/'broken.tif').exists())
            self.assertEqual(list(self.root.glob('*.part')), [])

    def test_missing_assets_fail_before_download(self):
        item = self.item('scene', 'A', 0)
        item.assets = {}
        d = SentinelDownloader(self.root)
        with self.assertRaisesRegex(ValueError, 'missing assets'):
            d.download_item(item)

    def test_interrupted_stream_retry_and_cleanup(self):
        source = self.raster('retry-source.tif', np.ones((3, 3), np.uint16))
        payload = Path(source).read_bytes()
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.headers = {}
        def interrupted():
            yield payload[:20]
            raise requests.ConnectionError('interrupted stream')
        response.iter_content.side_effect = [interrupted(), iter([payload])]
        d = SentinelDownloader(self.root, retries=2)
        with patch('src.io.downloader.requests.get', return_value=response) as get, \
                patch('src.io.downloader.time.sleep'):
            target = self.root/'retry.tif'
            d._download_file('https://example.test/retry', target)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(list(self.root.glob('*.part')), [])

    def test_scl_partial_extent_is_masked(self):
        bands = self.bands()
        bands['SCL'] = self.raster('small-scl.tif', np.full((1, 1), 4, np.uint8), 20)
        result = process_scene(bands, self.root/'out', chunk_size=3)
        self.assertEqual(result['valid_pixels'], 4)


if __name__ == '__main__':
    unittest.main()
