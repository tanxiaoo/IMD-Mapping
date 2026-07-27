# IMD-Mapping — Impervious Surface Density Prediction for Milan

Predicting **Copernicus CLMS Imperviousness Density (IMD) 2018** for the Milan
metropolitan area from satellite data, with spatially-aware model validation.

The repository answers one question: **does a learned foundation-model embedding
beat conventional Sentinel-2 reflectance as a predictor of impervious surface
density?** Two pipelines are run under identical conditions so the only
difference is the predictor.

| Pipeline | Predictor | Features |
|---|---|---|
| Embedding | [Google Satellite Embedding V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL) (AlphaEarth Foundations), annual 2018 | 64 (`A00`–`A63`) |
| **Baseline** | Sentinel-2 L2A surface reflectance, cloud-filtered 2018 composite | 10 spectral bands |

---

## Attribution

The original embedding-based pipeline — `01_IMD_Prediction_Milan_blockCV_v2.ipynb`
and `02_Transferability_Vietnam_v2.ipynb`, including the spatial block
cross-validation design, the hyperparameter tuning framework and the GEE export
workflow — was created by:

> **Matej Žgela** — PhD student, Department of Civil and Environmental
> Engineering, Politecnico di Milano

The Sentinel-2 baseline (`00_S2_Extraction_Milan_2018.ipynb`,
`01b_IMD_Prediction_Milan_blockCV_S2.ipynb`, `s2_utils.py`) was added to provide
a controlled comparison, reusing that pipeline's structure unchanged.

---

## Repository contents

```
00_S2_Extraction_Milan_2018.ipynb        Sentinel-2 scene selection + extraction
01_IMD_Prediction_Milan_blockCV_v2.ipynb Embedding pipeline  (Matej Žgela)
01b_IMD_Prediction_Milan_blockCV_S2.ipynb Sentinel-2 baseline (copy of 01)
02_Transferability_Vietnam_v2.ipynb      Hanoi / HCMC transfer (Matej Žgela)
s2_utils.py                              Shared S2 masks + composite builder
requirements.txt
```

> **Code only.** Rasters (~1 GB), trained models, sample points, figures and
> metrics are gitignored — they are regenerable by running the notebooks, and
> the GeoTIFFs exceed GitHub's 100 MB limit. See [Reproducing](#reproducing).

---

## Method

### Spatial validation

Ordinary random cross-validation leaks information between nearby points and
inflates accuracy. This pipeline instead uses **spatial block CV**:

- Points are assigned to a square grid in UTM 32N (500 m / 1 km / 2 km blocks).
- Whole *blocks* — never individual points — are assigned to folds.
- A **250 m buffer** drops validation points too close to any training point.
- A locked ~70/30 train/test split on 1 km blocks is evaluated exactly once.
- CV is repeated 5× with re-drawn fold assignments (25 fold scores total).

Models: Random Forest, SVR, MLP (scikit-learn), tuned with `RandomizedSearchCV`
under the same spatial folds. The best model is retrained server-side in GEE
(`ee.Classifier`) and exported as a 10 m raster.

### The controlled comparison

Both runs use the **same 3500 sample points** (500 per IMD class × 7 classes),
the same labels, and the **same train/test split** — the split is *imported*
from the embedding run rather than recomputed, because reusing a random seed is
not sufficient:

> The greedy block split is a function of the surviving row set. If a single
> point is dropped and it was the only point in its 1 km block, that block
> disappears from the array being permuted, so the same seed yields a
> *different* split. Whole blocks can flip between train and test.

`01b` therefore joins on point geometry to recover the exact membership
(2449 train / 1014 test / 37 buffer-removed) and asserts that `y_train` and
`y_test` are element-wise identical to the embedding run. **Only `X` differs.**

A side benefit: identical holdout points make the two runs *paired*, so the
difference can be tested with a Wilcoxon signed-rank test on per-point errors
rather than by comparing two independent RMSE numbers.

### Sentinel-2 scene selection

`COPERNICUS/S2_SR_HARMONIZED` scenes for 2018 are scored per acquisition date on
**three independent criteria** — a date must pass all three:

| Criterion | Catches |
|---|---|
| `AOI_cloud%` | cloud / shadow / cirrus over the AOI |
| `valid%` | full SCL validity — also no-data, saturated, snow |
| `coverage%` | partial swaths — a scene covering ⅓ of the AOI can still read 0% cloud |

Statistics are computed **over the AOI**, not from scene-level
`CLOUDY_PIXEL_PERCENTAGE`, which describes a whole MGRS tile and is misleading
for a sub-tile study area. Milan spans more than one tile, so scenes are
mosaicked per date before scoring.

Selected dates are combined by per-pixel **median**. Masking is applied *before*
the reduction, so cloudy observations are excluded from the sample entirely —
never averaged in.

**Bands** (10, all resampled to 10 m): `B2 B3 B4 B5 B6 B7 B8 B8A B11 B12`.
The 20 m SWIR bands are included deliberately — B11/B12 are the strongest
impervious-surface signal, and a 4-band baseline would lose to a 64-dimensional
embedding partly on feature count alone.

---

## Reproducing

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Unix
pip install -r requirements.txt

earthengine authenticate
```

Set your GEE project id (`GEE_PROJECT`) in the config cell of each notebook, and
upload your AOI polygon as a GEE asset (`projects/<you>/assets/milano_aoi`).

### Sentinel-2 baseline

1. **`00_S2_Extraction_Milan_2018.ipynb`** — run cells 1–5, read the ranked
   scene table, set `SELECTED_DATES` in cell 6, then run to the end.
   Writes `samples_S2/sample_points_all_S2.gpkg` (3500 points × 10 bands).

   The notebook **asserts all 3500 points resolve**. A shortfall is never
   random — masked pixels cluster on water and cloud, which would bias the
   uniform 500/class design — so it raises rather than silently accepting a
   subset. Add another date and re-run from cell 7.

2. **`01b_IMD_Prediction_Milan_blockCV_S2.ipynb`** — run top to bottom, pausing
   after the GEE export cell to download the two GeoTIFFs from Drive into
   `outputs_S2/`, then continue. Requires `outputs_v2/spatial_{train,test}_pts.gpkg`
   from the embedding run to import the split.

### Notes

- **Earth Engine quota.** Scene scoring is aggregation-heavy and GEE's quota is
  rate-based. If you hit `Too many concurrent aggregations`, lower `SCORE_BATCH`
  (default 6) and/or raise `QA_SCALE` from 60 m.
- **2018 L2A coverage.** GEE's surface-reflectance archive is incomplete over
  Europe for 2018. The notebook stops with an explicit message rather than
  silently substituting TOA — switching to `COPERNICUS/S2_HARMONIZED` is a
  decision with radiometric consequences, so it is left to you.
- **Band heterogeneity.** 2018 S2_SR scenes are not band-homogeneous: some order
  `MSK_CLDPRB, MSK_SNWPRB, QA10…` and others `QA10, …, MSK_CLDPRB`. GEE requires
  matching band *order*, so `s2_utils.harmonize()` normalises every image before
  any mosaic or median.

---

## Data sources

| Dataset | Use |
|---|---|
| Copernicus CLMS Imperviousness Density 2018, 10 m | target variable (Milan) |
| Google Satellite Embedding V1 (Annual) | embedding predictor |
| Copernicus Sentinel-2 L2A (`S2_SR_HARMONIZED`) | baseline predictor |
| ESA WorldCover v200 | water masking |
| GHSL built-up surface | target variable (Hanoi / HCMC transfer) |

---

## License

No license is currently specified. The original embedding pipeline is the work
of Matej Žgela (Politecnico di Milano) — please contact the author regarding
reuse.
