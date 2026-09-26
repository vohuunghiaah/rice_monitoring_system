import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import Affine

from src.core.spatial import load_polygons, pixel_centers, polygon_mask, sample_nearest
from src.io.downloader import SentinelDownloader
from src.mosaic import mosaic_scenes


class MosaicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def raster(self, name, values, transform=None, crs='EPSG:6933'):
        path = self.root/f'{name}.tif'
        values = np.asarray(values, dtype=np.float32)
        with rasterio.open(path, 'w', driver='GTiff', count=1, dtype='float32',
                           width=values.shape[1], height=values.shape[0], nodata=np.nan,
                           crs=crs, transform=transform or Affine(10, 0, 0, 0, -10, 20)) as ds:
            ds.write(values, 1)
        return path

    def summary(self, name, values, day='2026-02-03', cloud=10, transform=None, crs='EPSG:6933'):
        path = self.root/f'{name}.json'
        path.write_text(json.dumps(dict(scene_id=name, ndvi=str(self.raster(name, values, transform, crs)),
                                        datetime=day, cloud_cover=cloud)))
        return path

    def aoi(self, xmin, ymin, xmax, ymax, hole=None):
        projection = Transformer.from_crs(6933, 4326, always_xy=True)
        def ring(x0, y0, x1, y1):
            return [projection.transform(x, y) for x, y in
                    [(x0,y0), (x1,y0), (x1,y1), (x0,y1), (x0,y0)]]
        rings = [ring(xmin, ymin, xmax, ymax)]
        if hole:
            rings.append(ring(*hole))
        path = self.root/'aoi.geojson'
        path.write_text(json.dumps(dict(type='Polygon', coordinates=rings)))
        return path

    def test_overlap_priority_nodata_fallback_and_unique_area(self):
        a = self.summary('a', [[.2, np.nan], [.2, .2]], cloud=20)
        b = self.summary('b', [[.8, .8], [.8, .8]], day='2026-02-04', cloud=0)
        for chunk in (1, 512):
            result = mosaic_scenes([b, a, a], self.root/'out', '2026-02-03', chunk_size=chunk)
            self.assertEqual(result['valid_pixels'], 4)
            self.assertAlmostEqual(result['observed_area_ha'], .04)
            with rasterio.open(result['ndvi']) as ds:
                np.testing.assert_allclose(ds.read(1), [[.2, .8], [.2, .2]])
            with rasterio.open(result['source_index']) as ds:
                np.testing.assert_array_equal(ds.read(1), [[1, 2], [1, 1]])
            self.assertEqual([s['contributed_pixels'] for s in result['sources']], [3, 1])

    def test_full_aoi_counts_unobserved_area_and_hole(self):
        source = self.summary('a', [[.5, .5], [.5, .5]])
        aoi = self.aoi(0, 0, 40, 20, hole=(0, 0, 10, 10))
        result = mosaic_scenes([source], self.root/'out', '2026-02-03', aoi=aoi)
        self.assertEqual(result['roi_pixels'], 7)
        self.assertEqual(result['valid_pixels'], 3)
        self.assertAlmostEqual(result['coverage_fraction'], 3/7)
        self.assertAlmostEqual(result['roi_area_ha'], .07)

    def test_rice_mask_selection(self):
        source = self.summary('a', [[.5, .5], [.5, .5]])
        mask = self.raster('rice', [[1, 0], [np.nan, 1]])
        result = mosaic_scenes([source], self.root/'out', '2026-02-03', rice_mask=mask)
        self.assertEqual(result['valid_pixels'], 2)
        self.assertAlmostEqual(result['observed_area_ha'], .02)
        self.assertEqual(result['mask_unknown_pixels'], 1)
        self.assertEqual(result['mask_coverage_fraction'], .75)

    def test_reproject_utm48_and_49_to_equal_area(self):
        # Both UTM images cover the same point near the zone boundary.
        summaries = []
        for i, epsg in enumerate((32648, 32649)):
            x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(108, 10)
            summaries.append(self.summary(str(epsg), np.full((20, 20), .2+i*.5),
                                          transform=Affine(100, 0, x-1000, 0, -100, y+1000),
                                          crs=f'EPSG:{epsg}', cloud=i*10))
        result = mosaic_scenes(summaries, self.root/'out', '2026-02-03', resolution=100)
        self.assertGreater(result['valid_pixels'], 300)
        with rasterio.open(result['ndvi']) as ds:
            self.assertEqual(ds.crs.to_epsg(), 6933)
            px, py = Transformer.from_crs(4326, 6933, always_xy=True).transform(108, 10)
            row, col = ds.index(px, py)
            self.assertAlmostEqual(float(ds.read(1)[row, col]), .2, places=6)
        self.assertEqual(sum(s['contributed_pixels'] for s in result['sources']), result['valid_pixels'])

    def test_sparse_sampler_fallback_matches_rectangle(self):
        path = self.raster('grid', np.arange(180000, dtype=np.float32).reshape(300, 600))
        projection = Transformer.from_crs(6933, 6933, always_xy=True)
        with rasterio.open(path) as ds:
            x, y = pixel_centers(ds.transform, rasterio.windows.Window(0, 0, 600, 300))
            dense = sample_nearest(ds, x, y, projection)
            sparse = sample_nearest(ds, x, y, projection, max_read_pixels=1)
            np.testing.assert_array_equal(dense, sparse)

    def test_invalid_date_budget_aoi_and_missing_datetime(self):
        source = self.summary('a', [[.5]])
        with self.assertRaisesRegex(ValueError, 'tolerance'):
            mosaic_scenes([source], self.root/'out', '2026-03-01', max_day_gap=0)
        with self.assertRaisesRegex(ValueError, 'Output has'):
            mosaic_scenes([source], self.root/'out', '2026-02-03', resolution=1, max_pixels=2)
        with self.assertRaisesRegex(ValueError, 'does not intersect'):
            mosaic_scenes([source], self.root/'out', '2026-02-03', aoi=self.aoi(100, 100, 200, 200))
        data = json.loads(source.read_text())
        data['datetime'] = None
        source.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'acquisition'):
            mosaic_scenes([source], self.root/'out', '2026-02-03')

    def test_polygon_multipolygon_and_dateline(self):
        polygon = [[[0,0], [2,0], [2,2], [0,2], [0,0]]]
        path = self.root/'poly.json'
        path.write_text(json.dumps(dict(type='MultiPolygon', coordinates=[polygon])))
        mask = polygon_mask(np.array([1, 3]), np.array([1, 1]), load_polygons(path))
        np.testing.assert_array_equal(mask, [True, False])
        path.write_text(json.dumps(dict(type='Polygon', coordinates=[[[179,0],[-179,0],[-179,1],[179,0]]])))
        with self.assertRaises(ValueError):
            load_polygons(path)

    def test_discovery_prefers_date_before_cloud(self):
        catalog = Mock()
        items = []
        for identifier, day, cloud in [('near', '2026-02-03', 20), ('clear', '2026-02-05', 0)]:
            item = Mock(id=identifier, properties={'grid:code':'A', 'datetime':day, 'eo:cloud_cover':cloud})
            items.append(item)
        catalog.search.return_value.items.return_value = items
        result = SentinelDownloader(self.root, catalog=catalog).search(
            [105,9,106,10], '2026-02-01/2026-02-28', target_date='2026-02-03')
        self.assertEqual(result[0].id, 'near')


if __name__ == '__main__':
    unittest.main()
