from pathlib import Path
import tempfile
import unittest
import stat

from scripts.clean_workspace import clean


class CleanupTests(unittest.TestCase):
    def test_preview_and_apply_preserve_inputs_and_final_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = ['.claude/settings.local.json', 'src/__pycache__/code.pyc',
                     'media/videos/partial_movie_files/part.mp4',
                     'media/videos/final.mp4', 'data/raw.tif', 'image_test/reference.tif',
                     '.git/index', '.venv/__pycache__/keep.pyc']
            for name in paths:
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            clean(root)
            self.assertTrue(all((root/p).exists() for p in paths))
            (root/'.claude').chmod(stat.S_IREAD)
            clean(root, apply=True)
            self.assertTrue(all(not (root/p).exists() for p in paths[:3]))
            self.assertTrue(all((root/p).exists() for p in paths[3:]))
