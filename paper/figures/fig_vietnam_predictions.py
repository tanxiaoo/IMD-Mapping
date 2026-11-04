"""Hanoi and HCMC: GHSL training label, locally retrained predictions (AlphaEarth,
S2 median, S2 stack) and direct-transfer predictions from the Milan models
(AlphaEarth, S2 median), in the same style and legend as the Milan maps.

Output in Paper_needables (figure_jpeg_png: PNG; figure_tiff: TIFF):
  <City>_predictions   2 x 3 panel figure (a-f)
  <City>_<map>         one map per panel
"""
from imd_maps import HANOI, HCMC, REPO, basemap, panel_figure, single_map

TITLE = "Imperviousness density"

for city, key in [(HANOI, "hanoi"), (HCMC, "hcmc")]:
    runs = REPO / "output" / "transfer_vietnam" / key
    n = city.name
    maps = [  # (raster, panel label, file stem)
        (runs / "embedding" / f"IMD_{n}_10m_localrf.tif", "AlphaEarth · local", "AlphaEarth_local"),
        (runs / "median" / f"IMD_{n}_10m_localrf_S2median.tif", "S2 median · local", "S2median_local"),
        (runs / "stack_manual" / f"IMD_{n}_10m_localrf_S2stack_manual.tif", "S2 stack · local", "S2stack_local"),
        (runs / "embedding" / f"IMD_{n}_10m_zeroshot.tif", "AlphaEarth · direct transfer", "AlphaEarth_transfer"),
        (runs / "median" / f"IMD_{n}_10m_zeroshot_S2median.tif", "S2 median · direct transfer", "S2median_transfer"),
        (REPO / "data" / f"GHSL_2018_{n}_UTM48N.tif", "GHSL 2018 (training label)", "GHSL"),
    ]
    base = basemap(city)
    panel_figure([(r, l) for r, l, _ in maps], city, TITLE, f"{n}_predictions",
                 ncols=3, base=base, factor=2)
    for raster, label, stem in maps:
        single_map(raster, city, label, TITLE, f"{n}_{stem}", base=base)
