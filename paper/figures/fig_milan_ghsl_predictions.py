"""Milan IMD predicted by the GHSL-trained random forests (AlphaEarth, S2 percentile,
S2 median, S2 stack).

Output in Paper_needables (figure_jpeg_png: PNG; figure_tiff: TIFF):
  Milan_GHSL_predictions  2 x 2 panel figure (a-d)
  Milan_GHSL_<predictor>  one map per predictor
"""
from imd_maps import REPO, basemap, milan, panel_figure, single_map

RUNS = REPO / "output" / "milan" / "ghsl"
MAPS = [  # (raster, panel label, file stem)
    (RUNS / "embedding" / "GHSL_predicted_RF_spatialCV2_Milan.tif", "AlphaEarth · GHSL", "AlphaEarth"),
    (RUNS / "percentile" / "GHSL_predicted_RF_S2_Milan.tif", "S2 percentile · GHSL", "S2percentile"),
    (RUNS / "median" / "GHSL_predicted_RF_S2_Milan.tif", "S2 median · GHSL", "S2median"),
    (RUNS / "stack" / "GHSL_predicted_RF_S2_Milan.tif", "S2 stack · GHSL", "S2stack"),
]
TITLE = "Predicted imperviousness density"

city = milan()
base = basemap(city)
panel_figure([(r, l) for r, l, _ in MAPS], city, TITLE, "Milan_GHSL_predictions",
             ncols=2, base=base, factor=8)
for raster, label, stem in MAPS:
    single_map(raster, city, label, f"{TITLE} (GHSL-trained)", f"Milan_GHSL_{stem}", base=base)
