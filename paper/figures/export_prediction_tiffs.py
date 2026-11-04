"""Uncompressed GeoTIFF copies of the Milan CLMS- and GHSL-trained prediction rasters
(float32, georeferenced, NaN = nodata), saved in Paper_needables/figure_tiff.
"""
import sys

import rasterio

from imd_maps import OUT_TIFF, REPO

RUNS = REPO / "output" / "milan" / "clms"
GHSL_RUNS = REPO / "output" / "milan" / "ghsl"
RASTERS = {
    "Milan_Pred_CLMS_AlphaEarth": RUNS / "embedding" / "IMD_predicted_RF_spatialCV2_Milan.tif",
    "Milan_Pred_CLMS_S2percentile": RUNS / "percentile" / "IMD_predicted_RF_S2_Milan.tif",
    "Milan_Pred_CLMS_S2median": RUNS / "median" / "IMD_predicted_RF_S2_Milan.tif",
    "Milan_Pred_CLMS_S2stack": RUNS / "stack" / "IMD_predicted_RF_S2_Milan.tif",
    "Milan_Pred_GHSL_AlphaEarth": GHSL_RUNS / "embedding" / "GHSL_predicted_RF_spatialCV2_Milan.tif",
    "Milan_Pred_GHSL_S2percentile": GHSL_RUNS / "percentile" / "GHSL_predicted_RF_S2_Milan.tif",
    "Milan_Pred_GHSL_S2median": GHSL_RUNS / "median" / "GHSL_predicted_RF_S2_Milan.tif",
    "Milan_Pred_GHSL_S2stack": GHSL_RUNS / "stack" / "GHSL_predicted_RF_S2_Milan.tif",
}
ONLY = sys.argv[1:]  # optional stem prefixes, e.g. Milan_Pred_GHSL

OUT_TIFF.mkdir(parents=True, exist_ok=True)
for stem, src_path in RASTERS.items():
    if ONLY and not stem.startswith(tuple(ONLY)):
        continue
    with rasterio.open(src_path) as src:
        profile = src.profile
        profile.update(compress=None, tiled=False, nodata=float("nan"), BIGTIFF="IF_SAFER")
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        dst_path = OUT_TIFF / f"{stem}.tif"
        with rasterio.open(dst_path, "w", **profile) as dst:
            dst.write(src.read())
    print("written", dst_path)
