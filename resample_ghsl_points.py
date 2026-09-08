"""Resample the Milan GHSL training/test points using Matej Zgela's method
(reference/Zgela_LCZ-UHI-GEO_Report.pdf, Section 1a), instead of reusing the
CLMS point locations.

Why: extract_ghsl_milan.py's relabel_points() reused the CLMS-derived 3500
points and just read GHSL off them. Since CLMS and GHSL disagree pixel to
pixel, that gave a skewed class mix (e.g. 39 points at class 6 instead of
500). Matej's own method for the Vietnam transfer -- "random stratified
sampling of 500 points per class from the GHS-BUILT-S dataset" -- draws points
directly from GHSL's own classification instead, so the GHSL run is balanced
on its own terms, the same way the CLMS run is balanced on its.

Steps (mirrors notebook 02's Cell 3 "Sample 500/class stratified", applied to
Milan's own GHSL raster rather than a new city):
  1. Draw 500 points/class from data/GHSL_2018_Milan_UTM32N_class.tif (built by
     extract_ghsl_milan.py) -- new locations, not the CLMS ones.
  2. Run the same validation checks Matej reports for point selection: the
     Average Nearest Neighbour (ANN) spatial-randomness index per class, and
     per-class value-distribution stats.
  3. Extract AlphaEarth embeddings (A00-A63) and Sentinel-2 bands (B2-B12,
     same 30-date median composite as samples_S2_median) at these new points
     via Earth Engine, chunked as in notebook 00/02.
  4. Overwrite outputs_sampling/sample_points_all_GHSL.gpkg and
     samples_S2_median/sample_points_all_S2_GHSL.gpkg with the new points --
     both share the same new geometries, matching how the CLMS run's 3500
     points are shared between the AEF and S2 tables.

Needs a cached Earth Engine credential (same one 00_/01c/01d already use) --
no ee.Authenticate() prompt if `earthengine authenticate` has already run.

Run: python resample_ghsl_points.py
"""
import json
import os
import time

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree

from extract_ghsl_milan import CLASS_LABELS, CLASS_RASTER_PATH, OUT_RASTER_PATH
from s2_utils import build_composite, water_mask

GEE_PROJECT   = 'impervious-s2'
N_CLASSES     = 7
SAMPLES_PER_CLASS = 500
# Some drawn points land on water and get masked out of both the AlphaEarth
# and Sentinel-2 extractions (observed ~1.2% worst-case, class 0). Draw extra
# per class up front and trim back to exactly 500 after extraction, rather
# than shipping a shortfall -- Matej's design is exactly 500/class, and so is
# every downstream notebook's `assert len(gdf_all) == 3500`.
OVERSAMPLE_PER_CLASS = 520
RANDOM_STATE  = 42

AEF_OUT_PATH  = 'outputs_sampling/sample_points_all_GHSL.gpkg'
S2_SAMPLE_DIR = 'samples_S2_median'
S2_META_PATH  = f'{S2_SAMPLE_DIR}/s2_extraction_metadata.json'
S2_OUT_PATH   = f'{S2_SAMPLE_DIR}/sample_points_all_S2_GHSL.gpkg'
QC_FIG_PATH   = 'outputs_sampling/ghsl_resample_qc.png'

CHUNK_SIZE = 500   # points per getInfo batch, matches notebook 00 Cell 8


def sample_ghsl_points_matej():
    """OVERSAMPLE_PER_CLASS points/class drawn directly from the GHSL
    classification -- new locations, independent of the CLMS points. Extra
    points beyond the 500/class Matej uses are trimmed off in main() after
    extraction drops whichever ones land on water."""
    with rasterio.open(CLASS_RASTER_PATH) as src:
        cls_arr   = src.read(1)
        transform = src.transform
        crs       = src.crs
    with rasterio.open(OUT_RASTER_PATH) as src:
        val_arr = src.read(1)

    rng = np.random.RandomState(RANDOM_STATE)
    rows, cols, classes = [], [], []
    for c in range(N_CLASSES):
        ys, xs = np.where(cls_arr == c)
        if len(ys) < OVERSAMPLE_PER_CLASS:
            raise RuntimeError(f'Class {c} has only {len(ys)} px, need '
                                f'{OVERSAMPLE_PER_CLASS}.')
        idx = rng.choice(len(ys), OVERSAMPLE_PER_CLASS, replace=False)
        rows.extend(ys[idx]); cols.extend(xs[idx]); classes.extend([c] * OVERSAMPLE_PER_CLASS)

    rows, cols, classes = np.array(rows), np.array(cols), np.array(classes)
    xs_utm, ys_utm = rasterio.transform.xy(transform, rows, cols)  # pixel centres
    vals = val_arr[rows, cols].astype(float)

    gdf_utm = gpd.GeoDataFrame(
        {'GHSL': vals, 'GHSL_class': classes},
        geometry=gpd.points_from_xy(xs_utm, ys_utm), crs=crs)
    gdf = gdf_utm.to_crs('EPSG:4326').reset_index(drop=True)
    print(f'Sampled {len(gdf)} candidate points ({OVERSAMPLE_PER_CLASS}/class x '
          f'{N_CLASSES} classes -- a buffer over the {SAMPLES_PER_CLASS}/class '
          'target), Matej\'s method, from GHSL\'s own classification.')
    return gdf


def ann_report(coords_utm, classes, aoi_area_m2):
    """Average Nearest Neighbour index per class (Clark & Evans 1954, the
    formula Matej's report cites via the ArcGIS ANN documentation):
      expected mean NN distance under CSR = 0.5 * sqrt(A / n)
      ANN = observed mean NN distance / expected
    ANN << 1 -> clustered, ANN ~= 1 -> random, ANN >> 1 -> dispersed."""
    rows = []
    for c in range(N_CLASSES):
        pts = coords_utm[classes == c]
        tree = cKDTree(pts)
        d, _ = tree.query(pts, k=2)          # k=2: nearest OTHER point (k=1 is itself)
        observed = d[:, 1].mean()
        n = len(pts)
        expected = 0.5 * np.sqrt(aoi_area_m2 / n)
        rows.append({'class': CLASS_LABELS[c], 'n': n,
                      'observed_NN_m': observed, 'expected_NN_m': expected,
                      'ANN': observed / expected})
    df = pd.DataFrame(rows)
    print('\nSpatial randomness (Average Nearest Neighbour index per class):')
    print('  ANN ~= 1 random, < 1 clustered, > 1 dispersed '
          '(Matej reports 1.02 down to 0.75 for Milan/CLMS)')
    print(df.to_string(index=False, float_format=lambda v: f'{v:,.2f}'))
    return df


def value_distribution_report(gdf):
    rows = []
    for c in range(N_CLASSES):
        v = gdf.loc[gdf['GHSL_class'] == c, 'GHSL']
        rows.append({'class': CLASS_LABELS[c], 'n': len(v),
                      'min': v.min(), 'q1': v.quantile(.25), 'mean': v.mean(),
                      'median': v.median(), 'q3': v.quantile(.75), 'max': v.max(),
                      'std': v.std()})
    df = pd.DataFrame(rows)
    print('\nWithin-class value distribution (GHSL %, matches Matej\'s Figure 2 check):')
    print(df.to_string(index=False, float_format=lambda v: f'{v:,.2f}'))
    single_value = df[(df['min'] == df['max'])]['class'].tolist()
    if single_value:
        print(f'  Note: {single_value} are single-valued (0 or 100), same as '
              'Matej reports for classes 0 and 6 -- expected, not a defect.')
    return df


def plot_qc_figure(gdf, ann_df, dist_df):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    colors = plt.cm.viridis(np.linspace(0, 1, N_CLASSES))
    for c in range(N_CLASSES):
        sub = gdf[gdf['GHSL_class'] == c]
        axes[0].scatter(sub.geometry.x, sub.geometry.y, s=4, color=colors[c],
                         label=CLASS_LABELS[c], alpha=.6)
    axes[0].set_title('Resampled points by class'); axes[0].legend(fontsize=6, markerscale=2)
    axes[0].set_xlabel('lon'); axes[0].set_ylabel('lat')

    axes[1].bar(range(N_CLASSES), ann_df['ANN'], color=colors)
    axes[1].axhline(1, color='k', ls='--', lw=1)
    axes[1].set_xticks(range(N_CLASSES)); axes[1].set_xticklabels(range(N_CLASSES))
    axes[1].set_xlabel('class'); axes[1].set_ylabel('ANN index')
    axes[1].set_title('Spatial randomness per class')

    data = [gdf.loc[gdf['GHSL_class'] == c, 'GHSL'].values for c in range(N_CLASSES)]
    axes[2].boxplot(data, tick_labels=range(N_CLASSES))
    axes[2].set_xlabel('class'); axes[2].set_ylabel('GHSL (%)')
    axes[2].set_title('Within-class value spread')

    plt.tight_layout()
    os.makedirs(os.path.dirname(QC_FIG_PATH), exist_ok=True)
    plt.savefig(QC_FIG_PATH, dpi=130, bbox_inches='tight')
    plt.close(fig)
    print(f'\nQC figure -> {QC_FIG_PATH}')


def _sample_image_at_points(image, gdf, scale, projection, tile_scale, wide):
    """Chunked sampleRegions -> DataFrame, matching notebook 00 Cell 8 / 02 Cell 3.

    properties=['pid'] only: that arg copies INPUT feature properties onto the
    output, it does not select which image bands come back -- passing band
    names there (tried first) makes sampleRegions return pid alone and drop
    every band silently. Band columns are added automatically, one per band."""
    chunk_size = CHUNK_SIZE // 2 if wide else CHUNK_SIZE
    records = []
    n_chunks = int(np.ceil(len(gdf) / chunk_size))
    for ci in range(n_chunks):
        chunk = gdf.iloc[ci * chunk_size:(ci + 1) * chunk_size]
        feats = [ee.Feature(ee.Geometry.Point([row.geometry.x, row.geometry.y]),
                             {'pid': int(row['pid'])})
                  for _, row in chunk.iterrows()]
        sampled = image.sampleRegions(
            collection=ee.FeatureCollection(feats), properties=['pid'],
            scale=scale, projection=projection, tileScale=tile_scale, geometries=False)
        records.extend([f['properties'] for f in sampled.getInfo()['features']])
        print(f'  chunk {ci + 1}/{n_chunks}: {len(records)} points returned so far')
    return pd.DataFrame(records)


def extract_aef_at_points(gdf):
    """AlphaEarth embeddings (A00-A63) at the new points -- mirrors notebook
    01_/02_'s AEF image construction."""
    aoi = ee.FeatureCollection(f'projects/{GEE_PROJECT}/assets/milano_aoi')
    aoi_geom = aoi.geometry()
    non_water = water_mask(aoi_geom)

    start = ee.Date.fromYMD(2018, 1, 1)
    aef_col = (ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL')
               .filter(ee.Filter.date(start, start.advance(1, 'year')))
               .filter(ee.Filter.bounds(aoi_geom)))
    aef_proj = aef_col.first().projection()
    aef_img = (aef_col.mosaic().setDefaultProjection(aef_proj)
               .clip(aoi_geom).updateMask(non_water))
    band_names = aef_img.bandNames().getInfo()
    print(f'\nExtracting AlphaEarth ({len(band_names)} bands) at {len(gdf)} points...')

    gdf_pid = gdf.copy(); gdf_pid['pid'] = np.arange(len(gdf_pid))
    df = _sample_image_at_points(aef_img, gdf_pid, scale=10,
                                  projection=aef_proj, tile_scale=4, wide=False)
    return _attach_bands(gdf_pid, df, band_names, 'AlphaEarth')


def extract_s2_at_points(gdf):
    """Sentinel-2 median composite (B2-B12) at the new points, using the SAME
    30 dates as samples_S2_median -- so this predictor table is comparable to
    the CLMS-labelled one, differing only in which points/labels are used."""
    with open(S2_META_PATH) as f:
        meta = json.load(f)
    selected_dates = meta['selected_dates']

    aoi = ee.FeatureCollection(f'projects/{GEE_PROJECT}/assets/milano_aoi')
    aoi_geom = aoi.geometry()
    non_water = water_mask(aoi_geom)
    s2_img, s2_proj, band_names = build_composite(
        meta['collection'], selected_dates, aoi_geom, non_water, method='median')
    print(f'\nExtracting Sentinel-2 ({len(band_names)} bands, {len(selected_dates)} dates) '
          f'at {len(gdf)} points...')

    gdf_pid = gdf.copy(); gdf_pid['pid'] = np.arange(len(gdf_pid))
    wide = len(selected_dates) >= 10
    df = _sample_image_at_points(s2_img, gdf_pid, scale=10,
                                  projection=s2_proj,
                                  tile_scale=8 if wide else 4, wide=wide)
    return _attach_bands(gdf_pid, df, band_names, 'Sentinel-2')


def _attach_bands(gdf_pid, df, band_names, label):
    """Reindex the (possibly short -- masked points just don't come back)
    sampleRegions result onto pid 0..N-1, so missing points show up as NaN
    rows instead of silently shifting every later row up."""
    merged = df.set_index('pid').reindex(range(len(gdf_pid)))
    missing = merged[band_names].isna().any(axis=1)
    if missing.any():
        print(f'  {int(missing.sum())} of {len(gdf_pid)} points have no {label} value '
              '(masked/water).')
    out = gdf_pid.copy()
    out[band_names] = merged[band_names].values.astype(np.float32)
    return out, missing.values


def _trim_to_exactly(gdf, keep_mask, per_class):
    """Within each class, keep the first `per_class` surviving rows in their
    original (already-random) draw order, and drop the rest of the buffer."""
    gdf = gdf.copy()
    gdf['_survives'] = keep_mask
    keep_idx = []
    for c in range(N_CLASSES):
        cls_idx = gdf.index[(gdf['GHSL_class'] == c) & gdf['_survives']]
        if len(cls_idx) < per_class:
            raise RuntimeError(
                f'Class {c}: only {len(cls_idx)} surviving points after '
                f'extraction, need {per_class}. Raise OVERSAMPLE_PER_CLASS '
                'and re-run.')
        keep_idx.extend(cls_idx[:per_class])
    return sorted(keep_idx)


def main():
    ee.Initialize(project=GEE_PROJECT)

    gdf = sample_ghsl_points_matej()

    gdf_aef, missing_aef = extract_aef_at_points(gdf)
    gdf_s2,  missing_s2  = extract_s2_at_points(gdf)

    # Keep the AEF and S2 tables on the SAME point set -- matching how the
    # CLMS run's 3500 points are shared identically between the two tracks.
    # A point masked in either extraction is unusable in both.
    survives = ~(missing_aef | missing_s2)
    n_masked = (~survives).sum()
    if n_masked:
        print(f'\n{int(n_masked)} of {len(gdf)} candidate point(s) masked in '
              'AlphaEarth and/or Sentinel-2 (water) -- excluded before trimming.')

    keep_idx = _trim_to_exactly(gdf, survives, SAMPLES_PER_CLASS)
    gdf     = gdf.loc[keep_idx].reset_index(drop=True)
    gdf_aef = gdf_aef.loc[keep_idx].drop(columns=['pid']).reset_index(drop=True)
    gdf_s2  = gdf_s2.loc[keep_idx].drop(columns=['pid']).reset_index(drop=True)
    assert len(gdf) == SAMPLES_PER_CLASS * N_CLASSES, len(gdf)
    assert (gdf['GHSL_class'].value_counts() == SAMPLES_PER_CLASS).all()
    print(f'\nTrimmed to exactly {len(gdf)} points ({SAMPLES_PER_CLASS}/class).')

    # QC tests (Matej's method) run on the FINAL exactly-500/class set only.
    gdf_utm = gdf.to_crs('EPSG:32632')
    coords_utm = np.column_stack([gdf_utm.geometry.x, gdf_utm.geometry.y])
    aoi = ee.FeatureCollection(f'projects/{GEE_PROJECT}/assets/milano_aoi')
    aoi_area_m2 = aoi.geometry().area(1).getInfo()

    ann_df  = ann_report(coords_utm, gdf['GHSL_class'].values, aoi_area_m2)
    dist_df = value_distribution_report(gdf)
    plot_qc_figure(gdf, ann_df, dist_df)

    os.makedirs(os.path.dirname(AEF_OUT_PATH), exist_ok=True)
    gdf_aef.to_file(AEF_OUT_PATH, driver='GPKG')
    print(f'\nWrote {len(gdf_aef)} points -> {AEF_OUT_PATH}')

    os.makedirs(os.path.dirname(S2_OUT_PATH), exist_ok=True)
    gdf_s2.to_file(S2_OUT_PATH, driver='GPKG')
    print(f'Wrote {len(gdf_s2)} points -> {S2_OUT_PATH}')


if __name__ == '__main__':
    t0 = time.time()
    main()
    print(f'\nDone in {time.time() - t0:.0f}s')
