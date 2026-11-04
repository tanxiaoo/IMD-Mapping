"""Benchmark maps of Milan: CLMS 2018 Imperviousness Density alone, and CLMS 2018 next to
GHSL 2018 (built-up surface fraction).
Output: Paper_needables/figure_jpeg_png (PNG 300 dpi) and figure_tiff (TIFF).
"""
from imd_maps import REPO, basemap, milan, panel_figure, single_map

CLMS = REPO / "data" / "CLMS_2018_Milan_UTM32N.tif"
GHSL = REPO / "data" / "GHSL_2018_Milan_UTM32N.tif"

city = milan()
base = basemap(city)
single_map(CLMS, city, "CLMS Imperviousness Density 2018 (10 m)",
           "Imperviousness density (CLMS)", "Milan_CLMS", base=base)
panel_figure([(CLMS, "CLMS 2018"), (GHSL, "GHSL 2018")], city, "Imperviousness density",
             "Milan_CLMS_GHSL", ncols=2, base=base, factor=8)
