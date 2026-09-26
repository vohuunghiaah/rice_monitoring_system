"""Offline learning example: synthetic overlapping tiles, cloud, AOI, rice mask.

The generated mask is illustrative, not a real rice classification map.
Run: python scripts/demo_pipeline.py
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from pyproj import Transformer
import rasterio
from rasterio.transform import Affine
from src.pipeline import process_scene
from src.mosaic import mosaic_scenes


def main():
    root = Path(__file__).resolve().parents[1]/'data'/'demo'
    root.mkdir(parents=True, exist_ok=True)
    summaries = []
    def write(name, values, transform):
        path = root/name
        with rasterio.open(path, 'w', driver='GTiff', count=1, dtype=values.dtype,
                           width=values.shape[1], height=values.shape[0], nodata=0,
                           crs='EPSG:32648', transform=transform) as ds:
            ds.write(values, 1)
        return str(path)
    for index, shift in enumerate((0, 40)):
        scene = f'demo_{index+1}'
        transform = Affine(10, 0, 500000+shift, 0, -10, 1100000)
        scl = np.full((4, 4), 4, np.uint8)
        if index == 0:
            scl[:2, 2:] = 9
        bands = dict(B04=write(f'{scene}_red.tif', np.full((8, 8), 2000, np.uint16), transform),
                     B08=write(f'{scene}_nir.tif', np.full((8, 8), 4000+index*2000, np.uint16), transform),
                     SCL=write(f'{scene}_scl.tif', scl, Affine(20, 0, 500000+shift, 0, -20, 1100000)))
        process_scene(bands, root/'processed', scene, chunk_size=3,
                      calibration={k: dict(scale=.0001, offset=-.1) for k in ('B04','B08')},
                      scene_metadata=dict(datetime=f'2026-02-0{3+index}', cloud_cover=10-index*5))
        summaries.append(root/'processed'/f'{scene}_summary.json')
    projection = Transformer.from_crs(32648, 4326, always_xy=True)
    ring = [projection.transform(x, y) for x, y in [(500000,1099920), (500120,1099920),
             (500120,1100000), (500000,1100000), (500000,1099920)]]
    aoi = root/'illustrative_aoi.geojson'
    aoi.write_text(json.dumps(dict(type='Polygon', coordinates=[ring])))
    mask = np.ones((8, 12), np.uint8)
    mask[4:, :4] = 2  # Class 2 is non-rice in this fictional example.
    mask_path = write('illustrative_rice_mask.tif', mask, Affine(10,0,500000,0,-10,1100000))
    result = mosaic_scenes(summaries, root/'mosaic', '2026-02-03', aoi=aoi,
                           rice_mask=mask_path, chunk_size=3)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
