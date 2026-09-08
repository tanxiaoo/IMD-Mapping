"""Extract GHSL built-up surface (GHS-BUILT-S, 2018) at the Milan sample points.

A same-location alternative label to the CLMS-derived IMD, so a model trained
against GHSL can be compared with the CLMS run without re-sampling new points.
No Earth Engine needed -- everything here is local raster/vector work.

Three outputs:
  data/GHSL_2018_Milan_UTM32N.tif        GHSL clipped out of the global tile
                                          and reprojected onto the exact pixel
                                          grid of data/IMD_2018_CLMS_UTM32N.tif
                                          (EPSG:32632, 10 m) -- so the two are
                                          diff-able cell for cell.
  data/GHSL_2018_Milan_UTM32N_class.tif  The above reclassified into the 7 IMD
                                          classes (0 / 1-20 / 21-40 / 41-60 /
                                          61-80 / 81-99 / 100), done once over
                                          the whole raster before any point
                                          sampling -- so GHSL_class always
                                          traces back to a raster artifact you
                                          can open and check, not a value
                                          recomputed ad hoc per point.
  outputs_sampling/sample_points_all_GHSL.gpkg
                                          A drop-in replacement for
                                          outputs_sampling/sample_points_all.gpkg:
                                          same 3500 points, same A00-A63
                                          AlphaEarth columns, but GHSL/GHSL_class
                                          in place of IMD/IMD_class -- never
                                          both labels in one file, so notebook
                                          01c's ALL_POINTS_PATH can point at
                                          either interchangeably.
  samples_S2_<tag>/sample_points_all_S2_GHSL.gpkg
                                          Same drop-in swap for every Sentinel-2
                                          baseline table notebook 00 has built --
                                          median, stack, percentile_pXXpYY..., one
                                          per samples_S2_<tag>/ directory found.
                                          Same 3500 points, same bands (unaffected
                                          by the label, so nothing is re-extracted
                                          from GEE), GHSL/GHSL_class in place of
                                          IMD/IMD_class. Feeds notebook 01d --
                                          re-run this script after notebook 00
                                          finishes a new mode and it picks up the
                                          new samples_S2_<tag>/ automatically.

Run: python extract_ghsl_milan.py
"""
import glob
import os

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window

RAW_GHSL_PATH = (r'C:\Users\user\Downloads'
                  r'\GHS_BUILT_S_E2018_GLOBE_R2023A_54009_10_V1_0_R4_C19'
                  r'\GHS_BUILT_S_E2018_GLOBE_R2023A_54009_10_V1_0_R4_C19.tif')
REF_RASTER_PATH  = 'data/IMD_2018_CLMS_UTM32N.tif'
OUT_RASTER_PATH  = 'data/GHSL_2018_Milan_UTM32N.tif'
CLASS_RASTER_PATH = 'data/GHSL_2018_Milan_UTM32N_class.tif'

AEF_SRC_POINTS_PATH = 'outputs_sampling/sample_points_all.gpkg'
AEF_OUT_POINTS_PATH = 'outputs_sampling/sample_points_all_GHSL.gpkg'

S2_SAMPLE_GLOB = 'samples_S2_*/sample_points_all_S2.gpkg'

NODATA       = 255   # GHS-BUILT-S convention: 0-100 = % built, 255 = no data
CLASS_NODATA = 255   # no valid class is 255, so it doubles as the class marker

CLASS_LABELS = ['C0 (0%)', 'C1 (1-20%)', 'C2 (21-40%)', 'C3 (41-60%)',
                'C4 (61-80%)', 'C5 (81-99%)', 'C6 (100%)']


def reclass_imd_7(arr):
    """Continuous 0-100 density -> the 7 IMD classes (matches notebook 02's
    reclass_imd_7, so GHSL_class lines up with the existing IMD_class)."""
    out = np.full(arr.shape, -1, dtype=np.int8)
    out[arr == 0]                 = 0
    out[(arr > 0)  & (arr <= 20)] = 1
    out[(arr > 20) & (arr <= 40)] = 2
    out[(arr > 40) & (arr <= 60)] = 3
    out[(arr > 60) & (arr <= 80)] = 4
    out[(arr > 80) & (arr < 100)] = 5
    out[arr == 100]               = 6
    return out


def clip_and_align_ghsl():
    """Clip the raw 100000x100000 px global GHSL tile down to the Milan AOI
    and reproject it onto the CLMS reference raster's exact grid."""
    with rasterio.open(REF_RASTER_PATH) as ref:
        ref_crs, ref_transform = ref.crs, ref.transform
        ref_shape = (ref.height, ref.width)
        ref_bounds = ref.bounds

    with rasterio.open(RAW_GHSL_PATH) as src:
        # Window-read only the Milan area -- reprojecting the whole global
        # tile would mean reading ~10 billion pixels.
        moll_bounds = transform_bounds(ref_crs, src.crs, *ref_bounds, densify_pts=21)
        window = rasterio.windows.from_bounds(*moll_bounds, transform=src.transform)
        pad = 20  # px, absorbs reprojection edge effects
        window = Window(window.col_off - pad, window.row_off - pad,
                         window.width + 2 * pad, window.height + 2 * pad)
        src_arr       = src.read(1, window=window)
        src_transform = src.window_transform(window)
        src_crs       = src.crs
        src_nodata    = src.nodata

    dst_arr = np.full(ref_shape, NODATA, dtype=np.uint8)
    reproject(
        source=src_arr, destination=dst_arr,
        src_transform=src_transform, src_crs=src_crs, src_nodata=src_nodata,
        dst_transform=ref_transform, dst_crs=ref_crs, dst_nodata=NODATA,
        resampling=Resampling.bilinear,
    )

    os.makedirs(os.path.dirname(OUT_RASTER_PATH), exist_ok=True)
    profile = dict(driver='GTiff', height=ref_shape[0], width=ref_shape[1],
                    count=1, dtype='uint8', crs=ref_crs, transform=ref_transform,
                    nodata=NODATA, compress='deflate')
    with rasterio.open(OUT_RASTER_PATH, 'w', **profile) as dst:
        dst.write(dst_arr, 1)

    valid = dst_arr != NODATA
    print(f'GHSL aligned to the CLMS grid -> {OUT_RASTER_PATH}')
    print(f'  shape: {dst_arr.shape} | valid: {valid.sum()}/{dst_arr.size} '
          f'({100 * valid.mean():.1f}%) | range: '
          f'{dst_arr[valid].min()}-{dst_arr[valid].max()}%')

    # Reclassify the whole raster -- initially, before any point sampling --
    # into the 7 IMD classes. reclass_imd_7 fills unmatched cells with -1,
    # and int8(-1) casts to uint8(255) automatically, which is CLASS_NODATA:
    # the 255 GHSL nodata pixels fall out of every class test and land there
    # too, so no separate masking step is needed.
    cls_arr = reclass_imd_7(dst_arr).astype(np.uint8)
    cls_profile = dict(driver='GTiff', height=ref_shape[0], width=ref_shape[1],
                        count=1, dtype='uint8', crs=ref_crs, transform=ref_transform,
                        nodata=CLASS_NODATA, compress='deflate')
    with rasterio.open(CLASS_RASTER_PATH, 'w', **cls_profile) as dst:
        dst.write(cls_arr, 1)

    print(f'GHSL reclassified -> {CLASS_RASTER_PATH}')
    for c, label in enumerate(CLASS_LABELS):
        n = int((cls_arr == c).sum())
        print(f'  {label}: {n:>10,} px  ({100 * n / valid.sum():5.1f}% of valid area)')


def _sample_ghsl_at(coords_wgs84):
    """Value + class from the two rasters built in clip_and_align_ghsl(), at
    a list of (lon, lat) points -- shared by both relabelling calls below."""
    gdf_pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(*zip(*coords_wgs84)), crs='EPSG:4326'
    ).to_crs('EPSG:32632')
    coords = [(geom.x, geom.y) for geom in gdf_pts.geometry]

    with rasterio.open(OUT_RASTER_PATH) as src:
        vals = np.array([v[0] for v in src.sample(coords)], dtype=float)
        vals[vals == src.nodata] = np.nan

    # Read the class off the raster reclassified in clip_and_align_ghsl(),
    # rather than recomputing it from vals -- one reclassification, done once
    # on the raster, is the source of truth for both the raster and the points.
    with rasterio.open(CLASS_RASTER_PATH) as src:
        cls = np.array([v[0] for v in src.sample(coords)], dtype=int)

    return vals, cls


def relabel_points(src_path, out_path):
    """Read a sample-points gpkg carrying IMD/IMD_class, and write a copy at
    the same 3500 locations with GHSL/GHSL_class standing in for them --
    never both labels in one file. Every other column (AlphaEarth bands or
    Sentinel-2 bands) passes through untouched, since predictors don't depend
    on which label they're being compared against."""
    gdf_src = gpd.read_file(src_path)
    assert len(gdf_src) == 3500, f'Expected 3500 source points, got {len(gdf_src)}'
    keep_cols = [c for c in gdf_src.columns if c not in ('IMD', 'IMD_class', 'geometry')]

    gdf_wgs84 = gdf_src if gdf_src.crs.to_epsg() == 4326 else gdf_src.to_crs('EPSG:4326')
    coords = [(geom.x, geom.y) for geom in gdf_wgs84.geometry]
    vals, cls = _sample_ghsl_at(coords)

    missing = np.isnan(vals)
    if missing.any():
        print(f'{int(missing.sum())} of {len(vals)} points have no GHSL value '
              '(fell outside the downloaded tile or on a masked pixel).')

    gdf_out = gdf_src[keep_cols + ['geometry']].copy()
    gdf_out['GHSL']       = vals
    gdf_out['GHSL_class'] = cls

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    gdf_out.to_file(out_path, driver='GPKG')
    print(f'Wrote {len(gdf_out)} points -> {out_path}')
    print(f'Columns: {list(gdf_out.columns)}')

    # Sanity check only -- IMD never enters the output file.
    both = ~missing
    diff = vals[both] - gdf_src['IMD'].values[both]
    print(f'[sanity check, not written] GHSL vs CLMS IMD at the same '
          f'{both.sum()} points (GHSL - IMD): mean={diff.mean():+.2f}pp  '
          f'std={diff.std():.2f}pp\n')


if __name__ == '__main__':
    clip_and_align_ghsl()
    relabel_points(AEF_SRC_POINTS_PATH, AEF_OUT_POINTS_PATH)

    s2_tables = sorted(glob.glob(S2_SAMPLE_GLOB))
    if not s2_tables:
        print(f'No Sentinel-2 tables found ({S2_SAMPLE_GLOB}) -- run notebook '
              '00 for at least one COMPOSITE_METHOD before this script can '
              'relabel it.')
    for src_path in s2_tables:
        tag = os.path.basename(os.path.dirname(src_path))          # samples_S2_median
        out_path = src_path.replace('sample_points_all_S2.gpkg',
                                     'sample_points_all_S2_GHSL.gpkg')
        print(f'-- {tag} --')
        relabel_points(src_path, out_path)
