"""Milan IMD predicted by the CLMS-trained random forests (AlphaEarth, S2 percentile,
S2 median, S2 stack).

Output in Paper_needables (figure_jpeg_png: PNG; figure_tiff: TIFF):
  Milan_CLMS_predictions  2 x 2 panel figure (a-d)
  Milan_CLMS_<predictor>  one map per predictor
"""
from imd_maps import REPO, basemap, milan, panel_figure, single_map

RUNS = REPO / "output" / "milan" / "clms"
MAPS = [  # (raster, panel label, file stem)
    (RUNS / "embedding" / "IMD_predicted_RF_spatialCV2_Milan.tif", "AlphaEarth · CLMS", "AlphaEarth"),
    (RUNS / "percentile" / "IMD_predicted_RF_S2_Milan.tif", "S2 percentile · CLMS", "S2percentile"),
    (RUNS / "median" / "IMD_predicted_RF_S2_Milan.tif", "S2 median · CLMS", "S2median"),
    (RUNS / "stack" / "IMD_predicted_RF_S2_Milan.tif", "S2 stack · CLMS", "S2stack"),
]
TITLE = "Predicted imperviousness density"

city = milan()
base = basemap(city)
panel_figure([(r, l) for r, l, _ in MAPS], city, TITLE, "Milan_CLMS_predictions",
             ncols=2, base=base, factor=8)
for raster, label, stem in MAPS:
    single_map(raster, city, label, f"{TITLE} (CLMS-trained)", f"Milan_CLMS_{stem}", base=base)
