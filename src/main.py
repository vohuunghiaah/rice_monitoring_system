"""CLI: python -m src.main {search,download,run,process}."""
import argparse
import json
import logging
from pathlib import Path
from pystac_client.exceptions import APIError

from src.io.downloader import SentinelDownloader
from src.pipeline import process_scene
from src.mosaic import mosaic_scenes


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    parser = argparse.ArgumentParser(description='Windowed Sentinel-2 NDVI pipeline')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('search', 'download', 'run', 'process'):
        p = sub.add_parser(command)
        if command != 'process':
            p.add_argument('--bbox', nargs=4, type=float, required=True,
                           metavar=('WEST', 'SOUTH', 'EAST', 'NORTH'))
            p.add_argument('--dates', required=True, help='ISO date interval START/END')
            p.add_argument('--cloud-cover', type=float, default=20)
            p.add_argument('--raw-dir', default='data/01_raw')
            p.add_argument('--target-date', help='Prefer acquisition closest to YYYY-MM-DD')
            p.add_argument('--max-day-gap', type=int, default=3)
        else:
            p.add_argument('--manifest', type=Path, help='Downloaded scene JSON (includes calibration)')
            p.add_argument('--red')
            p.add_argument('--nir')
            p.add_argument('--scl')
            p.add_argument('--scene-id', default='local')
            p.add_argument('--acquired-at', help='Acquisition date/time for local bands; required for later mosaic')
            p.add_argument('--scale', type=float, help='Explicit shared reflectance scale for local bands')
            p.add_argument('--offset', type=float, help='Explicit shared reflectance offset for local bands')
        if command in ('run', 'process'):
            p.add_argument('--output-dir', default='data/03_processed')
            p.add_argument('--chunk-size', type=int, default=512)
        if command == 'run':
            p.add_argument('--mosaic', action='store_true', help='Build a regional mosaic after processing')
            p.add_argument('--aoi', type=Path)
            p.add_argument('--rice-mask', type=Path)
            p.add_argument('--rice-class', type=int, default=1)
            p.add_argument('--resolution', type=float, default=10)
            p.add_argument('--max-pixels', type=int, default=500_000_000)
    p = sub.add_parser('mosaic', help='Equal-area temporal mosaic from per-scene summaries')
    p.add_argument('--summaries', nargs='+', required=True, type=Path)
    p.add_argument('--target-date', required=True)
    p.add_argument('--max-day-gap', type=int, default=3)
    p.add_argument('--resolution', type=float, default=10)
    p.add_argument('--aoi', type=Path, help='WGS84 Polygon/MultiPolygon GeoJSON')
    p.add_argument('--rice-mask', type=Path, help='Categorical raster; not inferred from NDVI')
    p.add_argument('--rice-class', type=int, default=1)
    p.add_argument('--chunk-size', type=int, default=512)
    p.add_argument('--max-pixels', type=int, default=500_000_000)
    p.add_argument('--output-dir', default='data/03_processed/mosaic')
    args = parser.parse_args(argv)
    if hasattr(args, 'chunk_size') and not 1 <= args.chunk_size <= 2048:
        parser.error('--chunk-size must be in [1, 2048]')
    if args.command == 'run':
        if args.mosaic and not args.target_date:
            parser.error('run --mosaic requires --target-date')
        if not args.mosaic and (args.aoi or args.rice_mask):
            parser.error('--aoi/--rice-mask require --mosaic in run mode')
    try:
        if args.command == 'mosaic':
            result = mosaic_scenes(args.summaries, args.output_dir, args.target_date,
                                   args.max_day_gap, args.resolution, args.aoi,
                                   args.rice_mask, args.rice_class, args.chunk_size, args.max_pixels)
            print(json.dumps(result, indent=2))
        elif args.command == 'process':
            if args.manifest:
                if any((args.red, args.nir, args.scl, args.scale is not None,
                        args.offset is not None, args.acquired_at)):
                    parser.error('--manifest cannot be mixed with local band/calibration options')
                scene = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
            else:
                if not all((args.red, args.nir, args.scl)):
                    parser.error('process requires --manifest or all of --red --nir --scl')
                params = {}
                if args.scale is not None:
                    params['scale'] = args.scale
                if args.offset is not None:
                    params['offset'] = args.offset
                scene = {'id': args.scene_id, 'bands': {'B04': args.red, 'B08': args.nir, 'SCL': args.scl},
                         'datetime': args.acquired_at, 'calibration': {'B04': params, 'B08': params}}
            result = process_scene(scene['bands'], args.output_dir, scene['id'],
                                   args.chunk_size, scene.get('calibration'), scene)
            print(json.dumps(result, indent=2))
        else:
            downloader = SentinelDownloader(args.raw_dir)
            if args.command == 'search':
                print(json.dumps([{'id': item.id, 'cloud_cover': item.properties.get('eo:cloud_cover')}
                      for item in downloader.search(args.bbox, args.dates, args.cloud_cover,
                                                     args.target_date, args.max_day_gap)], indent=2))
            else:
                summaries = []
                for scene in downloader.download_scenes(args.bbox, args.dates, args.cloud_cover,
                                                        args.target_date, args.max_day_gap):
                    result = scene if args.command == 'download' else process_scene(
                        scene['bands'], args.output_dir, scene['id'], args.chunk_size, scene['calibration'], scene)
                    print(json.dumps(result, indent=2))
                    if args.command == 'run':
                        summaries.append(Path(args.output_dir)/f"{scene['id']}_summary.json")
                if args.command == 'run' and args.mosaic:
                    result = mosaic_scenes(summaries, Path(args.output_dir)/'mosaic', args.target_date,
                                           args.max_day_gap, args.resolution, args.aoi, args.rice_mask,
                                           args.rice_class, args.chunk_size, args.max_pixels)
                    print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, APIError) as exc:
        logging.error('%s', exc)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
