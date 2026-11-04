"""Milan GHSL-trained maps minus CLMS-trained maps, same predictor (percentage points): the
effect of the training label alone. Milan_GHSL_trained_minus_CLMS compares with the CLMS product.

Output in Paper_needables (figure_jpeg_png: PNG; figure_tiff: TIFF):
  Milan_GHSL_trained_minus_CLMS_trained              2 x 2 panel figure (a-d)
  Milan_GHSL_trained_minus_CLMS_trained_<map>        one map per panel
"""
from imd_maps import DIFF, REPO, basemap, milan, panel_figure, single_map

TITLE = "GHSL-trained − CLMS-trained (percentage points)"

runs = REPO / "output" / "milan"
preds = [  # (run folder, raster name after the label prefix, panel label, file stem)
    ("embedding", "predicted_RF_spatialCV2_Milan.tif", "AlphaEarth", "AlphaEarth"),
    ("percentile", "predicted_RF_S2_Milan.tif", "S2 percentile", "S2percentile"),
    ("median", "predicted_RF_S2_Milan.tif", "S2 median", "S2median"),
    ("stack", "predicted_RF_S2_Milan.tif", "S2 stack", "S2stack"),
]
maps = [((runs / "ghsl" / k / f"GHSL_{f}", runs / "clms" / k / f"IMD_{f}"), l, s) for k, f, l, s in preds]

city = milan()
base = basemap(city)
panel_figure([(r, l) for r, l, _ in maps], city, TITLE, "Milan_GHSL_trained_minus_CLMS_trained",
             ncols=2, base=base, factor=8, style=DIFF)
for raster, label, stem in maps:
    single_map(raster, city, label, TITLE, f"Milan_GHSL_trained_minus_CLMS_trained_{stem}",
               base=base, style=DIFF)
