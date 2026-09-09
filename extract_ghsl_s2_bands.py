"""Extract Sentinel-2 bands at the fixed GHSL points, for every composite
method notebook 00 has built (median/stack/percentile), so 01d can model any
of them against GHSL.

The GHSL point set itself is NOT re-sampled here -- it's the one Matej's-method
run already fixed in outputs_sampling/sample_points_all_GHSL.gpkg (3500 points,
500/class, already verified to survive both AlphaEarth and Sentinel-2 masking
under the median composite). This script reuses those exact geometries and
just pulls a different composite's bands at them, mirroring how notebook 00
itself reuses the same 3500 CLMS points across composite methods -- only the
extracted band values change per method, never the points.

For each samples_S2_<tag>/ that notebook 00 has populated (has
sample_points_all_S2.gpkg + s2_extraction_metadata.json) but that has no
sample_points_all_S2_GHSL.gpkg yet, this builds that tag's composite and
extracts it at the fixed GHSL points.

Run: python extract_ghsl_s2_bands.py
"""
import glob
import json
import os

import ee
import geopandas as gpd

from resample_ghsl_points import GEE_PROJECT, _sample_image_at_points
from s2_utils import build_composite, water_mask

GHSL_POINTS_PATH = 'outputs_sampling/sample_points_all_GHSL.gpkg'
S2_BANDS_N = 10   # from s2_utils.S2_BANDS -- used for the same "wide" test as notebook 00


def load_fixed_ghsl_points():
    gdf = gpd.read_file(GHSL_POINTS_PATH)[['GHSL', 'GHSL_class', 'geometry']]
    print(f'Loaded {len(gdf)} fixed GHSL points from {GHSL_POINTS_PATH}')
    return gdf


def extract_for_tag(sample_dir, gdf_ghsl):
    meta_path = f'{sample_dir}/s2_extraction_metadata.json'
    out_path  = f'{sample_dir}/sample_points_all_S2_GHSL.gpkg'
    with open(meta_path) as f:
        meta = json.load(f)

    aoi = ee.FeatureCollection(f'projects/{GEE_PROJECT}/assets/milano_aoi')
    aoi_geom = aoi.geometry()
    non_water = water_mask(aoi_geom)
    s2_img, s2_proj, band_names = build_composite(
        meta['collection'], meta['selected_dates'], aoi_geom, non_water,
        method=meta['method'],
        percentiles=tuple(meta['percentiles']) if meta.get('percentiles') else (25, 50, 75))

    assert band_names == meta['bands'], (
        f'{sample_dir}: rebuilt composite bands do not match metadata -- '
        's2_utils.build_composite has changed since notebook 00 ran.')

    # Same "wide" rule as notebook 00 Cell 8.
    wide = len(band_names) > S2_BANDS_N or len(meta['selected_dates']) >= 10
    print(f'\n-- {sample_dir} (method={meta["method"]}, '
          f'{len(meta["selected_dates"])} dates, {len(band_names)} bands) --')

    gdf_pid = gdf_ghsl.copy()
    gdf_pid['pid'] = range(len(gdf_pid))
    df = _sample_image_at_points(s2_img, gdf_pid, scale=10, projection=s2_proj,
                                  tile_scale=8 if wide else 4, wide=wide)

    merged = df.set_index('pid').reindex(range(len(gdf_pid)))
    missing = merged[band_names].isna().any(axis=1)
    if missing.any():
        raise RuntimeError(
            f'{sample_dir}: {int(missing.sum())} of {len(gdf_pid)} fixed GHSL '
            'points have no value under this composite -- unexpected, since '
            'these points already survived the median composite + AlphaEarth '
            'water mask. Inspect before proceeding.')

    gdf_out = gdf_ghsl.copy()
    gdf_out[band_names] = merged[band_names].values

    gdf_out.to_file(out_path, driver='GPKG')
    print(f'Wrote {len(gdf_out)} points -> {out_path}')


def main():
    ee.Initialize(project=GEE_PROJECT)
    gdf_ghsl = load_fixed_ghsl_points()

    candidates = sorted(glob.glob('samples_S2_*/sample_points_all_S2.gpkg'))
    if not candidates:
        print('No samples_S2_*/sample_points_all_S2.gpkg found -- run notebook 00 first.')
        return

    for src in candidates:
        sample_dir = os.path.dirname(src)
        out_path = f'{sample_dir}/sample_points_all_S2_GHSL.gpkg'
        if os.path.exists(out_path):
            print(f'-- {sample_dir}: {out_path} already exists, skipping.')
            continue
        extract_for_tag(sample_dir, gdf_ghsl)


if __name__ == '__main__':
    main()
