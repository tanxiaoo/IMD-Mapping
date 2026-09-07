# Experiment Map

How the notebooks, sample tables and output directories in this repo relate.
Directory names alone do **not** identify a producer — read this file, or the
`method` / `percentiles` fields in each run's metadata JSON.

Last updated: 2026-08-30

## Pipeline

```
Matej (external) ──► outputs_sampling/ ─┬─► 00  ──► samples_S2_<method>/ ──► 01b ──► outputs_S2_<method>/ ─┐
                     samples_IMD/ (idle)└─► 01  ────────────────────────────────────► outputs_v2/         ─┤
                                                                                                           ├─► 04 ──► outputs_validation/
                     00b ──► samples_S2_vietnam/         ──► 02 ──► outputs_transfer_v2/        ─┤
                             samples_S2_median_<city>/       03 ──► outputs_transfer_S2_median/ ─┘
```

## Output directories

| Directory | Notebook | City | Predictors | Model | Mode |
|---|---|---|---|---|---|
| `outputs_v2` | 01 | Milan | **AlphaEarth embeddings** — 64-d, `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` | RF + SVR reported (a third estimator is tuned but out of scope) | local train |
| `outputs_S2_stack` | 01b `'stack'` | Milan | **S2 stack** — 40 bands, 4 dates | RF + SVR | local train |
| `outputs_S2_median` | 01b `'median'` | Milan | **S2 median** — 10 bands, 30 dates | RF + SVR | local train |
| `outputs_S2_percentile_p10p25p50p75p90` | 01b `'percentile'` | Milan | **S2 percentile** — 50 bands, 30 dates | RF + SVR | local train |
| `outputs_transfer_v2` | 02 | Hanoi + HCMC | AlphaEarth embeddings | RF | **both** — `_zeroshot` = Milan RF applied directly (Scenario A); `_localrf` = local retrain, spatial block CV (Scenario B) |
| `outputs_transfer_S2_median` | 03 | Hanoi + HCMC | S2 median — 4 dates Hanoi / 3 HCMC (thin) | RF | **both**, same A/B pair |
| `outputs_validation` | 04 | Milan + Hanoi + HCMC | consumes 15 rasters | RF only (fixed by design) | scores everything above |

## Input and sample directories

| Directory | Source | City | Contents |
|---|---|---|---|
| `outputs_sampling` | **Matej (external)** | Milan | Shared point set — read-only; all Milan work builds on it |
| `samples_IMD` | **Matej (external)** | — | Archive, unused |
| `samples_S2_median` · `_stack` · `_percentile_p10p25p50p75p90` | 00, per method | Milan | Predictor tables + extraction metadata |
| `samples_S2_vietnam` | 00b | Hanoi + HCMC | Scene-candidate CSVs only (method-independent, shared) |
| `samples_S2_median_Hanoi` · `_HCMC` | 00b | Hanoi / HCMC | Screened dates metadata only — **no predictor table**; 03 extracts inline |

## Structural notes

**One notebook, many directories.** All `outputs_S2_*` come from 01b re-run with
a different `COMPOSITE_METHOD` / `PERCENTILES`; the directory name is derived
from those constants. Same for `samples_S2_*` from 00. `PERCENTILES` is a free
parameter — the tagging scheme exists so several sets coexist without
overwriting.

**Model columns.** `best_model_RF_*.joblib` is written unconditionally;
`best_model_<BEST>.joblib` records whichever model won CV. Notebook 04 validates
the RF raster from every directory regardless, holding the estimator fixed so the
comparison isolates the predictor set.

**Transfer axis.** Milan runs are all local-train. Notebooks 02 and 03 each emit
a zero-shot and a local-retrain raster per city, giving 04 its
2 feature-sets × 2 scenarios × 2 cities grid, plus CLMS/GHSL as `role='reference'`.

## Design decisions

### Photo-interpreted validation points

Produced by **Keerthana Kirubakaran** in **Google Earth Pro** on **2018** imagery
(matching the target year), labelled with **EarthLabel**.

| File | Plots |
|---|---|
| `data/milan_imd_2018_results_cells.csv` | 450 |
| `data/hanoi_imd_2018_results_cells.csv` | 450 |
| `data/hcmc_imd_2018_results_cells.csv` | 450 |
| **Total** | **1350** |

Each plot is a 10 m unit area (`ua_size_m=10`) — one Sentinel-2 pixel —
subdivided into a 3×3 grid (`assessment_mode='grid'`, `cell_grid='3x3'`), giving
the `cell_0`…`cell_8` columns. `ref_label` is the sampling stratum, not truth;
truth is the per-cell interpretation. Notebook 04 keys on numeric `code`, never
on `label` — the labels have spelling variants and a missing `Impervious` prefix
on railroads that would silently misclassify them.

### Vietnam composite choice: median was a constraint, not a preference

Percentile was the best-performing composite in Milan, but it was **not available**
in Vietnam. After cloud screening the 2018 L2A archive yields **4** usable dates
over Hanoi and **3** over HCMC. Percentiles need ≥ 17 dates; **no further usable
scenes exist**, and no relaxation of the screening thresholds can produce them —
notebook 00b tests this explicitly against an `ALL (ceiling)` rung that disables
every threshold, and still falls short. Median has no minimum, so it was the only
method that could be computed at all.

This is an archive limitation, not a modelling choice, and it should not be
reported as a preference for median.

Consequence for interpretation: the Milan median is built from ~30 looks per
pixel, Vietnam's from 2–4. Both sides use the same method and bands, so the
comparison is structurally fair — but if Scenario A transfers poorly, composite
depth and genuine transfer failure are confounded. Rule depth out first. See
[Composite date windows](#composite-date-windows) for the full depth accounting.

### `samples_S2_percentile_p25p50p75` (30-band) — superseded

A 30-band percentile variant (p25/p50/p75) was extracted and modelled, but was
superseded by the 50-band p10/p25/p50/p75/p90 set and its directories have been
deleted.

It was **never validated or analysed**: it is absent from notebook 04's
`MAP_REGISTRY` and from `make_presentation.py`. The run had produced an SVR model,
tuning and holdout CSVs, and both RF and SVR rasters.

Confirmed on 2026-08-30: both `samples_` and `outputs_` directories are deleted.
The only surviving mentions are three explanatory comments in notebooks 00 and
01b; no code path reads the tag.

### Estimator selection: SVR won CV, RF was carried forward

In the embeddings run (`outputs_v2`), **SVR won cross-validation** and
`model_metadata_spatialcv.json` records `best_model_name='SVR'` — `BEST_MODEL_NAME`
is chosen on CV RMSE alone ([01](../01_IMD_Prediction_Milan_blockCV_v2.ipynb)
cell 22). **RF was nonetheless carried forward** to Vietnam and to validation.

The reversal is real and is on the holdout:

| | RF | SVR | Winner |
|---|---|---|---|
| Tuning CV RMSE (best block) | 13.162 @ 1000m | **11.711 @ 500m** | SVR by 1.45 |
| Spatial CV eval @ 500m | 13.26 | **11.60** | SVR by 1.66 |
| **Holdout RMSE** | **14.123** | 14.756 | **RF** |
| Holdout MAE | **10.675** | 11.400 | **RF** |
| Holdout R² | **0.837** | 0.822 | **RF** |

SVR wins CV at every block size, then loses the independent holdout on all three
metrics. Two caveats on reading that reversal as overfitting:

- The holdout rows are `GEE_RF` / `GEE_SVR` — scored on rasters built by GEE's
  `smileRandomForest` and `libsvm`, **not** by the tuned sklearn models. The CV
  numbers are sklearn. The comparison is therefore confounded with how faithfully
  each GEE estimator reproduces its sklearn counterpart.
- The parameter translation in `train_gee_regressor` is lossy in both directions:
  RF passes only `numberOfTrees` and `minLeafPopulation`, dropping `max_features`,
  `max_samples` and `max_depth`; SVR passes `kernel`, `C`, `gamma`, `epsilon`.

**SVR is not unsupported in GEE.** `ee.Classifier.libsvm(svmType='EPSILON_SVR')
.setOutputMode('REGRESSION')` is used in cell 34, and
`outputs_v2/IMD_predicted_SVR_spatialCV2_Milan.tif` exists. The operative reason RF
is carried forward is the unconditional save in cell 34 —
`# Always save RF separately (needed for Vietnam transferability)` — written
regardless of which model wins CV, because notebook 02 requires an RF.

**Notebook 04 holds the estimator fixed at RF across every run**, so the validation
comparison isolates the predictor set rather than confounding predictor with
estimator.

### Backfilled metadata fields — `provenance = "backfilled"`

`holdout_rmse`, `best_params` and `best_block` in every
`outputs_S2_*/model_metadata_S2.json` were written by
`00c_backfill_S2_models.ipynb`, a one-off repair for models 01b failed to save on
those runs. 01b now saves models correctly and is the producer of record; 00c has
been deleted and is not a live dependency.

**These fields are kept, and must be labelled `provenance = "backfilled"`
wherever they are used** — in tables, figures and the write-up. They were not
produced by the current code and are not reproducible from this repo.

The `method`, `band_names` and `selected_dates` fields in the same files are
independently corroborated by the matching
`samples_S2_*/s2_extraction_metadata.json` and need no such label.

## Relationship to the Žgela reference report

`reference/RELAZIONE FINALE - Zgela_LCZ-UHI-GEO_Incarico_Report_signed (1).pdf`
(Matej Žgela, 12 pp) is the study this project extends. The AlphaEarth method and
the shared Milan sample set (`outputs_sampling`) are his work, used here as
supplied.

**The embeddings baseline reproduces his published figures exactly**, for both
estimators (Žgela p. 5):

| | RF | SVR |
|---|---|---|
| Žgela p. 5 | R² 0.837, MAE 10.68, RMSE 14.12, Bias +0.62 | 0.822 / 11.40 / 14.76 / +0.27 |
| This project (`outputs_v2`) | 0.837 / 10.675 / 14.123 / +0.624 | 0.822 / 11.400 / 14.756 / +0.274 |

This is **verification that the shared baseline is correctly reconstructed**, not
a new result.

Two findings in this project are reproductions of his, and must be reported as
such rather than as new observations:

- **The CV-versus-holdout reversal** (p. 5). He reports SVR best on CV at 11.5 %
  with RF ~1.6 % worse, then RF winning every holdout metric, and selects RF.
  Note that his reason for excluding a third estimator is that it is unsupported
  in GEE's Python API — that does **not** apply to SVR, which is supported
  (`ee.Classifier.libsvm`) and is rastered in this project.
- **Bias recovery** (p. 10). He observed qualitatively that roads and unroofed
  impervious surfaces "are visibly better represented in the predicted maps",
  which "highlights the ability of the model to recover additional information
  beyond what was explicitly provided during training." This project's
  contribution is to **quantify** that against an independent reference
  (7.57–13.09 pp, 38–67 % of the deficit) — see the bias-recovery table in
  `FACTS.md`.

He also states the GHS-BUILT-S road exclusion himself (pp. 8, 10), and records
that no other suitable 2018 reference existed for Vietnam. Cite him for that
limitation rather than asserting it independently.

Design parameters he established, reused unchanged here (pp. 2, 4): 7 IMD groups,
500 points each = 3 500; 1 km blocks assigned whole to train or test; 250 m
buffer; **2 449 train / 1 014 test**; spatially aware 5-fold CV over 500 m / 1 km
/ 2 km blocks. All 64 embedding bands are used because his feature-selection
experiment found any reduced subset worse (p. 5).

## Validation unit of analysis

**n = 450 plots per city, 1350 total. The 3×3 sub-cells are never observations.**

The nine interpreted sub-cells are collapsed to one number per plot before
anything is scored ([04](../04_Validation_PhotoInterpreted.ipynb) cell 7):

```python
def compute_ref_imd(cells_json, impervious):
    codes = [d['code'] for d in json.loads(cells_json)]
    kept  = [c for c in codes if c not in DROP_CODES]
    n_imp = sum(c in impervious for c in kept)
    return 100.0 * n_imp / len(kept), len(kept), len(codes) - len(kept)
```

Plot IMD is the **percentage of the 9 sub-cells that are impervious**. Codes in
`DROP_CODES` (code 15, `'Rock/material'`, n=1, Milan only) are removed and **the
denominator renormalised**, so a plot with one ambiguous cell scores out of 8
rather than being discarded.

`long_df` is one row per **plot × map × rule**; `compute_metrics` runs on
`ref_imd` vs `pred_imd`, and every table is a `groupby` on that frame. Table 1
reports `N = 450`.

The sub-cells survive in exactly two derived quantities:

- **`n_cells_kept`** feeds `reference_noise()` — the binomial SE
  `100 · sqrt(mean(p(1−p)/n))` — which produces `RMSE_corr`, the noise-corrected
  RMSE reported alongside the raw value.
- **`ref_level`** = `round(ref_imd/100 × n_cells_kept)`, an integer 0–9 giving the
  native measurement resolution, used for the per-level breakdown in
  `table4_perlevel_metrics.csv`.

**Sub-cells within a 10 m pixel are spatially correlated**, so the independent-draw
assumption behind `reference_noise()` understates the true reference noise. This is
why `RMSE_corr` is an **upper bound** on map error, never a point estimate: use it
to say "map error is at most ~22 %, not ~25 %", never to claim a specific map's
error equals the corrected figure.

**Plot-level independence is assumed and untested.** The 450 plots per city are
treated as independent observations in every metric and paired test; no spatial
autocorrelation check is applied at plot level.

### The three impervious rules

`long_df` carries one row per **plot × map × rule**. The three rules differ only
in `ref_imd` — the prediction never changes — and are defined in
[04](../04_Validation_PhotoInterpreted.ipynb) cell 5:

```python
IMPERVIOUS_STRICT = {6, 7, 8, 9, 10, 14, 16}   # parking, pavement, road, roof,
                                               # railroad, airport, pool
PERVIOUS_STRICT   = {1, 2, 3, 4, 11, 12}       # trees, grass, bare soil, water,
                                               # permeable pavement, dirt road
DROP_CODES        = {15}                       # 'Rock/material' -- ambiguous

RULES = {
    'strict': IMPERVIOUS_STRICT,
    'B':      IMPERVIOUS_STRICT | {11},        # permeable pavement -> impervious
    'C':      IMPERVIOUS_STRICT | {12},        # dirt road          -> impervious
}
```

| Rule | Impervious codes | Difference |
|---|---|---|
| **strict** (primary) | 6, 7, 8, 9, 10, 14, 16 | — |
| **B** | strict + **11** | permeable pavement counts as impervious; matches CLMS's sealed-surface definition |
| **C** | strict + **12** | unpaved dirt road counts as impervious; compacted surfaces behave hydrologically as sealed |

**`strict` is the primary rule for reporting.** Table 1, all figures and the paired
tests use it (`strict = long_df[long_df['rule'] == 'strict']`, cell 18);
`validation_summary.json` records `'primary_rule': 'strict'`. B and C are
sensitivity analyses, reported in `table3_rule_sensitivity.csv`.

Code 15 (`'Rock/material'`, n=1, Milan only) is dropped under **all three** rules
and the denominator renormalised.

#### How each rule treats roads — and why it matters for GHSL

Roads appear under three distinct codes, treated differently:

| Code | Label | strict | B | C |
|---|---|---|---|---|
| **8** | Road / Asphalt | impervious | impervious | impervious |
| **10** | Railroad tracks / ballast beds | impervious | impervious | impervious |
| **12** | Unpaved dirt road / heavily compacted bare soil | *pervious* | *pervious* | **impervious** |
| **11** | Permeable pavement / interlocking concrete | *pervious* | **impervious** | *pervious* |

So **paved roads (code 8) count as impervious under every rule, including the
primary one.** Only unpaved dirt roads move, and only under rule C.

This interacts directly with the GHSL comparison. **GHS-BUILT-S measures built-up
surface and excludes roads by design**, while the photo-interpreted reference counts
paved roads as impervious under all three rules. Part of GHSL's large positive bias
(≈ +20, i.e. it understates imperviousness) is therefore **structural** — a
definitional mismatch between target and reference, not random error. Rule C widens
the gap further by adding dirt roads; strict and B do not.

Read GHSL's disagreement accordingly: it is partly a property of what GHS-BUILT-S
sets out to measure, and is not evidence about model quality in either direction.
Cell 5's code→label crosstab keys on numeric `code` precisely because code 10 appears
as `'Railroads Tracks / Ballast Beds '` with no `Impervious` prefix — a
`label.startswith('Impervious')` heuristic would silently score railroads pervious.

### Bias sign convention

**Bias = observed − predicted (reference − map), in both tracks.** They already
agree; nothing was harmonised.

| Track | Definition | Location |
|---|---|---|
| independent validation (independent validation) | `Bias = float(np.mean(yt - yp))`; docstring `"Bias (obs-pred)"`; `'error': ref - pred, # obs - pred (repo convention)` | [04](../04_Validation_PhotoInterpreted.ipynb) cells 14, 16 |
| same-source validation Vietnam | `float(np.mean(y_te - y_pred_zs))`, `..._lr`; per-class `np.mean(obs_c - pred_c)` | [02](../02_Transferability_Vietnam_v2.ipynb) / [03](../03_Transferability_Vietnam_S2_median.ipynb) cells 7, 17 |
| same-source validation Milan | `float(np.mean(yte - yp))`, `np.mean(y_test - yp)` | [01](../01_IMD_Prediction_Milan_blockCV_v2.ipynb) / [01b](../01b_IMD_Prediction_Milan_blockCV_S2.ipynb) cells 16, 36/37 |

Therefore:

- **Positive bias → the map UNDER-predicts** (reference is higher than the map).
- **Negative bias → the map OVER-predicts** (the map reads higher than reference).

Notebook 04 states this explicitly in two places: the per-level table header
`'Bias by reference level (pp; positive = under-prediction)'` (cell 27) and the
Figure 3 axis label `'Mean error, obs − pred (pp) / + = under-prediction'`
(cell 31).

**Reconciliation with the GHS-BUILT-S roads argument.** Under this convention the
roads argument and the measured sign **agree** — verified directly on the plot
values:

| City | Target | mean reference | mean target | Bias | Reading |
|---|---|---|---|---|---|
| Milan | CLMS | 38.72 | 36.45 | +2.26 | CLMS under-states by 2.26 pp |
| Hanoi | GHSL | 46.05 | 26.37 | +19.68 | GHSL **under**-states by 19.68 pp |
| HCMC | GHSL | 51.06 | 31.26 | +19.80 | GHSL **under**-states by 19.80 pp |

GHSL reads ~26–31 % impervious where interpreters see ~46–51 %. It under-marks
sealed area by ~20 points, exactly as excluding roads by design would predict. No
correction to the roads argument is required.

Note the Vietnam same-source validation biases are **negative** (−23 to −30 for zero-shot): there
the *models* over-predict relative to GHSL. Same convention, different comparison —
same-source validation compares model against GHSL, independent validation compares GHSL against interpretation.
The two are not in conflict, and the signs must not be read across tracks.

### independent validation reference results — all three cities

The training targets scored against the photo-interpreted plots, strict rule,
n = 450 per city (`table1_headline_ci.csv`):

| City | Target | RMSE | RMSE 95% CI | RMSE_corr | MAE | Bias | R² |
|---|---|---|---|---|---|---|---|
| **Milan** | **CLMS** | **26.25** | [23.3, 29.1] | 24.41 | 14.61 | **+2.26** | 0.605 |
| Hanoi | GHSL | 40.35 | [37.5, 43.2] | 38.83 | 27.05 | +19.68 | 0.187 |
| HCMC | GHSL | 37.35 | [34.6, 40.1] | 35.60 | 25.73 | +19.80 | 0.305 |

**CLMS is far better calibrated than GHSL.** Its bias is +2.26 against GHSL's ≈ +20,
consistent with CLMS measuring sealed surface (roads included) while GHS-BUILT-S
excludes roads by design.

CLMS's RMSE of 26.25 is nonetheless **no better than the Milan models it trained**
(24.64–25.98) — the indistinguishability result. Note CLMS has the *best* MAE
(14.61 vs 16.49–18.36) but the *worst* RMSE: it is right more often than the models
but wrong by more when wrong, whereas the models spread moderate error evenly. Quote
one metric consistently; the MAE column does not contradict the target-quality
argument.

## Same-source validation metrics

same-source validation scores each run against the source it was trained on: **CLMS** in Milan,
**GHSL** in Vietnam. Distinct from notebook 04 (independent validation), which scores against
independent photo-interpretation.

### Milan runs — identical structure in all four

| Quantity | File | Fields | Scope |
|---|---|---|---|
| RMSE / MAE / R² / Bias | `holdout_test_metrics.csv` | `Model,RMSE,MAE,R2,Bias`; rows `GEE_RF`, `GEE_SVR` | global, **both models** |
| Same four | `model_metadata_*.json` | `holdout_rmse`, `holdout_mae`, `holdout_r2`, `holdout_bias` | global, **best model only** |
| Per-class | `perclass_metrics_GEE_RF.csv`, `perclass_metrics_GEE_SVR.csv` | — | **per-class, both models** |
| CV (not holdout) | `spatial_cv_summary.csv`, `hyperparameter_tuning.csv` | `RMSE_mean`, `CV_RMSE`, … | per model × block size |

RF holdout values:

| Run | RMSE | MAE | R² | Bias | best model (CV) |
|---|---|---|---|---|---|
| `outputs_v2` (embeddings) | 14.123 | 10.675 | 0.837 | +0.624 | SVR @ 500m |
| `outputs_S2_median` | 11.285 | 7.820 | 0.896 | +0.046 | RF @ 500m |
| `outputs_S2_stack` | 10.864 | 7.641 | 0.904 | −0.169 | RF @ 1000m |
| `outputs_S2_percentile_p10…p90` | 9.462 | 6.389 | 0.927 | −0.104 | RF @ 1000m |

**The JSON copies of `holdout_*` are the backfilled ones; the CSVs are the source
of record.** They agree exactly, so either can be quoted — but cite the CSV, and
label the JSON values `provenance = "backfilled"` if used (see above).

### Vietnam runs — both transfer directories

| Quantity | File | Fields | Scope |
|---|---|---|---|
| RMSE / MAE / R² / Bias | `transferability_comparison.csv` | `Scenario,City,Approach,RMSE,MAE,R2,Bias` — 5 rows: Milan baseline + A/B × 2 cities | global |
| Same, nested | `transfer_summary.json` | `<city>/zero_shot/{RMSE,MAE,R2,Bias}`, `<city>/local_rf/{…}`, plus `best_cv_block_m`, `cv_rmse_tune`, `n_samples_train`, `n_samples_test`, `buffer_removed` | global |
| Per-class | `per_class_metrics.csv` | `City,Scenario,Class,N,RMSE,MAE,Bias` | per-class |

**Nothing is missing and nothing is notebook-output-only** — every run in all six
directories has RMSE/MAE/R²/Bias on disk, globally and per class.

**Vietnam per-class R² was added on 2026-08-31** (notebooks 02 and 03, cell 17)
and both notebooks re-run. Their headline metrics reproduced bit-identically, so
the change is purely additive.

**Read the per-class R² with care — it is not comparable to the global R².**
Restricting to one IMD class removes most of the observed variance, so the
denominator of R² collapses and a modest offset produces a large negative value.
Every defined per-class value is negative: **−1.3 to −115.6** (embeddings),
**−6.6 to −80.7** (S2 median), while the same models reach global R² of 0.52–0.65
in the local-retrain scenario. Both are correct; they answer different questions.
Quote per-class RMSE, MAE or Bias for within-class performance, and reserve R²
for the global comparison.

Classes 0 and 6 are **blank by design**: they are the single-valued 0 % and 100 %
strata, so observed variance is exactly zero and R² is undefined rather than 0.
The guard is `np.ptp(obs_c) > 0`, else `NaN`.

## Composite date windows

| Composite | n | Dates | Months | Character |
|---|---|---|---|---|
| **Milan median** | 30 | 2018-03-23 → 2018-12-08 | 9/12 (no Jan, Feb, May) | Near-annual, growing-season weighted |
| **Milan percentile** | 30 | identical list to median | 9/12 | Near-annual (same dates) |
| **Milan stack** | 4 | 03-23, 06-16, 08-05, 10-24 | 4/12 | Four-season snapshot, one date per season by design |
| **Hanoi median** | 4 | 01-19, 03-10, 10-31, 12-20 | 4/12 | Dry-season; 3.82 obs/pixel |
| **HCMC median** | 3 | 02-12, 12-24, 12-29 | **2/12** | Dry-season; 2.66 obs/pixel |

**Milan is near-annual, not annual.** January, February and May are absent from all
30 dates, so the composite leans to the growing season. Describing it as "annual"
overstates its coverage.

**HCMC's three dates are effectively two independent looks.** 2018-12-24 and
2018-12-29 are **five days apart** — the same scene state, not two seasons. The
composite is one February look plus one late-December look, spanning 2 months of
12. It is thinner than "3 dates" suggests, and thinner than Hanoi's 4.

**AlphaEarth embeddings are annual for all three cities.** Both notebooks use
`GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` filtered to exactly one year —
`.filter(ee.Filter.date(start_date, start_date.advance(1, 'year')))` at
[01](../01_IMD_Prediction_Milan_blockCV_v2.ipynb) cell 6 and
[02](../02_Transferability_Vietnam_v2.ipynb) cell 7. Milan, Hanoi and HCMC receive
identical treatment with no seasonal gap.

**This asymmetry matters for the Vietnam comparison.** The embeddings zero-shot
compares **annual against annual**. The S2-median zero-shot compares Milan's
30-date near-annual composite against 2–4 dry-season Vietnamese looks. The two
zero-shot results are therefore **not equally handicapped**, and composite depth is
confounded with predictor type: an embeddings-beats-S2 result in Vietnam cannot be
attributed to the predictor without first ruling out depth.

## Open question — resolved: notebook 04 consumes **15** rasters, not 13

An earlier note in this project said "13 rasters". That was an error. Cell 11 of
`04_Validation_PhotoInterpreted.ipynb` builds `MAP_REGISTRY` as 15 rows —
12 `role='model'` + 3 `role='reference'` — and asserts every path exists, so a
short registry would fail loudly rather than run.

**12 predictions (`role='model'`)**

| # | City | `map_id` | Path |
|---|---|---|---|
| 1 | Milan | `emb_RF` | `outputs_v2/IMD_predicted_RF_spatialCV2_Milan.tif` |
| 2 | Milan | `S2_median` | `outputs_S2_median/IMD_predicted_RF_S2_Milan.tif` |
| 3 | Milan | `S2_percentile` | `outputs_S2_percentile_p10p25p50p75p90/IMD_predicted_RF_S2_Milan.tif` |
| 4 | Milan | `S2_stack` | `outputs_S2_stack/IMD_predicted_RF_S2_Milan.tif` |
| 5 | Hanoi | `emb_zeroshot` | `outputs_transfer_v2/IMD_Hanoi_10m_zeroshot.tif` |
| 6 | Hanoi | `S2_median_zeroshot` | `outputs_transfer_S2_median/IMD_Hanoi_10m_zeroshot_S2median.tif` |
| 7 | Hanoi | `emb_localrf` | `outputs_transfer_v2/IMD_Hanoi_10m_localrf.tif` |
| 8 | Hanoi | `S2_median_localrf` | `outputs_transfer_S2_median/IMD_Hanoi_10m_localrf_S2median.tif` |
| 9 | HCMC | `emb_zeroshot` | `outputs_transfer_v2/IMD_HCMC_10m_zeroshot.tif` |
| 10 | HCMC | `S2_median_zeroshot` | `outputs_transfer_S2_median/IMD_HCMC_10m_zeroshot_S2median.tif` |
| 11 | HCMC | `emb_localrf` | `outputs_transfer_v2/IMD_HCMC_10m_localrf.tif` |
| 12 | HCMC | `S2_median_localrf` | `outputs_transfer_S2_median/IMD_HCMC_10m_localrf_S2median.tif` |

**3 reference products (`role='reference'`)**

| # | City | `map_id` | Path |
|---|---|---|---|
| 13 | Milan | `CLMS` | `data/IMD_2018_CLMS_UTM32N.tif` |
| 14 | Hanoi | `GHSL` | `data/IMD_2018_Hanoi.tif` |
| 15 | HCMC | `GHSL` | `data/IMD_2018_HCMC.tif` |

**Explanation of the difference:** there is none to explain — 4 Milan + 8 Vietnam
+ 3 reference = 15 is correct, and all 15 files were confirmed present on disk on
2026-08-30. The "13" figure did not come from the code and matches no subset of
the registry (dropping the 3 reference rows gives 12; dropping only Milan's CLMS gives
14). It was simply a miscount and should not be repeated in the write-up.

The `role='reference'` rows score the **training targets themselves** (CLMS in
Milan, GHSL in Vietnam) against the independent photo-interpretation, on the same
terms as the models. They measure the quality of the labels the models were
fitted to.

**They do not bound achievable model performance.** A model can legitimately
score better than its own training target, by two mechanisms:

- **Noise smoothing.** Where the target carries random per-pixel error, a model
  cannot fit that noise; it learns the systematic part and averages the rest
  away, so it can agree with independent truth more closely than its own labels do.
- **Signal the labels lack.** Where the predictors carry information the target
  does not encode, a model can partially recover classes the labels never marked.

Vietnam is a live instance: GHSL scores RMSE ~40 (Hanoi) and ~37 (HCMC) with bias
≈ +20, and every locally-retrained model — plus the S2-median zero-shot map in
HCMC — beats it.

A separate, genuine limitation of the GHSL target: **GHS-BUILT-S measures built-up
surface and excludes roads by design**, so it systematically under-marks sealed
area that photo-interpretation counts. That is a property of the target, and a
reason its disagreement with interpretation is partly structural rather than
random — not a ceiling on what a model can achieve.
