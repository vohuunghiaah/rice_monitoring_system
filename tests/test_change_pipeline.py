"""Contract, geospatial reconstruction and numerical regression tests."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

import numpy as np
import rasterio
from affine import Affine

from src.raster_engine import Band, Scene, RasterEngine, normalized_difference, erode_clear
from src.change_pipeline import predict_raster
from src.change_metrics import ChangeMetrics


class ChangePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.transform = Affine(10, 2, 500000, 1, -10, 1100000)

    def tearDown(self):
        self.temp.cleanup()

    def raster(self, name, values, transform=None):
        path = self.root/name
        with rasterio.open(path, 'w', driver='GTiff', width=values.shape[1],
                           height=values.shape[0], count=1, dtype=values.dtype,
                           transform=transform or self.transform, crs='EPSG:32648', nodata=0) as ds:
            ds.write(values, 1)
        return path

    def engine(self, quality=False):
        values = np.arange(1, 36, dtype=np.float32).reshape(5, 7)
        path = self.raster('red.tif', values)
        nir = self.raster('nir.tif', values*3)
        q = np.ones((5, 7), np.uint8)
        q[0, 0] = 0
        scene = Scene('T1', (Band('B04', path), Band('B08', nir)),
                      self.raster('quality.tif', q) if quality else None)
        return RasterEngine(scene, Scene('T2', scene.bands, scene.quality), core_size=4, halo=2)

    def test_owned_patches_affine_indices_and_complete_coverage(self):
        engine = self.engine()
        patches = list(engine)
        self.assertEqual(len(patches), 4)
        coverage = np.zeros((5, 7), int)
        for patch in patches:
            m = patch.metadata
            r, c = int(m.window.row_off), int(m.window.col_off)
            h, w = int(m.window.height), int(m.window.width)
            coverage[r:r+h, c:c+w] += 1
            self.assertEqual(m.sub_affine*(m.halo, m.halo), self.transform*(c, r))
            np.testing.assert_allclose(patch.t1[-1][patch.valid], .5)
        np.testing.assert_array_equal(coverage, 1)
        self.assertFalse(np.shares_memory(patches[0].t1, patches[1].t1))

    def test_reconstruction_unknown_edges_and_atomic_failure(self):
        engine = self.engine(quality=True)
        output = self.root/'result.tif'
        predict_raster(engine, lambda p: (p.t2[0] >= 18).astype(np.float32), output)
        with rasterio.open(output) as ds:
            expected = (np.arange(1, 36).reshape(5, 7) >= 18).astype(np.uint8)
            expected[0, 0] = 255
            np.testing.assert_array_equal(ds.read(1), expected)
            self.assertEqual(ds.transform, self.transform)
            self.assertEqual(ds.crs.to_epsg(), 32648)
            self.assertEqual(ds.nodata, 255)
        previous = output.read_bytes()
        with self.assertRaises(ValueError):
            predict_raster(engine, lambda p: np.zeros((1, 1)), output)
        self.assertEqual(previous, output.read_bytes())
        self.assertFalse(list(self.root.glob('.change-*')))

    def test_misaligned_inputs_rejected(self):
        engine = self.engine()
        shifted = self.raster('shift.tif', np.ones((5, 7), np.float32),
                              self.transform*Affine.translation(.5, 0))
        scene = Scene('shift', (Band('B04', shifted), Band('B08', shifted)))
        with self.assertRaisesRegex(ValueError, 'grids differ'):
            next(iter(RasterEngine(engine.scenes[0], scene)))

    def test_raw_scl_is_rejected(self):
        engine = self.engine()
        scl = self.raster('scl.tif', np.full((5, 7), 9, np.uint8))
        scene = Scene('scl', engine.scenes[0].bands, scl)
        with self.assertRaisesRegex(ValueError, 'binary'):
            next(iter(RasterEngine(scene, scene)))

    def test_quality_buffer_consistent_across_core_sizes(self):
        engine = self.engine()
        clear = np.ones((5, 7), np.uint8)
        clear[2, 3] = 0
        quality = self.raster('clear.tif', clear)
        scene = Scene('clear', engine.scenes[0].bands, quality)
        expected = erode_clear(clear.astype(bool), 1)
        for size in (1, 3, 16):
            output = self.root/f'buffer-{size}.tif'
            predict_raster(RasterEngine(scene, scene, size, 0, quality_radius=1),
                           lambda p: np.ones_like(p.valid, np.float32), output)
            with rasterio.open(output) as ds:
                np.testing.assert_array_equal(ds.read(1) != 255, expected)
        self.assertEqual(np.count_nonzero(expected), 6)

    def test_interleaved_iterators_do_not_leave_gdal_environment(self):
        engine = self.engine()
        with rasterio.Env(GDAL_CACHEMAX=123456):
            a, b = iter(engine), iter(engine)
            next(a)
            next(b)
            a.close()
            list(b)
            self.assertEqual(rasterio.env.get_gdal_config('GDAL_CACHEMAX'), 123456)

    def test_bad_engine_parameters_fail_early(self):
        engine = self.engine()
        for kwargs in ({'ndvi': ()}, {'ndvi': ('B04',)}, {'ndvi': ('B04', 'B04')},
                       {'quality_radius': -1}, {'quality_radius': 1}, {'core_size': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RasterEngine(*engine.scenes, **kwargs)
        bad = Scene('bad', (Band('B04', self.root/'red.tif', 1e100),))
        with self.assertRaises(ValueError):
            RasterEngine(bad, bad, ndvi=None)

    def test_lock_sidecars_and_input_overwrite_are_safe(self):
        from src.change_pipeline import output_lock
        engine = self.engine()
        output = self.root/'protected.tif'
        predictor = lambda p: np.zeros_like(p.valid, np.float32)
        with output_lock(output):
            with self.assertRaisesRegex(ValueError, 'locked'):
                predict_raster(engine, predictor, output)
            self.assertTrue(Path(str(output)+'.lock').exists())
        self.assertFalse(Path(str(output)+'.lock').exists())
        Path(str(output)+'.msk').write_bytes(b'existing sidecar')
        with self.assertRaisesRegex(ValueError, 'sidecars'):
            predict_raster(engine, predictor, output)
        self.assertFalse(Path(str(output)+'.lock').exists())
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            predict_raster(engine, predictor, engine.scenes[0].bands[0].path)

    def test_incomplete_or_corrupt_metadata_cannot_publish(self):
        from dataclasses import replace
        engine = self.engine()
        class BrokenEngine(RasterEngine):
            def __iter__(self):
                iterator = super().__iter__()
                try:
                    yield next(iterator)
                finally:
                    iterator.close()
        output = self.root/'broken.tif'
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            predict_raster(BrokenEngine(*engine.scenes, 4, 2),
                           lambda p: np.ones_like(p.valid, np.float32), output)
        self.assertFalse(output.exists())
        class CorruptEngine(RasterEngine):
            def __iter__(self):
                for pair in super().__iter__():
                    pair.metadata = replace(pair.metadata, sub_affine=Affine.identity())
                    yield pair
        with self.assertRaisesRegex(ValueError, 'metadata'):
            predict_raster(CorruptEngine(*engine.scenes, 4, 2),
                           lambda p: np.ones_like(p.valid, np.float32), output)
        self.assertFalse(output.exists())

    def test_kernel_negative_zero_and_aliasing(self):
        a = np.array([1, 0, 1, np.nan], np.float32)
        b = np.array([3, 0, -1, 1], np.float32)
        out, work = np.empty_like(a), np.empty_like(a)
        normalized_difference(a, b, out, work)
        np.testing.assert_allclose(out, [-.5, np.nan, np.nan, np.nan], equal_nan=True)
        with self.assertRaises(ValueError):
            normalized_difference(a, b, a, work)

    def test_global_metrics_and_undefined_cases(self):
        metric = ChangeMetrics()
        p = np.array([.9, .8, .2, .1])
        y = np.array([1, 0, 1, 0])
        metric.update(p[:2], y[:2], np.ones(2, bool))
        metric.update(p[2:], y[2:], np.ones(2, bool))
        self.assertAlmostEqual(metric.compute()['change_iou'], 1/3)
        self.assertAlmostEqual(metric.compute()['pr_auc_ap_histogram'], 5/6)
        self.assertIsNone(ChangeMetrics().compute()['change_iou'])
        self.assertIsNone(ChangeMetrics().compute()['pr_auc_ap_histogram'])
        self.assertEqual(metric.compute()['precision'], .5)
        self.assertEqual(metric.compute()['recall'], .5)
        with self.assertRaises(ValueError):
            metric.update(p, y, np.array([1, 1, np.nan, 0]))

    def test_manifest_validation(self):
        import json
        from src.change_cli import load_engine
        path = self.root/'bad.json'
        for manifest in ([], {}, {'core_size': 2.5}, {'halo': True}, {'ndvi': []},
                         {'ndvi': 'B04'}, {'t1': {'bands': [None]}}):
            path.write_text(json.dumps(manifest), encoding='utf-8')
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                load_engine(path)

    def test_all_unknown_skips_predictor(self):
        engine = self.engine()
        empty = self.raster('empty.tif', np.zeros((5, 7), np.uint8))
        scene = Scene('cloud', engine.scenes[0].bands, empty)
        def fail(_):
            raise AssertionError('All-invalid patches should bypass inference')
        output = predict_raster(RasterEngine(scene, scene, 4, 2), fail, self.root/'unknown.tif')
        with rasterio.open(output) as ds:
            np.testing.assert_array_equal(ds.read(1), 255)

    @unittest.skipUnless(importlib.util.find_spec('torch'), 'Install requirements-vision.txt')
    def test_cli_with_explicit_synthetic_checkpoint(self):
        import json
        import sys
        from unittest.mock import patch
        import torch
        from src.vision_core import SiameseUNet
        from src.change_cli import main
        engine = self.engine()
        model = SiameseUNet(3, width=4)
        for p in model.parameters():
            p.data.zero_()
        model.head.bias.data.fill_(2)
        checkpoint = self.root/'test.pt'
        torch.save(dict(architecture='siam_diff_v1', channels=list(engine.channels), width=4,
                        state_dict=model.state_dict(), threshold=.5), checkpoint)
        scene = dict(scene_id='test', bands=[dict(name=b.name, path=str(b.path), scale=1, offset=0)
                                           for b in engine.scenes[0].bands])
        manifest = self.root/'pair.json'
        manifest.write_text(json.dumps(dict(t1=scene, t2=scene, core_size=4, halo=32)), encoding='utf-8')
        output = self.root/'cli.tif'
        with patch.object(sys, 'argv', ['change_cli', '--manifest', str(manifest),
                                       '--checkpoint', str(checkpoint), '--output', str(output)]):
            main()
        with rasterio.open(output) as ds:
            np.testing.assert_array_equal(ds.read(1), 1)
            provenance = json.loads(ds.tags()['provenance'])
            self.assertEqual(len(provenance['checkpoint_sha256']), 64)
        with patch.object(sys, 'argv', ['change_cli', '--manifest', str(manifest),
                                       '--checkpoint', str(checkpoint), '--output', str(checkpoint)]):
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                main()
        saved = torch.load(checkpoint, weights_only=True)
        saved['width'] = 4.5
        torch.save(saved, checkpoint)
        with patch.object(sys, 'argv', ['change_cli', '--manifest', str(manifest),
                                       '--checkpoint', str(checkpoint), '--output', str(output)]):
            with self.assertRaisesRegex(ValueError, 'width'):
                main()


@unittest.skipUnless(importlib.util.find_spec('torch'), 'Install requirements-vision.txt')
class VisionTests(unittest.TestCase):
    def test_bad_loss_parameters_masks_and_model_logits(self):
        import torch
        from src.vision_core import FocalTverskyLoss, SiameseUNet
        for key in ('gamma', 'alpha', 'beta'):
            with self.assertRaises(ValueError):
                FocalTverskyLoss(**{key: float('inf')})
        z = torch.zeros(1, 1, 4, 4)
        with self.assertRaises(ValueError):
            FocalTverskyLoss()(z, z, torch.ones_like(z))
        with self.assertRaises(ValueError):
            SiameseUNet(3)(torch.zeros(1, 2, 4, 4), torch.zeros(1, 2, 4, 4))
        from src.change_pipeline import TorchPredictor
        from src.raster_engine import RasterPair
        class Infinite(torch.nn.Module):
            def forward(self, a, b):
                return torch.full((1, 1, 4, 4), float('inf'))
        pair = RasterPair(np.ones((3, 4, 4), np.float32), np.ones((3, 4, 4), np.float32),
                          np.ones((4, 4), bool), None)
        with self.assertRaisesRegex(ValueError, 'finite'):
            TorchPredictor(Infinite())(pair)

    def test_halo_core_matches_full_inference_at_internal_seams(self):
        import torch
        from src.vision_core import SiameseUNet
        torch.manual_seed(11)
        torch.set_num_threads(1)
        model = SiameseUNet(3, 4).eval()
        a, b = torch.randn(1, 3, 128, 128), torch.randn(1, 3, 128, 128)
        with torch.inference_mode():
            full = model(a, b)
            for r in (32, 64):
                for c in (32, 64):
                    tile = model(a[..., r-32:r+64, c-32:c+64], b[..., r-32:r+64, c-32:c+64])
                    torch.testing.assert_close(tile[..., 32:64, 32:64], full[..., r:r+32, c:c+32],
                                               rtol=1e-5, atol=1e-6)

    def test_zero_copy_and_storage_lifetime(self):
        import torch
        from src.dataset_bridge import tensor_pairs
        from src.raster_engine import RasterPair
        a = np.ones((3, 8, 8), np.float32)
        pair = RasterPair(a, a.copy(), np.ones((8, 8), bool), None)
        tensor = next(tensor_pairs([pair]))
        self.assertEqual(tensor.t1.data_ptr(), a.ctypes.data)
        del pair
        self.assertEqual(tensor.t1.sum().item(), 192)
        self.assertEqual(tensor.valid.dtype, torch.bool)

    def test_siamese_symmetry_backward_and_serialization(self):
        import torch
        from src.vision_core import SiameseUNet, FocalTverskyLoss
        torch.manual_seed(7)
        torch.set_num_threads(1)
        model = SiameseUNet(3, width=4)
        a, b = torch.randn(1, 3, 16, 16), torch.randn(1, 3, 16, 16)
        z = model(a, b)
        torch.testing.assert_close(z, model(b, a))
        y = torch.zeros_like(z)
        y[..., 5, 5] = 1
        loss = FocalTverskyLoss()(z, y, torch.ones_like(z, dtype=torch.bool))
        loss.backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'weights.pt'
            torch.save(model.state_dict(), path)
            restored = SiameseUNet(3, width=4)
            restored.load_state_dict(torch.load(path, weights_only=True))
            torch.testing.assert_close(z, restored(a, b))

    def test_loss_extreme_logits_invalid_and_empty_targets(self):
        import torch
        from src.vision_core import FocalTverskyLoss
        criterion = FocalTverskyLoss()
        z = torch.tensor([[[[-1000., 1000., float('nan')]]]], requires_grad=True)
        y = torch.tensor([[[[1., 0., 255.]]]])
        valid = torch.tensor([[[[True, True, False]]]])
        loss = criterion(z, y, valid)
        self.assertTrue(torch.isfinite(loss))
        loss.backward()
        self.assertLess(z.grad[0, 0, 0, 0], 0)
        self.assertGreater(z.grad[0, 0, 0, 1], 0)
        self.assertEqual(z.grad[0, 0, 0, 2], 0)
        z2 = torch.zeros(1, 1, 4, 4, requires_grad=True)
        zero = criterion(z2, torch.zeros_like(z2), torch.zeros_like(z2, dtype=torch.bool))
        zero.backward()
        self.assertEqual(zero.item(), 0)
        self.assertTrue(torch.isfinite(criterion(z2, torch.zeros_like(z2), torch.ones_like(z2, dtype=torch.bool))))


if __name__ == '__main__':
    unittest.main()
