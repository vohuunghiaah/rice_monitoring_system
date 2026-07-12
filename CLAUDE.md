# Rice Monitoring System — Project Compass

Last synced: 2026-07-06. This file is the single source of truth for architecture, task status, and collaboration protocol. Update it on every module completion or structural change — do not let it drift from the actual repo state.

## 1. Core Constraint (do not violate)

From the original roadmap: **no off-the-shelf libraries for core numerical computation.** `rasterio` is permitted for I/O (GeoTIFF/JP2 decoding), but NDVI computation, masking, resampling math, and array manipulation must be hand-implemented with NumPy primitives (vectorized ops, strides, broadcasting) — not wrapped from a higher-level geospatial stats library. The pedagogical goal is memory-layout and vectorization literacy, not shipping speed. Any suggestion that reaches for a canned solution here should be challenged before being accepted.

## 2. Collaboration Protocol

- Direct, critical feedback only. No unearned praise — approval is given only when a technical justification accompanies it.
- Algorithm/ML explanations use the Socratic method: no complete solution code up front. Break the problem down, ask guiding questions, let the user derive the implementation.
- All technical terminology in English (NDVI, vectorization, windowed reading, affine transform, coregistration, etc.), even mid-Vietnamese-sentence.
- This file (`CLAUDE.md`) gets rewritten after every completed task or architectural change.

## 3. System Architecture

```
rice_monitoring_system/
├── data/
│   ├── 01_raw/               # Raw .tif/.jp2 from Copernicus/Earth Search
│   ├── 02_intermediate/      # Cropped, SCL cloud-masked intermediates
│   └── 03_processed/         # NDVI outputs, statistics
├── docs/                     # Technical docs, LaTeX report, architecture notes
├── media/                    # Manim-rendered explainer visuals
├── scripts/
│   └── pipeline_data.py      # NOTE: currently a Manim scene file, NOT an ETL entry point (see §5)
└── src/
    ├── core/                 # NDVI + math kernels — EMPTY, this is Phase 2, not started
    ├── io/
    │   ├── raster_wrapper.py # RasterWrapper — rasterio wrapper, windowed reads
    │   └── downloader.py     # SentinelDownloader — STAC search/download, BROKEN (see §5)
    ├── viz/                  # Heatmap/color-mapping — EMPTY, Phase 3, not started
    └── main.py               # Pipeline glue — BROKEN, does not parse (see §5)
```

Data source: Sentinel-2 MSI, Level-2A (BOA reflectance), cloud cover ≤ 20%, bands B04/B08/SCL.

### Ingestion architecture decision (2026-07-06)

Target use case: macro/government-scale monitoring — scan a province's full agricultural area monthly for yield/drought-area statistics. This is an **exhaustive full-tile scan** workload, not an ad-hoc small-AOI query.

- **Chosen**: Level 1 — STAC API search (`pystac_client`) + bulk download to `data/01_raw/` + local windowed I/O, triggered by scheduled cronjob (pull). Justification: for exhaustive full-tile reads, per-chunk `/vsicurl/` HTTP Range Requests (COG streaming) pay round-trip latency (~50-100ms) on every windowed read — for a 10,980×10,980 tile at 256px chunks (~1,849 chunks/band) that overhead dominates local-disk read time. Streaming only wins when you read less than you'd download, which isn't this workload.
- **Deferred, not rejected**: Level 2 — Cloud-native COG streaming via `rasterio`'s `/vsicurl/`. Reserve for a future ad-hoc/interactive feature (e.g. query NDVI time-series for one small user-drawn AOI) where the access pattern is sparse, not exhaustive.
- **Considered, out of scope**: event-driven/push ingestion (subscribe to new-scene SNS notifications instead of polling STAC). Monthly cadence tolerates poll latency fine; revisit only if near-real-time reaction to new imagery becomes a requirement.
- **Rejected outright**: compute-to-data (Google Earth Engine / openEO / Sentinel Hub Processing API). Violates §1 core constraint — NDVI must be computed locally with hand-rolled NumPy, not by a remote managed engine.

## 4. Module Status Matrix

| Module | Status | Notes |
|---|---|---|
| `RasterWrapper` (`src/io/raster_wrapper.py`) | Functional | metadata, `read_band`, `get_pixel_size`, `get_bounds` (rotated-image case handled), `pixel_to_coords`, `read_chunk` (windowed generator). |
| `SentinelDownloader` (`src/io/downloader.py`) | Functional, single-tile scope only | Parses, runs, verified live against Earth Search STAC v1 (`sentinel-2-l2a`) — search, asset-key resolution (`red`/`nir`/`scl`), atomic file write, and explicit `sortby` (lowest `eo:cloud_cover` first) all confirmed. **Caveat**: `max_items=1` assumes the input `bbox` fits inside one Sentinel-2 UTM tile. A bbox spanning multiple tiles (e.g. a full province) silently returns only one of them — see known limitation #10. |
| `src/main.py` | Functional | Full flow wired: instantiate `SentinelDownloader` → `search_and_download` → open result with `RasterWrapper`. Verified live: correctly raises/handles `ValueError` when the STAC query returns no items. |
| NDVI core engine (`src/core/`) | Not started | Phase 2 of the roadmap. `__init__.py` is empty. |
| Visualization / color mapping (`src/viz/`) | Not started | Phase 3 of the roadmap. `__init__.py` is empty. |
| `scripts/pipeline_data.py` | Mislabeled | Contains a Manim `ThreeDScene` (pedagogical animation of the array→raster→NDVI pipeline), not the ETL entry point the README claims it is. Either rename this file or write the actual ETL script separately — the current naming is misleading. Not yet addressed. |

## 5. Known Issues

**Phase 1 — resolved 2026-07-06:**

1. ~~`src/main.py:14-16`~~ — incomplete `try` block, `SyntaxError`. Fixed: `SentinelDownloader` is now instantiated and `search_and_download` is called and awaited for its return dict; `except (ValueError, requests.exceptions.RequestException)` handles both "no data found" and network failures.
2. ~~`src/io/downloader.py:7`~~ — stray `:` before the default arg, `SyntaxError`. Fixed.
3. ~~`src/io/downloader.py:33`~~ — `target_bands` referenced but never defined. Fixed: module-level `TARGET_BANDS = {"B04": "red", "B08": "nir", "SCL": "scl"}`, confirmed against a live STAC item's `assets` dict.
4. ~~`src/io/downloader.py:47`~~ — `request.get` typo (missing `s`), `NameError`. Fixed.
5. ~~`src/io/downloader.py:24`~~ — `max_item` vs `max_items` kwarg mismatch. Fixed.
6. **Found during live verification, not in the original list**: `collections=["sentinel-2-L2A"]` — Earth Search v1 collection IDs are case-sensitive; the real ID is lowercase `sentinel-2-l2a`. The uppercase version doesn't error, it just silently returns zero items, which then surfaces as the misleading "no satellite data matching the parameters" `ValueError` — looks like a bbox/date/cloud-cover problem, isn't. Fixed.
7. **Found during live verification, not in the original list**: `_download_file` wrote directly to `dest_path` with no atomicity. An interrupted download (network drop, killed process) leaves a truncated file at `dest_path`, and the existence check (`if os.path.exists(dest_path): return`) then treats that corrupt file as a valid cache hit forever. Fixed: stream to `dest_path + ".part"`, `os.replace()` into place only on success, clean up the partial file in a `finally` otherwise.
10. **Found during ingestion-architecture review, not in the original list**: no explicit `sortby` on the STAC search. STAC does not guarantee a default sort order across backends, and within a single tile a monthly `time_range` can match 4-6 candidate scenes (Sentinel-2 revisit ~5 days) with different cloud cover. Without an explicit sort, the query could silently pick a scene that merely passes the `cloud_cover` threshold rather than the clearest one available — bad for month-over-month drought-area statistics. Fixed: `sortby=[{"field": "properties.eo:cloud_cover", "direction": "asc"}]`.

**Open:**

11. `requirements.txt` only listed `rasterio`, `numpy`, `manim` — `requests` and `pystac_client` were imported by `downloader.py` but never declared. Added.
12. `scripts/pipeline_data.py` naming/purpose mismatch (see §4) — not yet resolved.
13. **Multi-tile mosaicking — deliberately deferred, not a bug.** `search_and_download` uses `max_items=1`, which assumes the caller's `bbox` fits inside a single Sentinel-2 UTM tile. Confirmed live: querying `bbox_dbscl = [105.0, 9.5, 106.0, 10.5]` returns candidates from two distinct tiles (`48PVS`, `48PWR`) — a province-scale bbox will silently only download one. Decision (2026-07-06): build the Phase 2 NDVI kernel against a single tile first (separates matrix-computation concerns from spatial-geometry concerns — CRS harmonization across UTM zones, overlap dedup). Multi-tile mosaicking becomes an orchestration layer *around* the proven single-tile kernel, not before it. Track as a backlog item, not a Phase 1 blocker.

## 6. Roadmap (from original EXECUTION_ROADMAP)

**Phase 1 — Dataflow & I/O (`src/io/`) — CLOSED 2026-07-06**
- [x] Task 1.1 — `RasterWrapper` base class: read, metadata, context manager.
- [x] Task 1.2 — `get_pixel_size`, `get_bounds` (rotated-image support), `pixel_to_coords`.
- [x] Task 1.3 — Windowed/chunked reads (`read_chunk`, 256/512px blocks) to avoid OOM.
- [x] Fix `SentinelDownloader` (issues 1-7 in §5) and wire it into `src/main.py`.

**Phase 2 — Core Engine (`src/core/ndvi_engine.py`, not yet created)**
- [ ] Task 2.1 — NDVI kernel: `(NIR - RED) / (NIR + RED)` on NumPy arrays, no off-the-shelf geospatial-stats shortcut.
- [ ] Task 2.2 — Divide-by-zero handling via vectorized masking (`np.errstate`, boolean indexing, or `np.where`) — no nested `for`/`if`.
- [ ] Task 2.3 — Vectorization/strides optimization for full 10,980 × 10,980 Sentinel-2 tiles.

**Phase 3 — Rendering (`src/viz/heatmap_generator.py`, not yet created)**
- [ ] Task 3.1 — Float [-1, 1] → color LUT mapping.
- [ ] Task 3.2 — RGB matrix generation for false-color NDVI output.

**Phase 4 — Pipeline Assembly (`src/main.py`)**
- [ ] Task 4.1 — Wire I/O → Core → Viz → `data/03_processed/`.
- [ ] Task 4.2 — Sequential chunk-wise processing loop (no full-image load).
- [ ] Task 4.3 — Performance/memory profiling (`memory_profiler` or equivalent).

**Backlog — Multi-tile Mosaicking (deferred from Phase 1, see known issue #13)**
- [ ] Extend `search_and_download` to return all STAC items intersecting `bbox`, not just `max_items=1`.
- [ ] Orchestrator layer to loop the (proven, single-tile) Phase 2 NDVI kernel across N tiles.
- [ ] CRS harmonization for bboxes spanning two UTM zones (e.g. 48N/49N boundary).
- [ ] Overlap deduplication for adjacent-tile sensing-time mismatches.

## 7. Mock-interview checkpoints (self-assessment, unchecked = not yet internalized)
- [ ] Peak RAM footprint of loading a full 16-bit raster; mitigation under a 256MB container limit.
- [ ] Branchless divide-by-zero avoidance (why nested `for`/`if` hurts branch prediction).
- [ ] Intermediate memory blow-up when casting `uint16` → `float64`; how to bound it.
- [ ] Why multiprocessing doesn't scale linearly for data-bound (I/O-bound) tasks.
- [ ] Row-major vs column-major traversal and L1/L2 cache-miss behavior.
