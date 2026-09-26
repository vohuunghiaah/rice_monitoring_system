from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from src.main import main


class CLITests(unittest.TestCase):
    def test_run_mosaic_passes_dates_and_metadata(self):
        scene = dict(id='sample', datetime='2026-02-03', cloud_cover=3,
                     bands={'B04':'r', 'B08':'n', 'SCL':'s'}, calibration={})
        with patch('src.main.SentinelDownloader') as downloader, \
                patch('src.main.process_scene', return_value={}) as process, \
                patch('src.main.mosaic_scenes', return_value={}) as mosaic, redirect_stdout(StringIO()):
            downloader.return_value.download_scenes.return_value = [scene]
            status = main(['run', '--bbox', '105','9','106','10', '--dates','2026-02',
                           '--target-date','2026-02-03', '--max-day-gap','0', '--mosaic'])
            self.assertEqual(status, 0)
            self.assertEqual(process.call_args.args[-1], scene)
            self.assertEqual(downloader.return_value.download_scenes.call_args.args[-2:], ('2026-02-03', 0))
            self.assertEqual(mosaic.call_args.args[0], [Path('data/03_processed/sample_summary.json')])

    def test_missing_mosaic_date_rejected_before_network(self):
        with patch('src.main.SentinelDownloader') as downloader, redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(['run', '--bbox','105','9','106','10', '--dates','2026-02', '--mosaic'])
            self.assertEqual(error.exception.code, 2)
            downloader.assert_not_called()
