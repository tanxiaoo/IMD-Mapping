"""Milan GHSL-trained maps minus CLMS 2018 (percentage points): the map counterpart of the
GHSL-trained - CLMS table, unlike Milan_GHSL_difference, which compares with GHSL.

Output in Paper_needables (figure_jpeg_png: PNG; figure_tiff: TIFF):
  Milan_GHSL_trained_minus_CLMS              2 x 2 panel figure (a-d)
  Milan_GHSL_trained_minus_CLMS_<map>        one map per panel
"""
from imd_maps import DIFF, REPO, basemap, milan, panel_figure, single_map

TITLE = "GHSL-trained map − CLMS (percentage points)"

runs = REPO / "output" / "milan" / "ghsl"
bench = REPO / "data" / "CLMS_2018_Milan_UTM32N.tif"
preds = [  # (prediction raster, panel label, file stem)
    (runs / "embedding" / "GHSL_predicted_RF_spatialCV2_Milan.tif", "AlphaEarth", "AlphaEarth"),
    (runs / "percentile" / "GHSL_predicted_RF_S2_Milan.tif", "S2 percentile", "S2percentile"),
    (runs / "median" / "GHSL_predicted_RF_S2_Milan.tif", "S2 median", "S2median"),
    (runs / "stack" / "GHSL_predicted_RF_S2_Milan.tif", "S2 stack", "S2stack"),
]
maps = [((p, bench), f"{l} (GHSL) − CLMS", s) for p, l, s in preds]

city = milan()
base = basemap(city)
panel_figure([(r, l) for r, l, _ in maps], city, TITLE, "Milan_GHSL_trained_minus_CLMS",
             ncols=2, base=base, factor=8, style=DIFF)
for raster, label, stem in maps:
    single_map(raster, city, label, TITLE, f"Milan_GHSL_trained_minus_CLMS_{stem}",
               base=base, style=DIFF)
