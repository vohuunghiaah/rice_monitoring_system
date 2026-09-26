"""Preview/remove only known caches. Never traverse data, .git or .venv.

    python scripts/clean_workspace.py
    python scripts/clean_workspace.py --apply
"""
import argparse
import os
from pathlib import Path
import shutil
import stat

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {'.git', '.venv', 'data', 'image_test'}
CACHES = {'__pycache__', '.pytest_cache', '.ruff_cache', 'partial_movie_files'}
TEX_CACHE_SUFFIXES = {'.aux', '.log', '.out', '.toc', '.fls', '.fdb_latexmk'}


def candidates(root=ROOT):
    root = root.resolve()
    for folder, directories, files in os.walk(root, topdown=True, followlinks=False):
        folder = Path(folder)
        for name in list(directories):
            path = folder/name
            # Resolve each directory before walking/removing: skip symlinks/junctions.
            if name in PROTECTED or path.is_symlink() or path.resolve() != path.absolute():
                directories.remove(name)
            elif (name in CACHES or path == root/'.claude'
                  or path in (root/'media'/'Tex', root/'media'/'texts')):
                directories.remove(name)
                yield path
        for name in files:
            path = folder/name
            tex_cache = (path.is_relative_to(root/'docs') and path.suffix in TEX_CACHE_SUFFIXES
                         and path.with_suffix('.tex').exists())
            if name == '.DS_Store' or name.endswith(('.pyc', '.pyo')) or tex_cache:
                if not path.is_symlink():
                    yield path


def clean(root=ROOT, apply=False):
    root = root.resolve()
    def retry_readonly(function, name, error):
        path = Path(name)
        resolved = path.resolve()
        if (not isinstance(error[1], PermissionError) or resolved == root
                or not resolved.is_relative_to(root) or path.is_symlink()):
            raise error[1]
        # OneDrive marks directories read-only on Windows. Clear that attribute
        # only on the already-selected cache target; do not change ACLs.
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
        function(name)
    removed = []
    for path in candidates(root):
        resolved = path.resolve()
        if resolved == root or not resolved.is_relative_to(root) or path.is_symlink():
            raise ValueError(f'Refusing path outside workspace: {path}')
        print(('REMOVE ' if apply else 'PREVIEW ') + str(path.relative_to(root)))
        if apply:
            if path.is_dir():
                shutil.rmtree(path, onerror=retry_readonly)
            else:
                try:
                    path.unlink()
                except PermissionError as error:
                    retry_readonly(os.unlink, path, (type(error), error, None))
        removed.append(str(path.relative_to(root)))
    return removed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    clean(apply=parser.parse_args().apply)
