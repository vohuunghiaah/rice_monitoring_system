"""Run registered temporal change inference from a JSON manifest and checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from src.raster_engine import Band, Scene, RasterEngine


def file_digest(path: Path) -> str:
    """Hash a manifest/checkpoint with bounded memory for output provenance."""
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_engine(path: Path) -> RasterEngine:
    """Validate a JSON manifest before opening raster datasets or allocating a model."""
    manifest = json.loads(path.read_text(encoding='utf-8-sig'))
    root = path.resolve().parent
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be an object')

    def scene(key: str) -> Scene:
        item = manifest[key]
        if not isinstance(item, dict) or not isinstance(item.get('bands'), list):
            raise ValueError(f'{key} requires a bands list')
        bands = []
        for b in item['bands']:
            if not isinstance(b, dict) or not isinstance(b.get('path'), str) or not b['path'].strip():
                raise ValueError('Each band requires a nonempty path')
            if any(type(b.get(k)) not in (int, float) for k in ('scale', 'offset')):
                raise ValueError('Band scale/offset must be explicit numbers')
            bands.append(Band(b['name'], root/b['path'], b['scale'], b['offset']))
        quality = item.get('quality')
        if quality is not None and (not isinstance(quality, str) or not quality.strip()):
            raise ValueError('quality must be a nonempty path or null')
        return Scene(item['scene_id'], tuple(bands), root/quality if quality else None)

    try:
        core, halo = manifest.get('core_size', 256), manifest.get('halo', 32)
        if (type(core) is not int or type(halo) is not int or core <= 0
                or core % 4 or halo % 4 or halo < 24):
            raise ValueError('Siamese requires positive core/halo multiples of 4 and halo >= 24')
        ndvi = manifest.get('ndvi', ['B08', 'B04'])
        if ndvi is not None and (not isinstance(ndvi, list) or len(ndvi) != 2):
            raise ValueError('ndvi must be a pair of band names or null')
        return RasterEngine(scene('t1'), scene('t2'), core, halo,
                            tuple(ndvi) if ndvi is not None else None,
                            quality_radius=manifest.get('quality_radius', 0))
    except KeyError as exc:
        raise ValueError(f'Missing manifest field: {exc.args[0]}') from exc


def main() -> None:
    """Load a weights-only checkpoint; never silently use untrained weights."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    args = parser.parse_args()
    import torch
    from src.vision_core import SiameseUNet
    from src.change_pipeline import TorchPredictor, predict_raster, same_path

    if any(same_path(args.output, p) for p in (args.manifest, args.checkpoint)):
        raise ValueError('Output must not overwrite the manifest or checkpoint')
    engine = load_engine(args.manifest)
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    required = {'architecture', 'channels', 'width', 'state_dict', 'threshold'}
    if not isinstance(checkpoint, dict) or not required <= checkpoint.keys():
        raise ValueError('Checkpoint lacks required architecture/channels/width/state_dict/threshold')
    if (not isinstance(checkpoint['channels'], (list, tuple))
            or type(checkpoint['width']) is not int or checkpoint['width'] <= 0
            or type(checkpoint['threshold']) not in (int, float)
            or not math.isfinite(checkpoint['threshold']) or not 0 <= checkpoint['threshold'] <= 1):
        raise ValueError('Invalid checkpoint channel list, width or threshold')
    if checkpoint['architecture'] != 'siam_diff_v1' or tuple(checkpoint['channels']) != engine.channels:
        raise ValueError('Checkpoint architecture/channel contract differs from manifest')
    model = SiameseUNet(len(engine.channels), width=checkpoint['width'])
    model.load_state_dict(checkpoint['state_dict'], strict=True)
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise ValueError('Checkpoint contains nonfinite parameters')
    output = predict_raster(engine, TorchPredictor(model, args.device), args.output,
                            float(checkpoint['threshold']), provenance={
                                'manifest_sha256': file_digest(args.manifest),
                                'checkpoint_sha256': file_digest(args.checkpoint),
                                'architecture': checkpoint['architecture'],
                                'torch_version': str(torch.__version__)})
    print(output.resolve())


if __name__ == '__main__':
    main()
