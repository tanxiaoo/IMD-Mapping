"""The sample points and their predictor values, shared by every model.

Two folders under data/:

``data/sample_points/``
    The four point sets: where the samples are, their label and a train/test
    split (used only on the train-test-split branch). Drawn once by notebooks
    00 and 00b with :func:`stratified_sample`: 500 points per class, from the
    pixels where EVERY predictor of the city has a value (combined mask), so
    every predictor uses the same points.

``data/sample_features/``
    One table per (point set, predictor): the same points in the same order,
    the label, the ``split`` column, and that predictor's band values. Written
    once by the 00 notebooks (00 for Milan, 00b for Hanoi and HCMC); every
    modelling notebook reads its table from here and nothing else. A ``.json``
    beside each table records its band names and, for Sentinel-2, the dates and
    composite the bands came from, which the modelling notebooks need to build
    the same image for the full-raster prediction.

Each table keeps the points that have a value under ITS predictor
(:func:`valid_points`): a point lost to water or to no clear observation is a
cost of that predictor, so it is dropped from that table only. The ``split``
always comes from the point set, so a point is never training data for one
predictor and test data for another: each predictor's test set is a subset of
the same test set. Report each table's point count beside its scores. A model
trained on all points simply ignores ``split``. ``pid`` is each point's row in
its point file.

Names are ``{SOURCE}_{CITY}_{PREDICTOR}``: SOURCE is the product the labels
come from (CLMS, GHSL), PREDICTOR one of embedding, S2median, S2stack,
S2percentile.
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parent
POINTS_DIR = REPO / "data" / "sample_points"
FEATURES_DIR = REPO / "data" / "sample_features"

POINT_SETS = {
    ("CLMS", "Milan"): "sample_points_all_CLMS_Milan.gpkg",
    ("GHSL", "Milan"): "sample_points_all_GHSL_Milan.gpkg",
    ("GHSL", "Hanoi"): "sample_points_all_GHSL_Hanoi.gpkg",
    ("GHSL", "HCMC"):  "sample_points_all_GHSL_HCMC.gpkg",
}
UTM_CRS = {"Milan": "EPSG:32632", "Hanoi": "EPSG:32648", "HCMC": "EPSG:32648"}
EMBEDDING_BANDS = [f"A{i:02d}" for i in range(64)]

# The split design, used only where a point set has no stored split.
SPLIT_BLOCK_M, SPLIT_TEST_FRAC, SPLIT_BUFFER_M, SPLIT_SEED = 1000, 0.30, 250, 42


# Where each point set is drawn from: the reference raster, the label column
# name kept from the original files, and the AOI the mask was clipped to.
REFERENCE = {
    ("CLMS", "Milan"): (REPO / "data" / "CLMS_2018_Milan_UTM32N.tif", "IMD"),
    ("GHSL", "Milan"): (REPO / "data" / "GHSL_2018_Milan_UTM32N.tif", "GHSL"),
    ("GHSL", "Hanoi"): (REPO / "data" / "GHSL_2018_Hanoi_UTM48N.tif", "IMD"),
    ("GHSL", "HCMC"):  (REPO / "data" / "GHSL_2018_HCMC_UTM48N.tif", "IMD"),
}
N_PER_CLASS, SAMPLE_SEED, N_CLASSES = 500, 42, 7


def reclass_imd_7(arr):
    """Continuous 0-100 % -> the 7 IMD classes (0 / 1-20 / 21-40 / 41-60 /
    61-80 / 81-99 / 100); -1 elsewhere. The rule the original points use."""
    out = np.full(arr.shape, -1, dtype=np.int8)
    out[arr == 0] = 0
    out[(arr > 0) & (arr <= 20)] = 1
    out[(arr > 20) & (arr <= 40)] = 2
    out[(arr > 40) & (arr <= 60)] = 3
    out[(arr > 60) & (arr <= 80)] = 4
    out[(arr > 80) & (arr < 100)] = 5
    out[arr == 100] = 6
    return out


def combined_mask_image(test_bands, aoi_geom):
    """1 where EVERY image in ``test_bands`` has a value, 0 elsewhere (uint8).

    Pass one band per predictor image: the Sentinel-2 cloud/validity mask is
    applied to a date's whole image, so one band tells whether a pixel has a
    value (median: at least one clear date; stack: one band per date, so clear
    on every date). Images already carry the water mask; 0 outside the AOI.
    """
    import ee

    mask = ee.Image.constant(1)
    for band in test_bands:
        mask = mask.And(band.mask().gt(0))
    return mask.clip(aoi_geom).unmask(0).rename("valid").toUint8()


def stratified_sample(source, city, mask_path, aoi, n=N_PER_CLASS, seed=SAMPLE_SEED):
    """Draw ``n`` points per class from the reference raster, valid pixels only.

    Valid = inside ``aoi`` (a GeoDataFrame or GeoSeries), not nodata, and 1 in
    the combined mask (resampled, nearest, onto the reference grid). Points are
    pixel centres. Writes the point set to data/sample_points/ (label, class,
    split) and returns it with a per-class report of what the mask removed.
    """
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.transform import xy
    from rasterio.warp import Resampling, reproject

    ref_path, label = REFERENCE[(source, city)]
    with rasterio.open(ref_path) as r:
        ref = r.read(1).astype("float32")
        if r.nodata is not None:
            ref[ref == r.nodata] = np.nan
        transform, crs, shape = r.transform, r.crs, r.shape
    ref[(ref < 0) | (ref > 100)] = np.nan
    with rasterio.open(mask_path) as m:
        valid = np.zeros(shape, dtype="uint8")
        reproject(m.read(1), valid, src_transform=m.transform, src_crs=m.crs,
                  dst_transform=transform, dst_crs=crs, src_nodata=None,
                  dst_nodata=0, resampling=Resampling.nearest)
    in_aoi = ~geometry_mask(list(aoi.to_crs(crs).geometry), shape, transform)
    cls = np.where(np.isfinite(ref) & in_aoi, reclass_imd_7(np.nan_to_num(ref, nan=-1)), -1)

    rng = np.random.RandomState(seed)
    rows, cols, report = [], [], []
    for c in range(N_CLASSES):
        in_class = cls == c
        ys, xs = np.where(in_class & (valid == 1))
        if len(ys) < n:
            raise RuntimeError(f"{source} {city} class {c}: only {len(ys)} valid pixels, need {n}.")
        pick = rng.choice(len(ys), n, replace=False)
        rows.append(ys[pick]); cols.append(xs[pick])
        total = int(in_class.sum())
        report.append({"class": c, "pixels_in_aoi": total, "valid_pixels": len(ys),
                       "masked_pct": round(100 * (1 - len(ys) / total), 2)})
    rows, cols = np.concatenate(rows), np.concatenate(cols)
    x, y = xy(transform, rows, cols, offset="center")
    utm = gpd.GeoDataFrame({label: ref[rows, cols].astype("float64"),
                            f"{label}_class": cls[rows, cols].astype(int)},
                           geometry=gpd.points_from_xy(x, y), crs=crs)
    coords = np.column_stack([utm.geometry.x, utm.geometry.y])
    utm["split"] = spatial_split(coords)   # unused on main; kept for the table format
    pts = utm.to_crs("EPSG:4326")
    POINTS_DIR.mkdir(parents=True, exist_ok=True)
    pts.to_file(POINTS_DIR / POINT_SETS[(source, city)], driver="GPKG")
    print(f"  {source} {city}: {len(pts)} points ({n} per class) -> "
          f"{POINTS_DIR / POINT_SETS[(source, city)]}")
    return load_points(source, city), pd.DataFrame(report)


def label_column(gdf):
    """The label column of a point set: GHSL for GHSL Milan, IMD otherwise.

    The Vietnam files carry GHSL values under the generic name IMD; that is
    kept as is so the notebooks that read them need no renaming.
    """
    return "GHSL" if "GHSL" in gdf.columns else "IMD"


def spatial_split(coords, test_frac=SPLIT_TEST_FRAC, block_size=SPLIT_BLOCK_M,
                  buffer_m=SPLIT_BUFFER_M, seed=SPLIT_SEED):
    """'train' / 'test' / 'buffer' per point: whole blocks go to test until
    ``test_frac`` is reached, and test points within ``buffer_m`` of a training
    point become 'buffer' (in neither set). Notebook 01's algorithm; it
    reproduces the CLMS Milan split every CLMS run used (2449 / 1014 / 37)."""
    bx = (coords[:, 0] // block_size).astype(int)
    by = (coords[:, 1] // block_size).astype(int)
    blocks = np.array([f"{x}_{y}" for x, y in zip(bx, by)])
    test_blocks, n = set(), 0
    for b in np.random.RandomState(seed).permutation(np.unique(blocks)):
        if n / len(coords) >= test_frac:
            break
        test_blocks.add(b)
        n += (blocks == b).sum()
    is_test = np.array([b in test_blocks for b in blocks])
    dist, _ = cKDTree(coords[~is_test]).query(coords[is_test], k=1)
    split = np.where(is_test, "test", "train").astype(object)
    split[np.where(is_test)[0][dist <= buffer_m]] = "buffer"
    return split


def load_points(source, city):
    """A fixed point set with its label, class and split, in file order.

    The stored ``split`` column is used as is: it is the split every existing
    run of that point set used. CLMS Milan has none stored, so it is computed
    with :func:`spatial_split`, which reproduces that set's split exactly.
    """
    gdf = gpd.read_file(POINTS_DIR / POINT_SETS[(source, city)]).reset_index(drop=True)
    if "split" not in gdf.columns:
        utm = gdf.to_crs(UTM_CRS[city])
        gdf["split"] = spatial_split(np.column_stack([utm.geometry.x, utm.geometry.y]))
    gdf["pid"] = np.arange(len(gdf))
    return gdf


def valid_points(points, values, name):
    """Keep-mask of the points with a value in every band of ``values``.

    ``values`` holds one predictor's bands in ``points`` order (NaN where a
    point has no value). Prints what the predictor loses, by class and split,
    because that loss is part of how the predictor performs.
    """
    lab = label_column(points)
    keep = values.notna().all(axis=1).to_numpy()
    if keep.all():
        print(f"  {name}: all {len(points)} points have a value")
    else:
        lost = points.loc[~keep, f"{lab}_class"].value_counts().sort_index().to_dict()
        by_split = points.loc[~keep, "split"].value_counts().to_dict()
        print(f"  {name}: {int((~keep).sum())} of {len(points)} points have no value "
              f"and are dropped from this table (by class {lost}, by split {by_split})")
    return keep


def table_name(source, city, predictor):
    return f"{source}_{city}_{predictor}"


def extract_at_points(image, projection, gdf, band_names, chunk_size=500, tile_scale=4):
    """Sample ``image`` at every point of ``gdf``, in ``gdf``'s order.

    Chunked, because a few thousand points in one ``getInfo`` exceeds the
    payload limit. ``sampleRegions`` neither keeps order nor returns masked
    points, so each point carries its row number and the result is reindexed
    on it: a point with no value comes back as a NaN row, never as a shift.
    """
    import ee

    records = []
    n_chunks = int(np.ceil(len(gdf) / chunk_size))
    for ci in range(n_chunks):
        chunk = gdf.iloc[ci * chunk_size:(ci + 1) * chunk_size]
        feats = [ee.Feature(ee.Geometry.Point([p.x, p.y]), {"pid": int(i)})
                 for i, p in zip(chunk.index, chunk.to_crs("EPSG:4326").geometry)]
        sampled = image.sampleRegions(
            collection=ee.FeatureCollection(feats), properties=["pid"],
            scale=10, projection=projection, tileScale=tile_scale, geometries=False)
        records.extend(f["properties"] for f in sampled.getInfo()["features"])
        print(f"    chunk {ci + 1}/{n_chunks}: {len(records)} points returned")
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=["pid"] + list(band_names))
    return df.set_index("pid").reindex(range(len(gdf)))[band_names]


def write_features(points, values, band_names, source, city, predictor, meta=None):
    """Write one feature table and its sidecar JSON; refuse any missing value.

    ``points`` is the output of :func:`load_points`, reduced to this
    predictor's valid points (``points[valid_points(...)]``), and ``values``
    holds the band columns for those same rows. Geometry, label, split and ``pid`` are
    taken from ``points``, never from an Earth Engine round trip, so every
    table of a point set shares them exactly.
    """
    points = points.reset_index(drop=True)
    values = values.reset_index(drop=True)
    missing = values[band_names].isna().any(axis=1).to_numpy()
    if missing.any():
        lab = label_column(points)
        lost = points.loc[missing, f"{lab}_class"].value_counts().sort_index().to_dict()
        raise RuntimeError(
            f"{table_name(source, city, predictor)}: {int(missing.sum())} of "
            f"{len(points)} points have no value (by class: {lost}). Reduce the "
            "points with valid_points() first.")
    lab = label_column(points)
    out = gpd.GeoDataFrame(
        {lab: points[lab].to_numpy(), f"{lab}_class": points[f"{lab}_class"].to_numpy().astype(int),
         "split": points["split"].to_numpy(), "pid": points["pid"].to_numpy(),
         **{b: values[b].to_numpy(dtype="float32") for b in band_names}},
        geometry=points.geometry.to_numpy(), crs=points.crs)
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    name = table_name(source, city, predictor)
    out.to_file(FEATURES_DIR / f"{name}.gpkg", driver="GPKG")
    sidecar = {"source": source, "city": city, "predictor": predictor,
               "label": lab, "band_names": list(band_names), "n_points": len(out),
               "split_counts": out["split"].value_counts().to_dict(),
               "points_file": f"data/sample_points/{POINT_SETS[(source, city)]}",
               **(meta or {})}
    with open(FEATURES_DIR / f"{name}.json", "w") as f:
        json.dump(sidecar, f, indent=2, default=str)
    print(f"  wrote {name}: {len(out)} points, {len(band_names)} bands, "
          f"split {sidecar['split_counts']}")
    return out


def load_features(source, city, predictor):
    """One feature table and its sidecar: ``(gdf, meta)``.

    Checks that the table still matches its point set (each ``pid`` at its own
    location with its own split), so a stale table fails here rather than
    training on the wrong rows.
    """
    name = table_name(source, city, predictor)
    path = FEATURES_DIR / f"{name}.gpkg"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run notebook {'00' if city == 'Milan' else '00b'} "
            "first: it writes every feature table of this city.")
    gdf = gpd.read_file(path)
    with open(FEATURES_DIR / f"{name}.json") as f:
        meta = json.load(f)
    pts = load_points(source, city).to_crs(gdf.crs).iloc[gdf["pid"].to_numpy()]
    same = (np.allclose(np.column_stack([gdf.geometry.x, gdf.geometry.y]),
                        np.column_stack([pts.geometry.x, pts.geometry.y]))
            and (gdf["split"].to_numpy() == pts["split"].to_numpy()).all())
    if not same:
        raise RuntimeError(f"{path} no longer matches {meta['points_file']}; re-run the 00 notebook.")
    return gdf, meta


def split_index(gdf):
    """Row positions of the training and test points ('buffer' is in neither)."""
    s = gdf["split"].to_numpy()
    return np.where(s == "train")[0], np.where(s == "test")[0]
