"""Difference maps, prediction minus benchmark (percentage points), for every predicted map:
Milan CLMS-trained - CLMS 2018, Milan GHSL-trained - GHSL 2018, and Hanoi / HCMC
(local and direct transfer) - GHSL 2018.

Output in Paper_needables (figure_jpeg_png: PNG; figure_tiff: TIFF):
  Milan_CLMS_difference, Milan_GHSL_difference   2 x 2 panel figures (a-d)
  Hanoi_difference, HCMC_difference              2 x 3 panel figures (a-e)
  <City>_..._difference_<map>                    one map per panel
"""
from imd_maps import DIFF, HANOI, HCMC, REPO, basemap, milan, panel_figure, single_map

TITLE = "Predicted − benchmark (percentage points)"

city = milan()
base = basemap(city)
for label_key, bench in [("CLMS", "CLMS_2018_Milan_UTM32N.tif"), ("GHSL", "GHSL_2018_Milan_UTM32N.tif")]:
    runs = REPO / "output" / "milan" / label_key.lower()
    prefix = "IMD" if label_key == "CLMS" else "GHSL"
    preds = [  # (prediction raster, panel label, file stem)
        (runs / "embedding" / f"{prefix}_predicted_RF_spatialCV2_Milan.tif", "AlphaEarth", "AlphaEarth"),
        (runs / "percentile" / f"{prefix}_predicted_RF_S2_Milan.tif", "S2 percentile", "S2percentile"),
        (runs / "median" / f"{prefix}_predicted_RF_S2_Milan.tif", "S2 median", "S2median"),
        (runs / "stack" / f"{prefix}_predicted_RF_S2_Milan.tif", "S2 stack", "S2stack"),
    ]
    maps = [((p, REPO / "data" / bench), f"{l} − {label_key}", s) for p, l, s in preds]
    panel_figure([(r, l) for r, l, _ in maps], city, TITLE, f"Milan_{label_key}_difference",
                 ncols=2, base=base, factor=8, style=DIFF)
    for raster, label, stem in maps:
        single_map(raster, city, label, TITLE, f"Milan_{label_key}_difference_{stem}",
                   base=base, style=DIFF)

for city, key in [(HANOI, "hanoi"), (HCMC, "hcmc")]:
    runs = REPO / "output" / "transfer_vietnam" / key
    n = city.name
    bench = REPO / "data" / f"GHSL_2018_{n}_UTM48N.tif"
    preds = [
        (runs / "embedding" / f"IMD_{n}_10m_localrf.tif", "AlphaEarth · local", "AlphaEarth_local"),
        (runs / "median" / f"IMD_{n}_10m_localrf_S2median.tif", "S2 median · local", "S2median_local"),
        (runs / "stack_manual" / f"IMD_{n}_10m_localrf_S2stack_manual.tif", "S2 stack · local", "S2stack_local"),
        (runs / "embedding" / f"IMD_{n}_10m_zeroshot.tif", "AlphaEarth · direct transfer", "AlphaEarth_transfer"),
        (runs / "median" / f"IMD_{n}_10m_zeroshot_S2median.tif", "S2 median · direct transfer", "S2median_transfer"),
    ]
    maps = [((p, bench), f"{l} − GHSL", s) for p, l, s in preds]
    base = basemap(city)
    panel_figure([(r, l) for r, l, _ in maps], city, TITLE, f"{n}_difference",
                 ncols=3, base=base, factor=2, style=DIFF)
    for raster, label, stem in maps:
        single_map(raster, city, label, TITLE, f"{n}_difference_{stem}", base=base, style=DIFF)
