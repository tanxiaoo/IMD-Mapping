# Figure & table artefact inventory

Every figure and presentation-ready table in the repo, with what produces it and
whether it can be used as-is.

Last updated: 2026-08-30 · 84 image artefacts

**Every figure here was identified from the code that produces it** — the
`savefig` block, its titles, axis labels, legend entries and plotted data — not
by opening the image.

## Scope of the 2026-08-30 notebook-04 re-run

Notebook `04_Validation_PhotoInterpreted.ipynb` was re-executed at
**2026-08-30 01:37** to apply the `role='ceiling'` → `role='reference'` rename.

**That re-run wrote only `outputs_validation/`.** Notebook 04 reads existing
rasters and retrains nothing, so it cannot and did not touch the Milan Track A
directories (`outputs_v2`, `outputs_S2_*`) or the Vietnam transfer directories
(`outputs_transfer_*`). Those figures are **unaffected by the rename** — their
producing notebooks (01, 01b, 02, 03) never reference `role` at all, since the
map registry is a notebook-04 construct.

So a Milan or Vietnam figure being older than 2026-08-30 is **not** a staleness
finding. It only matters whether it is older than its own inputs.

## Status vocabulary

| Status | Meaning |
|---|---|
| **KEEP** | Current and consistent with `data/FACTS.md`; usable as-is |
| **STALE-REGENERATE** | Inputs changed after the figure was written; re-run its producer |
| **NEEDS-EDIT** | Correct but incomplete or mislabelled for how it is being used |

## Does any figure display the word "ceiling"?

**No.** Checked across every figure-producing cell in all five notebooks and
`make_presentation.py`. The role value reaches rendered text only as a
`(target)` suffix (notebook 04 cells 29, 31, 32) and as diamond markers
(cell 30). `make_presentation.py` contains no role value at all. The word
survives only in notebook 04's markdown prose, where cell 33 states "This is not
a ceiling on achievable accuracy" — deliberate.

---

## Milan Track A — same-source spatial holdout (CLMS)

Four directories, one filename set. `outputs_v2` ← notebook 01;
`outputs_S2_median` / `_stack` / `_percentile_p10p25p50p75p90` ← notebook 01b
re-run per `COMPOSITE_METHOD`. `outputs_v2` has no `figE` and no
`holdout_residuals.csv`.

| File | Shows | Kind | Numbers in title | Status |
|---|---|---|---|---|
| `fig01_spatial_split.png` | Train/test/buffer-removed points over the 1 km block grid + class counts | DIAGNOSTIC | train/test/removed n | KEEP |
| `fig_repeated_cv_results.png` | RMSE & R² vs CV strategy, one line per model | DIAGNOSTIC | per-point values | KEEP |
| `fig02_cv_folds.png` | Spatial fold assignment at each block size | DIAGNOSTIC | — | KEEP |
| `fig03_degradation.png` | RMSE/R² degradation with block size, vline at best block | DIAGNOSTIC | per-point values | KEEP |
| `fig04_rmse_boxplots.png` | Per-fold RMSE boxplots per model across block sizes | DIAGNOSTIC | tuning block | KEEP |
| `fig05_all_metrics.png` | 2×2 grouped bars, all four metrics × models × blocks | DIAGNOSTIC | — | KEEP |
| `fig06_inflation_heatmap.png` | Spatial-vs-random CV RMSE inflation, model × block | **RESULT** | every cell | KEEP |
| `fig07_holdout_scatter.png` | Observed vs predicted on the holdout, RF and SVR panels | **RESULT** | RMSE/MAE/R²/Bias | KEEP |
| `figA_holdout_accuracy_GEE_RF.png` · `_GEE_SVR.png` | 3-panel accuracy: scatter by class, KDE density, abs-error boxplot | **RESULT** | RMSE/MAE/R²/Bias | KEEP |
| `figB_model_cv_comparison.png` | Best-block CV RMSE per model, winner outlined | DIAGNOSTIC | CV RMSE + block | NEEDS-EDIT |
| `figC_perclass_GEE_RF.png` · `_GEE_SVR.png` | RMSE/MAE/Bias per IMD class | **RESULT** | every bar | KEEP |
| `figD_importance_RF.png` | RF impurity + permutation importance per band | DIAGNOSTIC | — | KEEP |
| `figE_raster_comparison_1.png` (not in `outputs_v2`) | Observed CLMS / predicted RF / difference rasters | MAP | **none** | NEEDS-EDIT |

**Dates** (each directory carries its own run): `outputs_v2` 2026-07-23 ·
`outputs_S2_stack` 2026-08-19 · `outputs_S2_percentile_p10p25p50p75p90`
2026-08-24 · `outputs_S2_median` 2026-08-27. `figE` in stack and percentile was
regenerated 2026-08-25.

**`figB_model_cv_comparison.png` — NEEDS-EDIT.** It shows the CV winner only. In
`outputs_v2` that winner is SVR, but RF is the model carried forward to Vietnam
and validation, and RF wins the holdout. Used alone the figure implies SVR was
selected. See the estimator-selection section of `EXPERIMENT_MAP.md`.

**`figE_raster_comparison_1.png` — NEEDS-EDIT.** Its suptitle is commented out in
the producing code, so the three copies carry no label identifying which
composite produced them and are indistinguishable outside their directory path.

## Vietnam transfer — same-source spatial holdout (GHSL)

`outputs_transfer_v2` ← notebook 02 · `outputs_transfer_S2_median` ← notebook 03.
Identical figure code in both; only the raster suffix and one suptitle differ.

| File | Shows | Kind | Numbers in title | Status |
|---|---|---|---|---|
| `fig00_spatial_split.png` | Train/test/buffer points over the 1 km grid, both cities | DIAGNOSTIC | train/test/removed n | KEEP |
| `fig01_transfer_comparison.png` | 2×2 bars: Milan baseline vs A vs B, per city, all four metrics | **RESULT** | every bar | NEEDS-EDIT |
| `fig02_per_class_mae.png` | MAE per IMD class, transfer vs local retrain | **RESULT** | — | KEEP |
| `fig_scatter_Hanoi.png` · `fig_scatter_HCMC.png` | Observed GHSL vs predicted, both scenarios | **RESULT** | RMSE/MAE/R²/Bias | KEEP |
| `fig_obs_vs_pred_hanoi_hcmc.png` | GHSL / Milan transfer / local retrain rasters, 2×3 | MAP | per-panel RMSE/R²/Bias | KEEP |

**Dates:** `outputs_transfer_v2` 2026-08-28 · `outputs_transfer_S2_median`
2026-08-29. Both postdate their input rasters; neither is stale.

**`fig01_transfer_comparison.png` — NEEDS-EDIT.** Its bias bars are measured
against GHSL, so they show the models diverging from the target. Against
photo-interpretation the sign reverses and the local retrains recover 7.6–13.1 pp
of GHSL's deficit. The figure is correct for Track A but must not be captioned as
if it described accuracy.

## Independent validation — photo-interpreted plots

`outputs_validation` ← notebook 04. **Four figures, all written by the
2026-08-30 01:37 re-run.** All test `role == 'reference'` correctly and render
the `(target)` suffix and diamond markers.

| File | Shows | Kind | Numbers in title | Status |
|---|---|---|---|---|
| `fig01_scatter_grid.png` | Reference vs predicted, 3 cities × every registered map, strict rule | **RESULT** | per-panel RMSE, Bias | KEEP |
| `fig02_forest_ci.png` | **RMSE and MAE with 95% bootstrap CI for all 15 maps**; diamond = training target, `\|` = noise-corrected RMSE | **RESULT (headline)** | — | KEEP |
| `fig03_error_by_level.png` | Mean signed error vs reference level, binomial ±1 SE envelope | **RESULT** | — | KEEP |
| `fig04_calibration.png` | Mean predicted vs reference level with 95% CI, 1:1 line | **RESULT** | — | KEEP |

`fig02_forest_ci.png` is the single most load-bearing figure in the repo: it
carries both the Track B collapse and the result that CLMS and GHSL score no
better than the models trained on them.

## Presentation-ready tables

| File | Content | Status |
|---|---|---|
| `outputs_validation/table1_headline_ci.csv` | Per (city, map): role, N, RMSE, RefNoise, RMSE_corr, MAE, Bias, r, R² + pre-formatted CI strings | KEEP — publication-ready |
| `outputs_validation/table2_wilcoxon_pairs.csv` | Pairwise Wilcoxon per city with `q_bh` and `sig` | KEEP — carries the Milan two-tier result |
| `outputs_validation/table3_rule_sensitivity.csv` | MAE/RMSE under strict/B/C with ranks and `rank_changed` | KEEP — carries the rule-C rank swap |
| `outputs_validation/table4_perlevel_metrics.csv` · `table4b_perclass7_metrics.csv` | Per-level and per-class metrics | KEEP — long; subset before use |
| `outputs_*/holdout_test_metrics.csv` (×4) | `Model,RMSE,MAE,R2,Bias` for GEE_RF and GEE_SVR | KEEP — the Track A headline table |
| `outputs_*/spatial_cv_summary.csv` (×4) | Model × CV method, all metrics mean+std | KEEP — wide; prune columns |
| `outputs_*/inflation_analysis.csv` (×4) | Tabular twin of `fig06` | KEEP |
| `outputs_*/perclass_metrics_GEE_{RF,SVR}.csv` (×4) | Tabular twin of `figC` | KEEP |
| `outputs_transfer_*/transferability_comparison.csv` | 5 rows: baseline + A/B × city | KEEP |
| `outputs_transfer_*/per_class_metrics.csv` | Per class × scenario × city | KEEP — appendix |
| `outputs_*/hyperparameter_tuning.csv` | Tuning results; `Best_params` is a raw dict string | NEEDS-EDIT — appendix only |
| `outputs_validation/validation_per_plot_long.csv` · `outputs_*/holdout_residuals.csv` | Raw per-point data | Not a table — inputs to `code/collect_metrics.py` |

## The presentation deck

`make_presentation.py` → `IMD_S2_composite_comparison.pptx`, 17 slides,
13.333×7.5 in. Milan S2-composite comparison only — it does **not** read
`outputs_transfer_*`, `outputs_validation`, or anything under `data/`.

**Status: STALE-REGENERATE.** The pptx and all nine `figs_ppt/*.png` are dated
2026-08-27 15:51, older than the script that builds them (21:37) and older than
the three composite run directories its argument rests on (2026-08-28 00:53).
Re-running refreshes every CSV-derived number automatically.

House style, for any new figure that must match the deck:

- Palette `INK #1a1a1a`, `MUTED #6b6b6b`, `ACCENT #0B6E4F`, `RULE #d4d4d4`;
  per-run `median #b0b7bd`, `stack #7d93a3`, `percentile` = ACCENT,
  `embedding #C2724A`.
- Figures: DejaVu Sans, figsize 11.5–13.0 × 3.5–4.6 in, `dpi=200`,
  `bbox_inches='tight'`, no top/right spines, grid `#ececec`.
- Slides: Calibri; kicker 10.5 bold accent → title 25 bold stated as a
  **conclusion, not a topic** → one 13 pt grey supporting sentence → evidence →
  grey footnote answering the obvious objection.
- Content column left `0.72"`, width `11.9"`.

### Hardcoded claims in the deck

Most numbers are computed live from the CSVs and refresh on rebuild. Two are
prose assertions the script never verifies:

- **Slide 6, "Random-CV and spatial-CV RMSE agree to within ~1%"** — checked and
  **correct**: maximum inflation in `inflation_analysis.csv` is exactly 1.0 %.
- **Slide 13, naming `B4_p25`/`B4_p10` and `B8_p90`/`B8_p75` as the top
  features — has no CSV backing.** Permutation importance is computed inside
  notebook 01b and rendered straight to `figD_importance_RF.png`; no importance
  table is written to disk. The claim cannot be verified without re-running the
  notebook, and a re-run could invalidate it while the deck still renders. Either
  persist an importance CSV or soften the slide text.

Also hardcoded and worth watching: the holdout count `1 014` appears literally in
three places (`fig_holdout` footer, `fig_paired` title, slide 11) while slide 17
computes it — those would disagree if the split ever changed.

## Version control

All `outputs_*`, `*.png` and `figs_ppt/` are gitignored, so no figure is under
version control. Regeneration is safe but leaves no history. The fact base
(`FACTS.md`, `EXPERIMENT_MAP.md`, `FIGURES.md`, `FIGURE_GAPS.md`) is exempted
from the `data/` ignore rule and **is** tracked.
