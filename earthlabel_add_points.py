"""Refill the EarthLabel plots that fall outside the new combined valid mask.

The original 450 plots per city (75 per IMD class) were drawn by
earthlabel_point_creation.ipynb from IMD_<city>_2018_reclass.tif. Some now
fall where output/sampling/<city>_combined_valid_mask.tif is 0. This script
draws one replacement per dropped plot with the same rules as the original,
limited to mask pixels:

  - same stratum (IMD class) as the dropped plot, read from the reclass raster
  - candidate pool: one random pixel per class per 250 m tile (seed 42)
  - same-class minimum distance from the original formula, relaxed 10 m at a
    time down to 100 m if needed, against the plots that are kept
  - 500 m from every plot of a different class

Each replacement takes the PLOTID of the plot it replaces, so the city still
has PLOT_001..PLOT_450. Writes data/earthlabel/add_points/<city>_IMD_2018_add_points.csv
in the EarthLabel input format (PLOTID, LON, LAT, ref_label) for every city
that lost plots.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import reproject, Resampling

REPO = Path(__file__).resolve().parent
ADD_DIR = REPO / "data" / "earthlabel" / "add_points"
CITIES = {"Milan": "milan", "Hanoi": "hanoi", "HCMC": "hcmc"}

# Same constraints as earthlabel_point_creation.ipynb
TILE_SIZE = 250
SAMPLES_PER_STRATUM = 75
CROSS_CLASS_MIN_DIST = 500
SAME_CLASS_FLOOR = 100
STEP = 10
SEED = 42


def load_city(city):
    """Reclass raster, the mask on its grid, and the original plots in its CRS."""
    with rasterio.open(ADD_DIR / f"IMD_{city}_2018_reclass.tif") as src:
        img = src.read(1)
        transform, crs, bounds, nodata = src.transform, src.crs, src.bounds, src.nodata
    valid = img != nodata

    with rasterio.open(REPO / "output" / "sampling" / f"{city}_combined_valid_mask.tif") as m:
        if m.transform == transform and m.shape == img.shape and m.crs == crs:
            mask = m.read(1)
        else:
            mask = np.zeros(img.shape, dtype="uint8")
            reproject(m.read(1), mask, src_transform=m.transform, src_crs=m.crs,
                      dst_transform=transform, dst_crs=crs,
                      resampling=Resampling.nearest)

    plots = pd.read_csv(REPO / "data" / "earthlabel" / f"{CITIES[city]}_imd_2018_results_cells.csv",
                        usecols=["PLOTID", "LON", "LAT", "ref_label"])
    plots = gpd.GeoDataFrame(plots, geometry=gpd.points_from_xy(plots.LON, plots.LAT),
                             crs=4326).to_crs(crs)
    plots["stratum_class"] = plots.ref_label.str.replace("IMD_Class_", "").astype(int)
    rows, cols = rasterio.transform.rowcol(transform, plots.geometry.x, plots.geometry.y)
    plots["raster_class"] = img[rows, cols]
    plots["in_mask"] = mask[rows, cols] == 1
    return img, valid, mask == 1, transform, crs, bounds, plots


def candidate_pool(img, usable, transform, crs, bounds):
    """One random pixel per class per TILE_SIZE tile, from usable pixels only.

    Built one band of tile rows at a time: Milan has ~44 M pixels, too many
    to hold as coordinates at once.
    """
    px, py = abs(transform[0]), abs(transform[4])
    row_centre_y = bounds.top - (np.arange(img.shape[0]) + 0.5) * py
    row_grid_y = ((row_centre_y - bounds.bottom) // TILE_SIZE).astype(int)
    parts = []
    for gy in np.unique(row_grid_y):
        band = np.where(row_grid_y == gy)[0]
        r, c = np.where(usable[band[0]:band[-1] + 1])
        if not len(r):
            continue
        r = r + band[0]
        x = bounds.left + (c + 0.5) * px
        df = pd.DataFrame({"stratum_class": img[r, c].astype(int), "x": x,
                           "y": row_centre_y[r], "grid_y": gy,
                           "grid_x": ((x - bounds.left) // TILE_SIZE).astype(int)})
        parts.append(df.groupby(["grid_x", "stratum_class"]).sample(n=1, random_state=SEED))
    pool = pd.concat(parts, ignore_index=True)
    return gpd.GeoDataFrame(pool, geometry=gpd.points_from_xy(pool.x, pool.y), crs=crs)


def refill(city):
    img, valid, in_mask, transform, crs, bounds, plots = load_city(city)

    # The reclass raster must reproduce the strata of the original plots.
    mismatch = plots[plots.raster_class != plots.stratum_class]
    if len(mismatch):
        raise RuntimeError(f"{city}: {len(mismatch)} original plots disagree with "
                           f"the reclass raster:\n{mismatch[['PLOTID', 'ref_label', 'raster_class']]}")

    dropped = plots[~plots.in_mask]
    kept = plots[plots.in_mask]
    print(f"\n== {city}: {len(kept)} plots in mask, {len(dropped)} to replace")
    if dropped.empty:
        return None

    # Same-class spacing from the original formula, over the original valid
    # area, so the new plots follow the spacing the old ones were drawn with.
    area = valid.sum() * abs(transform[0]) * abs(transform[4])
    same_class_min = 1 / (2 * np.sqrt(SAMPLES_PER_STRATUM / area))
    print(f"   same-class start distance: {same_class_min:.1f} m")

    pool = candidate_pool(img, valid & in_mask, transform, crs, bounds)
    accepted = kept[["PLOTID", "stratum_class", "geometry"]].copy()

    # Rarest class first, as in the original.
    need = dropped.groupby("stratum_class").size()
    order = pool.stratum_class.value_counts().reindex(need.index).sort_values().index

    new_rows = []
    for cls in order:
        n = int(need[cls])
        ids = sorted(dropped.loc[dropped.stratum_class == cls, "PLOTID"])
        cands = pool[pool.stratum_class == cls].sample(frac=1, random_state=SEED)
        same = accepted[accepted.stratum_class == cls].geometry
        diff = accepted[accepted.stratum_class != cls].geometry
        # Drop candidates too close to other classes once; that rule is never relaxed.
        far_diff = np.ones(len(cands), bool)
        for g in diff:
            far_diff &= cands.geometry.distance(g).values >= CROSS_CLASS_MIN_DIST
        cands = cands[far_diff]
        d_same = np.full(len(cands), np.inf)
        for g in same:
            d_same = np.minimum(d_same, cands.geometry.distance(g).values)

        threshold, chosen = same_class_min, []
        while True:
            chosen = []
            for i, pt in enumerate(cands.geometry):
                if len(chosen) == n:
                    break
                if d_same[i] < threshold:
                    continue
                if chosen and min(pt.distance(c) for c in chosen) < threshold:
                    continue
                chosen.append(pt)
            if len(chosen) == n or threshold <= SAME_CLASS_FLOOR:
                break
            threshold = max(threshold - STEP, SAME_CLASS_FLOOR)

        if len(chosen) < n:
            raise RuntimeError(f"{city} class {cls}: found {len(chosen)} of {n} "
                               f"even at the {SAME_CLASS_FLOOR} m floor")
        print(f"   class {cls}: {n} new (same-class >= {threshold:.0f} m, "
              f"other classes >= {CROSS_CLASS_MIN_DIST} m) -> {', '.join(ids)}")
        new = gpd.GeoDataFrame({"PLOTID": ids, "stratum_class": cls}, geometry=chosen, crs=crs)
        accepted = pd.concat([accepted, new], ignore_index=True)
        new_rows.append(new)

    new = pd.concat(new_rows, ignore_index=True).sort_values("PLOTID")

    # Every new plot must sit on a mask pixel of its own class.
    r, c = rasterio.transform.rowcol(transform, new.geometry.x, new.geometry.y)
    assert (img[r, c] == new.stratum_class.values).all() and in_mask[r, c].all()

    wgs = new.to_crs(4326)
    out = pd.DataFrame({"PLOTID": wgs.PLOTID, "LON": wgs.geometry.x, "LAT": wgs.geometry.y,
                        "ref_label": "IMD_Class_" + wgs.stratum_class.astype(str)})
    path = ADD_DIR / f"{city}_IMD_2018_add_points.csv"
    out.to_csv(path, index=False)
    print(f"   -> {path.relative_to(REPO)}")
    return out


if __name__ == "__main__":
    for city in CITIES:
        refill(city)
