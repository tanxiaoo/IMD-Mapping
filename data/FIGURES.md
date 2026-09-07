# Figure & table artefact inventory

Every figure and presentation-ready table in the repo, with what produces it and
whether it can be used as-is.

Last updated: 2026-09-01 · 84 notebook/deck artefacts + 4 report figures

**Every figure here was identified from the code that produces it** — the
`savefig` block, its titles, axis labels, legend entries and plotted data — not
by opening the image.

## Scope of the 2026-08-30 notebook-04 re-run

Notebook `04_Validation_PhotoInterpreted.ipynb` was re-executed at
**2026-08-30 01:37** to apply the `role='ceiling'` → `role='reference'` rename.

**That re-run wrote only `outputs_validation/`.** Notebook 04 reads existing
rasters and retrains nothing, so it cannot and did not touch the Milan
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

## Milan — same-source validation (vs CLMS)

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
| `fig06_inflation_heatmap.png` | Spatial-vs-random CV RMSE inflation, model × block | **RESULT** | every cell | NEEDS-EDIT — **not cited**, see below |
| `fig07_holdout_scatter.png` | Observed vs predicted on the holdout, RF and SVR panels | **RESULT** | RMSE/MAE/R²/Bias | KEEP |
| `figA_holdout_accuracy_GEE_RF.png` · `_GEE_SVR.png` | 3-panel accuracy: scatter by class, KDE density, abs-error boxplot | **RESULT** | RMSE/MAE/R²/Bias | STALE-REGENERATE — **source fixed 2026-09-01**, images not yet rebuilt, see below |
| `figB_model_cv_comparison.png` | Best-block CV RMSE per model, winner outlined | DIAGNOSTIC | CV RMSE + block | NEEDS-EDIT |
| `figC_perclass_GEE_RF.png` · `_GEE_SVR.png` | RMSE/MAE/Bias per IMD class | **RESULT** | every bar | KEEP |
| `figD_importance_RF.png` | RF impurity + permutation importance per band | DIAGNOSTIC | — | KEEP |
| `figE_raster_comparison_1.png` (not in `outputs_v2`) | Observed CLMS / predicted RF / difference rasters | MAP | **none** | NEEDS-EDIT |

**Dates** (each directory carries its own run): `outputs_v2` 2026-07-23 ·
`outputs_S2_stack` 2026-08-19 · `outputs_S2_percentile_p10p25p50p75p90`
2026-08-24 · `outputs_S2_median` 2026-08-27. `figE` in stack and percentile was
regenerated 2026-08-25.

**`figA_holdout_accuracy_*.png` — NEEDS-EDIT, not cited.** Its title reads
`(tuning block=<X>)`, and the value is wrong for every copy but one. In
notebooks 01/01b cell 22 `BEST_BLOCK_LABEL` is a **single global** holding the
block of whichever model won CV *overall*; cell 40 then loops over both
estimators and stamps that same label onto both figures. So the `GEE_RF` copies
carry another model's block:

| Run | `figA_GEE_RF` title says | FACTS.md has RF at | Label came from |
|---|---|---|---|
| `outputs_v2` | 500m | **1000m** | SVR |
| `outputs_S2_percentile_p10p25p50p75p90` | 500m | **1000m** | the excluded third estimator |

The percentile copy is the more serious case: its label is derived from the
estimator that is out of scope for this report, so the figure is downstream of a
model the report must not name. The plotted data are correct in all copies —
only the title is wrong. `fig07_holdout_scatter.png` (F4, §4.1) carries the same
holdout scatter and the same four metrics with a correct title.

**Source fixed 2026-09-01; the images on disk are still the old ones.** Cell 40
(nb 01) and cell 41 (nb 01b) now read `best_block_per_model[name.replace('GEE_',
'')]` — the estimator's own tuning result — instead of the global
`BEST_BLOCK_LABEL`, and the duplicating `Figure A · …` suptitle is reduced to the
estimator name plus its block. `BEST_BLOCK_LABEL` remains defined in cell 22 and
is still used for the overall-winner print and `model_metadata_*.json`; it no
longer reaches any figure. The notebooks were **not** re-executed, per CLAUDE.md,
so the PNGs still carry the old title until 01/01b next run deliberately. These
figures remain uncited, so nothing in the report depends on the rebuild.

**Largely duplicated by F4 in any case.** `figA`'s left panel plots the same
1014 points with the same RMSE/MAE/R²/Bias box as `fig07`'s corresponding panel,
differing only in point colouring; its right panel is per-class error, which is
already F5 (`figC_perclass_GEE_RF`). Only the middle KDE panel is new.

**`fig07_holdout_scatter.png` and `figC_perclass_GEE_RF.png` — suptitles removed
2026-09-01, percentile run only.** Both are cited (F4 and F6, §4.1) and both
carried a top-level suptitle that only repeated the report caption while exposing
internal tags: `Figure 7 · [S2] Spatial Holdout Test Set -- Observed vs Predicted
IMD (GEE raster)` and `Figure C · [S2] Per-Class Accuracy -- GEE_RF`. The
in-image `Figure 7` / `Figure C` also disagreed with the report's own numbering,
where they are Figures 4 and 6.

Re-running notebook 01b for a labelling change is forbidden by CLAUDE.md, and it
would overwrite every CSV `collect_metrics.py` builds `FACTS.md` from. So both
are redrawn by `code/redraw_notebook_figs.py` **at their existing paths** from
the CSVs the notebook already wrote — `holdout_residuals.csv` plus
`holdout_test_metrics.csv` for F4, `perclass_metrics_GEE_RF.csv` for F6 — the
same rule already used for F3 and F15. Panel geometry, colours, limits, marker
sizes and annotation boxes are copied verbatim from cells 39 and 45; only the
suptitle is dropped. Per-panel subplot titles are kept: they label the panels and
are not duplication. The residuals CSV carries the out-of-scope third
estimator's columns; only `pred_RF` and `pred_SVR` are read.

The plotted values are unchanged — `FACTS.md` was rebuilt after the redraw and is
byte-identical. Because these paths are gitignored notebook outputs, a future
deliberate re-run of 01b will revert them; re-run the script afterwards.

**Eight more cited figures — PNGs were STALE, rebuilt 2026-09-01.** The two
figures above were fixed at source in commit `9b5c792` ("Separate figure code
from figure titles"), which removed the numbered suptitles from notebooks 01,
01b, 02, 03 and 04. **The notebook source has been correct ever since.** What was
wrong was the images: they were never rebuilt after that commit, so eight cited
PNGs still displayed a title from the pre-fix code:

| File | Stale PNG displayed | Report figure |
|---|---|---|
| `outputs_v2/fig01_spatial_split.png` | `Figure 1 · Spatial Train/Test Split` | Figure 2 |
| `outputs_S2_percentile_.../figD_importance_RF.png` | `Figure D · Feature Importance …` | Figure 8 |
| `outputs_transfer_v2/fig01_transfer_comparison.png` | `Figure 1 · Same-source validation: … not accuracy` | Figure 9 |
| `outputs_transfer_S2_median/fig01_transfer_comparison.png` | same | Figure 10 |
| `outputs_transfer_v2/fig_obs_vs_pred_hanoi_hcmc.png` | `Observed vs Predicted IMD …` + `Hanoi & HCMC` | Figure 11 |
| `outputs_transfer_v2/fig02_per_class_mae.png` | `Figure 2 · Per-Class MAE …` | Figure 12 |
| `outputs_validation/fig02_forest_ci.png` | `Figure 2 · Map accuracy …` | Figure 13 |
| `outputs_validation/fig01_scatter_grid.png` | `Figure 1 · Reference vs predicted IMD …` | Figure 14 |

The LaTeX conversion is what exposed them: LaTeX prints its own figure number
directly beneath an image already showing a different one. This is the blind spot
CLAUDE.md names — `audit_numbers.py` checks caption-to-image agreement but cannot
read a number *inside* a PNG, so a figure captioned "Figure 14" while displaying
"Figure 1" passed every check. **A figure whose PNG predates a labelling fix is
invisible to every automated check in this repo; only rebuilding catches it.**

**The fix was to rebuild, not to post-process.** `code/redraw_cited_figs.py`
redraws F2, F8, F9, F10, F11 and F12 from the CSVs, point files and rasters the
notebooks already wrote, reproducing cells 12, 47, 13, 17 and 23 verbatim.
F13 and F14 came from re-executing notebook 04, which is safe because it reads
existing rasters, retrains nothing and makes no Earth Engine calls — its six CSVs
and `FACTS.md` were verified byte-identical afterwards. Notebooks 01 and 02 were
**not** re-executed: they re-tune models and export rasters to Earth Engine,
which CLAUDE.md forbids for a labelling change.

**What the rebuilt figures legitimately keep.** The rule is not "remove every
suptitle" — CLAUDE.md permits run-identifying parameters where the same filename
exists in several run directories and the plot cannot distinguish them. So these
survive, and should:

| Figure | Kept suptitle | Why |
|---|---|---|
| F2 | `Train: 2449 pts \| Test: 1014 pts \| Buffer: 250m` | run parameters |
| F8 | `RF · Sentinel-2 (tuning block=1000m)` | same filename in 4 run dirs |
| F9, F10 | `scored against GHSL (Milan baseline against CLMS)` | same filename in 2 run dirs; names the reference, not the finding |
| F11 | `AlphaEarth embedding (64 dims)` | distinguishes from the S2 median run |
| F12 | `spatial test set \| 1000m blocks, 250m buffer` | run parameters |
| F13, F14 | none | notebook 04 emits none |

None carries a figure number, a restatement of the caption, or a conclusion.

**`fig06_inflation_heatmap.png` — NEEDS-EDIT, resolved for the report by F3.**
Its plotted values are correct, but it renders one row per *tuned* model, so it
displays the name of the third estimator that is out of scope for this report.
It is therefore not cited. `report/figs/fig_cv_inflation.png` (F3, §3.2) is
redrawn from `outputs_v2/inflation_analysis.csv` filtered to RF and SVR, per
CLAUDE.md's rule that a labelling change is made from the CSV the notebook
already wrote rather than by re-executing the notebook. The values are the
notebook's; only the row filter and the labelling differ.

**`figB_model_cv_comparison.png` — NEEDS-EDIT.** It shows the CV winner only. In
`outputs_v2` that winner is SVR, but RF is the model carried forward to Vietnam
and validation, and RF wins the holdout. Used alone the figure implies SVR was
selected. See the estimator-selection section of `EXPERIMENT_MAP.md`.

**`figE_raster_comparison_1.png` — NEEDS-EDIT, resolved for the percentile run
by F15.** Its suptitle is commented out in the producing code, so the three
copies carry no label identifying which composite produced them and are
indistinguishable outside their directory path.

The percentile copy is the one the report needs, and it is rebuilt with a
suptitle as `report/figs/fig_milan_raster_comparison.png` (F15, §4.1) rather
than edited in place. The rebuild reads the same two GeoTIFFs the notebook reads
and copies its panel geometry, colormap, limits and decimation verbatim, so the
pixels are the notebook's; only the label is added. The `median` and `stack`
copies remain unlabelled and NEEDS-EDIT — neither is cited.

## Vietnam transfer — same-source validation (vs GHSL)

`outputs_transfer_v2` ← notebook 02 · `outputs_transfer_S2_median` ← notebook 03.
Identical figure code in both; only the raster suffix and one suptitle differ.

| File | Shows | Kind | Numbers in title | Status |
|---|---|---|---|---|
| `fig00_spatial_split.png` | Train/test/buffer points over the 1 km grid, both cities | DIAGNOSTIC | train/test/removed n | KEEP |
| `fig01_transfer_comparison.png` | 2×2 bars: Milan baseline vs A vs B, per city, all four metrics | **RESULT** | every bar | KEEP — **both copies cited**: F7 (`outputs_transfer_v2`, embeddings) and F16 (`outputs_transfer_S2_median`, S2 median) |
| `fig02_per_class_mae.png` | MAE per IMD class, transfer vs local retrain | **RESULT** | — | KEEP |
| `fig_scatter_Hanoi.png` · `fig_scatter_HCMC.png` | Observed GHSL vs predicted, both scenarios | **RESULT** | RMSE/MAE/R²/Bias | KEEP |
| `fig_obs_vs_pred_hanoi_hcmc.png` | GHSL / Milan transfer / local retrain rasters, 2×3 | MAP | per-panel RMSE/R²/Bias | KEEP |

**Dates:** `outputs_transfer_v2` 2026-08-28 · `outputs_transfer_S2_median`
2026-08-29. Both postdate their input rasters; neither is stale.

**`fig01_transfer_comparison.png` — FIXED 2026-09-01.** The figure had four
panels labelled only `RMSE`, `MAE`, `R2`, `Bias` and no suptitle, so nothing
said what they were scored against. The Bias panel in particular invited the
reading that a model near zero is accurate, when every bar is measured against
GHSL — which itself under-marks sealed area by ~20 pp against
photo-interpretation. Notebooks 02 and 03 now add a suptitle naming the
reference: *"Same-source validation: scored against GHSL (Milan baseline
against CLMS) · Agreement with the training target, not accuracy."*

The plotted values were always correct; only the labelling was incomplete.

**Both copies are cited in §5.1, as F7 and F16.** The section tabulates both
predictor sets, so showing only the embeddings run would plot half of what the
table reports. The two figures are directly comparable — the figure code is
identical in notebooks 02 and 03, and only the raster suffix and one suptitle
differ — which is exactly why they must be labelled apart in the report: on the
page they are two similar 2×2 bar panels whose axes do not say which predictor
set produced them. **Each caption names its predictor set and its reference**,
and every citation carries its directory, since the filename alone does not
identify the run.

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
carries both the collapse under independent validation and the result that
CLMS and GHSL score no better than the models trained on them.

## Report figures — built for the report, not by a notebook

`report/figs/` ← `code/make_report_figs.py`. These four carry findings no
notebook figure covers; see `data/FIGURE_GAPS.md` for why each exists.

| File | Shows | Kind | §  | Status |
|---|---|---|---|---|
| `fig_composite_depth.png` | Usable S2 acquisitions per city on a 2018 calendar, with counts and obs/pixel | **RESULT** | 2.3 | KEEP |
| `fig_cv_inflation.png` | Spatial-vs-random CV RMSE, model × block — the notebook's `fig06` redrawn from `inflation_analysis.csv` with the out-of-scope estimator's row filtered out | DIAGNOSTIC | 3.2 | KEEP — **cited** |
| `fig_milan_predictor_ranking.png` | The four Milan predictor sets on holdout RMSE, MAE and R², ranked, GEE RF | **RESULT** | 4.1 | KEEP — **cited** |
| `fig_samesource_vs_independent.png` | The four Milan predictor sets under both validations, shared 5–30 pp axis | **RESULT** | 7.1 | KEEP |
| `fig_hcmc_prediction_histogram.png` | Predicted-IMD distributions for the four HCMC maps plus the reference, with a range/IQR/mean strip | **RESULT** | 7.2 | KEEP |
| `fig_bias_recovery.png` | GHSL's bias against each local retrain's, per city, with the closed gap in pp | **RESULT** | 7.3 | KEEP |
| `fig_milan_raster_comparison.png` | Observed CLMS / predicted / difference rasters, Milan, percentile run — `figE` relabelled with a run-identifying suptitle | MAP | 4.1 | KEEP — **cited** |

**Figure numbers are no longer rendered into any image (2026-09-01).** They used
to be, and the suptitle had to track the report's numbering — outline F-numbers
are planning ids in outline order, while the report numbers figures by page
order, so the two differ and a suptitle reading "Figure 12" beside a caption
reading "Figure 15" was a defect a reader sees immediately. That made every
renumbering of the report a matching edit to `code/make_report_figs.py`, policed
by nothing: `code/audit_numbers.py` checks caption-to-image agreement but cannot
read a number rendered inside a PNG. Removing the numbers removes the hazard —
renumber the report freely; no figure needs rebuilding.

**Every plotted value is read from `data/FACTS.md`.** `facts_value()` raises on
an absent row, an ambiguous match, or a `MISSING` cell rather than substituting
a literal, so a figure cannot drift from the numbers it claims to show. Each
build prints its plotted values for checking against the fact base.

**F15 is the one exception**: it is a map, not a chart, and reads its two
GeoTIFFs directly. It plots no metric and quotes no number, so there is nothing
for it to drift from; its build prints a difference summary for checking, which
is deliberately raster-wide and is **not** quoted in the report — the report's
numbers are the 1014-point holdout in Table A.

**These figures state readings, never conclusions.** No conclusion sentences, no
interpretive annotations, no callouts — only axis labels, panel titles, and
numeric values that are measurements. Every claim ("saturated, not shifted",
"recovers 38–67 %", the ≥ 17-date percentile floor) belongs to the report
caption. This is a deliberate departure from `make_presentation.py`, whose
slide titles are written as conclusions.

**No figure carries its own title or number (2026-09-01).** Figure code
generates the visualisation; the report generates the title and caption
(CLAUDE.md). Applied across `make_report_figs.py` and all five notebooks:
describing suptitles removed, `Figure N ·` / `Figure A–E ·` prefixes and `[S2]`
run tags dropped everywhere they were rendered. What stays is what the plot
cannot say for itself — per-panel titles, axis labels, legends, measured
annotations, and run parameters (buffer, folds, block size, composite depth).
Three suptitles survive as run identification rather than caption: F15 and
notebook 02/03 cell 23 name the predictor set behind otherwise identical raster
panels, and 02/03 cell 13 keeps "scored against GHSL" so the Bias panel cannot
be read as accuracy. Two conclusions were also removed: `figB`'s axes title
named the CV winner, and `fig_samesource_vs_independent`'s stated the spread
that Section 7.1 argues in prose.

This retires the numbering hazard described below rather than managing it.

**House style** follows the notebooks, not the deck: notebook `rcParams`
verbatim, dpi 150, `Figure N · Description` suptitle at 13 pt bold, axes titles
11 pt bold, default matplotlib font and tick colours. The only thing carried
over from the deck is the per-predictor palette.

Regenerate with `python code/make_report_figs.py` (all four) or
`python code/make_report_figs.py F12` (one). Unlike every other figure in this
repo, these **are** version-controlled — see the negation in `.gitignore`.

## Presentation-ready tables

| File | Content | Status |
|---|---|---|
| `outputs_validation/table1_headline_ci.csv` | Per (city, map): role, N, RMSE, RefNoise, RMSE_corr, MAE, Bias, r, R² + pre-formatted CI strings | KEEP — publication-ready |
| `outputs_validation/table2_wilcoxon_pairs.csv` | Pairwise Wilcoxon per city with `q_bh` and `sig` | KEEP — carries the Milan two-tier result |
| `outputs_validation/table3_rule_sensitivity.csv` | MAE/RMSE under strict/B/C with ranks and `rank_changed` | KEEP — carries the rule-C rank swap |
| `outputs_validation/table4_perlevel_metrics.csv` · `table4b_perclass7_metrics.csv` | Per-level and per-class metrics | KEEP — long; subset before use |
| `outputs_*/holdout_test_metrics.csv` (×4) | `Model,RMSE,MAE,R2,Bias` for GEE_RF and GEE_SVR | KEEP — the same-source validation headline table |
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
  features — now verified and correct.** Notebooks 01 and 01b were changed on
  2026-08-31 to persist `feature_importance_RF.csv` alongside
  `figD_importance_RF.png`, and 01b was re-run on the percentile composite. The
  CSV ranks by permutation importance: **B4_p25 (0.181), B4_p10 (0.056),
  B8_p90 (0.040), B4_p50 (0.023), B8_p75 (0.021)**. The deck's four named bands
  are ranks 1, 2, 3 and 5 — the claim holds, with `B4_p50` sitting between them
  at rank 4. The claim is no longer unverifiable: cite the CSV.

Also hardcoded and worth watching: the holdout count `1 014` appears literally in
three places (`fig_holdout` footer, `fig_paired` title, slide 11) while slide 17
computes it — those would disagree if the split ever changed.

## Version control

All `outputs_*`, `*.png` and `figs_ppt/` are gitignored, so no figure **at its
original path** is under version control. Regeneration is safe but leaves no
history. The fact base (`FACTS.md`, `EXPERIMENT_MAP.md`, `FIGURES.md`,
`FIGURE_GAPS.md`) is exempted from the `data/` ignore rule and **is** tracked.

The exception is `report/figs/`, described below, which **is** tracked in full.

## `report/figs/` holds copies

`report/` is a self-contained Overleaf project: it must compile with no file
outside it. So every figure the report cites lives under `report/figs/`, and
two kinds sit there:

| Path | Origin | Refreshed by |
|---|---|---|
| `report/figs/fig_*.png` | built directly there from `data/FACTS.md` | `python code/make_report_figs.py` |
| `report/figs/outputs_*/**.png` | **copies** of the notebook figures | `python code/sync_figs.py` |

**The copies are copies, not the originals.** The notebooks still write to
`outputs_v2/`, `outputs_validation/`, `outputs_transfer_*/` and the rest exactly
as before; nothing in the pipeline was re-pathed. `sync_figs.py` reads the
`\includegraphics` paths out of `report/report.tex` and copies each cited file
into `report/figs/`, **mirroring the run directory** — so
`outputs_v2/fig01_spatial_split.png` becomes
`report/figs/outputs_v2/fig01_spatial_split.png`.

Mirroring rather than flattening is required, not tidiness:
`fig01_transfer_comparison.png` exists in both `outputs_transfer_v2/` and
`outputs_transfer_S2_median/` and the report cites **both**. A flat copy would
silently drop one. Mirroring also keeps every `\includegraphics` path in the
report unchanged, so `\graphicspath{{figs/}}` alone resolves them all.

**After regenerating any cited figure, re-run `python code/sync_figs.py`** or
the report will keep compiling against the previous copy. The script is
idempotent and compares content rather than mtime, so running it when nothing
changed copies nothing; it exits 1 and names the file if a cited figure cannot
be found.
