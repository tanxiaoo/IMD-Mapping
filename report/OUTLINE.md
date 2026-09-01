# Report outline

Impervious surface density from Sentinel-2 composites and AlphaEarth embeddings:
Milan, Hanoi, Ho Chi Minh City, 2018.

**Target:** 18–22 pages, 13 figures.
**Audience:** the professor and colleagues who have read `reference/` — the
AlphaEarth report by Matej Zgela. Anything that report already covers is
compressed to a short account with a citation, not re-derived.

**Structural decisions taken at the interview stage:**

- Sections 4 and 6 carry equal billing. The report is built around the contrast
  between them; §7 does the reconciling work.
- Vietnam argues **transfer fails, retraining is required**. Level-matching is
  the supporting mechanism, not the headline.
- Reference-product quality is folded into the §6 forest plot as a paragraph,
  not promoted to its own section. Its quantitative form — bias recovery — moves
  to §7 as evidence that retraining works.
- Data and Methods stay short but self-contained: a reader should not need the
  Zgela report open to follow them.
- **SVR appears in §4 only.** Vietnam is RF throughout. Stated once in §3.2.

Sources: `data/FACTS.md` (all metrics), `data/EXPERIMENT_MAP.md` (provenance),
`data/FIGURES.md` (inventory and status), `data/FIGURE_GAPS.md` (what must be
built).

---

## 1. Introduction — 1.5 pp

**Claim:** Replacing AlphaEarth embeddings with explicit Sentinel-2 composites
improves impervious-density mapping in Milan, but the improvement is measured
against CLMS; independent validation is needed to say whether it is accuracy.

Covers the LCZ-UHI-GEO context, the objective, and what changed relative to the
AlphaEarth study: the predictor set (three S2 composites added), the transfer
experiment (two Vietnamese cities), and a second validation track against
photo-interpreted plots.

**Attribution — an explicit paragraph, not a footnote.** The AlphaEarth method
and the shared Milan sample set (`outputs_sampling`) are Žgela's work and are
used here as supplied. The embeddings pipeline was independently re-run in this
project and reproduces his published holdout figures **exactly, for both
estimators**: RF 14.12 / 10.68 / 0.837 / +0.62 and SVR 14.76 / 11.40 / 0.822 /
+0.27 (Žgela p. 5). Record this as *verification that the shared baseline is
correctly reconstructed*, not as a new result.

Figures: none.
FACTS.md: Table A rows `Milan | AlphaEarth embeddings | GEE_RF` and `| GEE_SVR`.
Cite: Žgela p. 5.

---

## 2. Data — 4 pp

### 2.1 Targets: CLMS and GHS-BUILT-S — 1 pp

**Claim:** The two training targets measure different things, and the difference
is not noise: CLMS measures sealed surface, GHS-BUILT-S measures built-up surface
and **excludes roads by design**.

Sets up §6 and §7, where GHSL's ~+20 pp deficit against photo-interpretation is
shown to be partly definitional. State the exclusion here so the later result is
not a surprise.

Cite Žgela for the limitation rather than asserting it independently — he states
it twice (pp. 8, 10): GHS-BUILT-S "doesn't include all impervious surfaces such
as roads", accounting "only for built-up surfaces, namely buildings and a limited
set of other roofed infrastructure", and he calls this "an inherent limitation of
the chosen reference dataset". He also records that no other suitable 2018
reference existed for Vietnam, which is why it was used regardless — worth
repeating so the choice does not read as careless.

Figures: none.
FACTS.md: none yet — forward-reference to Table B reference rows.
Cite: Žgela pp. 8 and 10.

### 2.2 AlphaEarth embeddings — 0.5 pp

**Claim:** 64-dimensional annual embeddings, identical treatment in all three
cities.

Short account: `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`, filtered to one year,
`A00`–`A63`. Cite Žgela for the method and rationale; do not re-derive. The point
worth making here is **annual coverage for all three cities**, because §5 and §7
need it: the embeddings zero-shot compares annual against annual while the S2
zero-shot does not.

One sentence worth carrying from Žgela (pp. 3–4): 60 of 64 bands differ
significantly across IMD classes by Kruskal–Wallis, and a feature-selection
experiment found all 64 outperform any reduced subset — so the embeddings are
used whole here, not pruned. That forecloses an obvious reader question without
re-running the test.

Figures: none.
EXPERIMENT_MAP.md: composite-date-windows section.
Cite: Žgela pp. 3–5, Fig. 3.

### 2.3 Sentinel-2: search, screening, composites — 1.5 pp

**Claim:** After cloud screening, Milan yields 30 usable dates but Hanoi only 4
and HCMC only 3 — of which two are five days apart — so median was the **only**
composite computable in Vietnam.

This is where the Vietnam composite constraint lives, as a data fact, not a
modelling choice. Cover: scene search, the three screening criteria, surviving
dates per city, the 10 bands, and the three composite methods (median 10 bands,
stack 40 bands / 4 dates, percentile 50 bands / 5 percentiles). State that
percentiles need ≥17 dates and that notebook 00b's most permissive setting still
falls short — no relaxation recovers them.

Also state that Milan is **near-annual, not annual**: January, February and May
are absent from all 30 dates.

Figures: **F1** `report/figs/fig_composite_depth.png` — **BUILT**.
2018 calendar, usable dates per city, HCMC's two December dates marked as one
effective look.
FACTS.md: none. EXPERIMENT_MAP.md: composite-date-windows table.

### 2.4 Photo-interpreted plots — 1 pp

**Claim:** 450 plots per city, each a 10 m unit area equal to one pixel,
subdivided into nine interpreted sub-cells; plot IMD is the percentage of
sub-cells that are impervious.

Protocol and attribution: produced by Keerthana Kirubakaran in Google Earth Pro
on 2018 imagery, labelled with EarthLabel. State the three rules (strict primary;
B adds permeable pavement, C adds unpaved dirt road) and that **paved roads are
impervious under all three** — only dirt roads move, and only under C. Note that
code 11 does not occur in Vietnam, so B is identical to strict there.

Figures: none.
FACTS.md: rule-code counts table (Milan 23/112 cells, Hanoi 0/63, HCMC 0/34).

---

## 3. Methods — 4 pp

### 3.1 Sampling, spatial blocking, buffering — 1 pp

**Claim:** Train/test separation is spatial, not random: 1 km blocks with a 250 m
buffer, giving 2449 training and 1014 held-out points in Milan.

Short self-contained account, citing Žgela for the design's provenance and
rationale. State that the Milan point set is his and is used unchanged, and that
notebook 01b **imports** the split from the embeddings run rather than
recomputing it — which is what makes the four Milan predictor sets directly
comparable.

Concrete facts available (Žgela pp. 2, 4): 7 IMD groups (0 %, 1–20, 21–40,
41–60, 61–80, 81–99, 100 %), 500 points each = 3 500; 1 km blocks assigned whole
to train or test; 250 m buffer; **2 449 train / 1 014 test**. Report the ANN
check as his validation of the design — 1.02 for class 0 down to 0.75 for class
6, with the class-6 clustering acknowledged as a limitation rather than
concealed.

Figures: **F2** `fig01_spatial_split.png` (`outputs_v2`) — **EXISTS/KEEP**.
FACTS.md: provenance-of-n paragraph (1014, cross-checked two ways).
Cite: Žgela pp. 2 and 4, Figs. 1–2.

### 3.2 RF and SVR, tuning, spatial CV — 1 pp

**Claim:** Both estimators are tuned by randomised search under spatial block CV;
RF is carried forward everywhere outside §4.

**The single statement about model scope goes here:** SVR is evaluated in Milan
only. Vietnam is RF throughout, because notebook 02's transfer design requires an
RF and the comparison across cities must hold the estimator fixed. Notebook 04
likewise validates the RF raster from every run, so the validation comparison
isolates the predictor set rather than confounding predictor with estimator.

Figures: **F3** `fig06_inflation_heatmap.png` — **EXISTS/KEEP**. Shows that
spatial blocking has removed what leakage there was: maximum inflation 1.0 %.
FACTS.md: none directly.

### 3.3 Accuracy metrics — 1 pp

**Claim:** Four metrics, with bias defined as **observed − predicted**, so
positive bias means the map under-predicts.

Give the formulas for RMSE, MAE, R² and bias. State the sign convention
explicitly and note it is identical across all five notebooks — this matters
because §5 reports negative Vietnam biases (models over-predict against GHSL)
while §6 reports positive ones (GHSL under-predicts against interpretation), and
the two must not be read across tracks.

Also define `RMSE_corr`: the binomial reference-noise correction, and why it is
an **upper bound** on map error rather than a point estimate.

Figures: none.
FACTS.md: header bias-convention paragraph; `RMSE_corr` note.

### 3.4 The two-track validation design — 1 pp

**Claim:** same-source validation measures agreement with the training target; independent validation measures
accuracy against an independent reference. Both are needed because the first
cannot distinguish a good map from one that merely resembles its labels.

This subsection is the report's methodological hinge — it is what makes §6
interpretable rather than a second results section. State that the two tracks are
never merged and their numbers are never compared directly.

Figures: none.
FACTS.md: the two-table structure and its "not comparable" warning.

---

## 4. Milan results — same-source validation — 2.5 pp

**Claim:** All three Sentinel-2 composites beat the AlphaEarth embeddings against
CLMS, percentile best at RMSE 9.46 against the embeddings' 14.12 — a 33 %
reduction.

⚠ **same-source validation numbers only.** Every figure in this section is scored against CLMS
on the 1 014-point spatial holdout. Nothing measured against the photo-interpreted
plots belongs here — §3.4 states the two tracks are never merged, and that rule
binds this section. The paired per-plot testing of these same four predictor sets
uses independent validation data and lives in §6.2.

### 4.1 Four predictor sets ranked — 1.5 pp

Percentile 9.462, stack 10.864, median 11.285, embeddings 14.123 (all `GEE_RF`).
The ranking is identical on RMSE, MAE and R², so it is not a metric artefact.

Figures: **F4** `fig07_holdout_scatter.png` (percentile) — **EXISTS/KEEP**;
**F5** `figC_perclass_GEE_RF.png` (percentile) — **EXISTS/KEEP**, per-class
behaviour.
FACTS.md: Table A, all eight Milan rows.

### 4.2 The CV-versus-holdout reversal — 0.5 pp

**Claim:** SVR wins cross-validation and loses the holdout; RF is carried
forward. **This reproduces Žgela's result rather than adding to it** (p. 5) — he
reports SVR best on CV at 11.5 % with RF ~1.6 % worse, then RF winning every
holdout metric, and selects RF for that reason.

SVR CV RMSE 11.71 at its best block against RF's 13.16, then SVR holdout 14.756
against RF 14.123, losing on MAE and R² simultaneously. State the confound
honestly: holdout rows are scored on GEE-built rasters (`smileRandomForest`,
`libsvm`) while the CV numbers are sklearn, and the parameter translation is
lossy in both directions — so the reversal may be overfitting to CV or may be
translation fidelity. Note that `outputs_v2` metadata records
`best_model_name='SVR'` for this reason while RF is the model used downstream.

⚠ **Do not claim SVR cannot be rastered in GEE.** Žgela's stated reason for
dropping a third estimator is that it is unsupported in GEE's Python API; SVR
itself *is* supported (`ee.Classifier.libsvm`, `svmType='EPSILON_SVR'`) and is
used here — `outputs_v2/IMD_predicted_SVR_spatialCV2_Milan.tif` exists. The
operative reason RF is carried forward is that notebook 02's transfer design
requires an RF (§3.2).

Figures: none — paragraph plus a table row.
FACTS.md: Table A `GEE_SVR` rows; EXPERIMENT_MAP.md estimator-selection section.
Cite: Žgela p. 5, Fig. 4.

### 4.3 Where the signal is — 0.5 pp

**Claim:** The percentile composite's advantage comes from the **low red and high
NIR percentiles** — a seasonality signal that a single median cannot express.

Now quantified, not qualitative. `feature_importance_RF.csv` (written by the
2026-09-01 re-run) ranks by permutation importance:

| Rank | Band | Perm. importance | Impurity |
|---|---|---|---|
| 1 | **B4_p25** | 0.181 | 0.352 |
| 2 | **B4_p10** | 0.056 | 0.116 |
| 3 | **B8_p90** | 0.040 | 0.066 |
| 4 | B4_p50 | 0.023 | 0.075 |
| 5 | **B8_p75** | 0.021 | 0.045 |

B4_p25 alone carries **3.3× the permutation importance of the next band**. Four
of the top five are the low percentiles of red (B4) and the high percentiles of
NIR (B8) — precisely the quantiles a median discards, which is the mechanistic
explanation for §4.1's ranking.

Contrast with the embeddings run (Žgela p. 6, Fig. 7): there the top two are
bands **B16 and B08** of the 64-dimensional embedding, which are not physically
interpretable. Worth one sentence — the S2 composites give an interpretable
answer to *why* they work, and the embeddings do not.

Figures: **F6** `figD_importance_RF.png` (percentile) — **EXISTS/KEEP**,
regenerated 2026-09-01.
Data: `outputs_S2_percentile_p10p25p50p75p90/feature_importance_RF.csv`.
Cite: Žgela p. 6, Fig. 7 for the embedding comparison.

---

## 5. Vietnam results — same-source validation — 3 pp

**Claim:** Zero-shot transfer of a Milan-trained model to Hanoi or HCMC fails;
local retraining is necessary and sufficient.

### 5.1 Zero-shot versus local retrain — 2 pp

Zero-shot R² is at or below zero in three of four city × predictor combinations
(−0.070, −0.279, −0.142, +0.042) — the transferred models are no better than
predicting the mean. Local retraining recovers R² 0.52–0.65 in every case.
Biases −23 to −30 show the transferred models systematically over-predict
against GHSL.

Both predictor sets behave the same way, so the failure is not specific to
embeddings or to S2.

Figures: **F7** `fig01_transfer_comparison.png` — **NEEDS-EDIT**. Correct for
same-source validation but its bias bars are measured against GHSL; the caption must say so
explicitly and must not be read as accuracy. **F8**
`fig_obs_vs_pred_hanoi_hcmc.png` — **EXISTS/KEEP**, the qualitative map view.
FACTS.md: Table A, all eight Vietnam rows.

### 5.2 Per-class behaviour — 1 pp

Where in the IMD range the transfer fails, and where local retraining helps.

**Correct a plausible but wrong claim here.** Local retraining does *not* improve
every class. On the re-run tables it helps sharply in C0–C3 (Hanoi C0 MAE
40.75 → 6.36) but is **worse** in C5–C6 (Hanoi C6 MAE 17.25 → 30.95; HCMC C6
12.93 → 25.20). Žgela reports the same pattern (p. 9): improvements "mainly
visible in the lower IMD classes (C0–C3)", with the retrained model challenged
above 80 % imperviousness. Say so — it is a real limitation of local retraining,
not noise.

⚠ **Per-class R² is available but should not be quoted as a performance figure.**
Every defined value is negative (−1.3 to −115.6) because restricting to one class
removes the variance R² is normalised by. Use per-class RMSE/MAE/Bias instead,
and reserve R² for the global comparison in §5.1. Classes 0 and 6 are blank by
construction — single-valued strata, zero variance.

Figures: **F9** `fig02_per_class_mae.png` — **EXISTS/KEEP**.
FACTS.md: none — sourced from `per_class_metrics.csv` (now carries `R2`).
Cite: Žgela p. 9, Fig. 10.

---

## 6. Independent validation — 4 pp

**Claim:** Against photo-interpretation, the Milan spread largely disappears —
and the training products themselves score no better than the models trained on
them.

### 6.1 All fifteen maps — 2 pp

Every map in all three cities scored on 450 plots each, strict rule. The Milan
four collapse from a same-source validation spread of 9.46–14.12 to 24.64–25.98. Overlapping
bootstrap CIs make the point visually.

Figures: **F10** `fig02_forest_ci.png` — **EXISTS/KEEP**. The report's
centrepiece: all 15 maps, targets as diamonds, noise-corrected RMSE ticked.
**F11** `fig01_scatter_grid.png` — **EXISTS/KEEP**.
FACTS.md: Table B, all primary-rule rows.

### 6.2 Two tiers under paired testing — 1 pp

**Claim:** The Milan four are not a clean ranking of four but two tiers of two —
(stack, percentile) and (emb_RF, median) — indistinguishable within each tier but
separated between them.

**This is independent validation analysis and belongs here, not in §4.** The test runs on
per-plot absolute error against the photo-interpreted reference
(`abs_error` in `validation_per_plot_long.csv`), so placing it beside §4's
CLMS-scored holdout numbers would merge the tracks that §3.4 keeps apart.

Paired Wilcoxon with BH-FDR within city: each of stack/percentile separates from
each of emb_RF/median (q from 3.6e-08 to 6.8e-03), but stack does **not** separate
from percentile (q = 0.79) and emb_RF does **not** separate from median (q = 0.79).

Two points to state explicitly, because §6.1 has just shown overlapping CIs:

- The paired test and the RMSE CIs **measure different quantities and are both
  correct.** The CIs describe each map's RMSE uncertainty on its own; pairing
  compares two maps on the same 450 plots, removing plot-level variance and
  gaining power. Overlapping CIs plus a significant paired difference is not a
  contradiction.
- So the §6.1 collapse and this tier structure are **both true**. The four-way
  spread shrinks sharply; it does not vanish.

Figures: none — carried by a table.
FACTS.md: paired-significance table, six Milan rows.

### 6.3 The training products, scored as maps — 1 pp

**A paragraph, not a subsection with its own figures** — the forest plot already
shows it. CLMS scores RMSE 26.253, worse than all four Milan models it trained.
GHSL scores 40.345 (Hanoi) and 37.355 (HCMC), worse than every local retrain.
Note the CLMS MAE/RMSE split (best MAE 14.61, worst RMSE) and that this does not
contradict the argument.

State plainly that this measures **label quality**, and is **not** a ceiling on
achievable model performance — §7.3 gives the mechanism and the measurement.

FACTS.md: Table B rows with `role = reference`.

### 6.4 Rule sensitivity — 1 pp

**Claim:** The conclusion does not depend on the impervious coding.

Ranking is unchanged under rule B. Under C the top two and CLMS hold position
while emb_RF and S2_median swap 3rd/4th — a flip between two maps §6.2 has just
shown are indistinguishable (q = 0.79), so a reordering within noise. All five
Milan maps including CLMS improve under C.

Figures: none — carried by a table.
FACTS.md: Milan rule-ranking table; rule-code counts.

---

## 7. Discussion — 3 pp

### 7.1 From same-source to independent — 1 pp

**Claim:** Most of the same-source validation separation between predictor sets was agreement
with CLMS rather than accuracy — but a real, resolvable difference survives.

The percentile composite leads the embeddings by **4.66 RMSE on same-source validation but only
0.82 on independent validation**. Across all four sets the spread falls from **4.661 (33.0 % of
the worst map, 14.123) to 1.340 (5.2 % of the worst, 25.984)** — a **6.4-fold**
compression. same-source validation remains the right instrument for *model selection*; it is
the wrong instrument for claiming accuracy.

Note the worst map differs by track — emb_RF on same-source validation, S2_median on independent validation —
which is itself part of the collapse: the ordering is not merely compressed but
partly reshuffled.

**Do not overstate the collapse.** §6.2's paired testing still resolves two tiers
on the same data, so the residual difference is real and detectable, not lost in
noise. The honest statement is that the advantage **shrinks sharply but does not
disappear**: the gap is small relative to each map's own error, yet consistent
enough across 450 paired plots to be significant. Both facts belong in the same
paragraph, or a reader will take one and drop the other.

Figures: **F12** `report/figs/fig_samesource_vs_independent.png` — **BUILT**. Slope chart, four Milan predictor sets, same-source RMSE → independent validation
RMSE, CLMS marked on the independent validation axis.
FACTS.md: Table A Milan `GEE_RF` rows + Table B Milan primary-rule rows.

### 7.2 Why transfer fails: level-matching and saturation — 1 pp

**Claim:** The transferred maps fail because their prediction range does not
match the target city, and in HCMC the embeddings zero-shot has saturated
outright.

Zero-shots inherit Milan's high level (Hanoi 61.77 and 61.93; HCMC 70.70 and
57.89); local retrains inherit GHSL's low level (37.87–39.97). Which scenario wins a given city is
therefore partly set by that city's reference level — HCMC's S2 zero-shot
"winning" at RMSE 25.95 is this effect, not evidence of good transfer.

The stronger evidence is saturation: HCMC `emb_zeroshot` never predicts below
**31.9 %** at any plot, and **0.00 % of 8.2 M valid pixels** fall below 20 %,
against a reference where 39.3 % of plots do. Its IQR is 26.0 against the
reference's 100.0. The low tail is absent, not displaced — a shifted map would
keep its spread. The reference is bimodal (37.3 % of plots below 10 %, 35.8 %
above 90 %) and a map spanning 31.9–91.4 can represent neither mode.

Figures: **F13** `report/figs/fig_hcmc_prediction_histogram.png` — **BUILT** (merges
FIGURE_GAPS.md gap 3 with the saturation evidence). Predicted-IMD distribution
for the four HCMC maps against the reference; the level-matching means annotated
so one figure carries both arguments.
FACTS.md: HCMC saturation stats table and distribution table.

### 7.3 Retraining works: bias recovery — 1 pp

**Claim:** Local retraining does not merely reproduce GHSL's offset — it recovers
between a third and two thirds of it, so the models extract signal their labels
lack.

**Frame this as quantification, not discovery.** Žgela already reported the
effect qualitatively (p. 10): roads and unroofed impervious surfaces "are visibly
better represented in the predicted maps", which "highlights the ability of the
model to recover additional information beyond what was explicitly provided
during training." He observed it by visual inspection of Fig. 11. The
contribution here is to **measure it against an independent reference**, which
his study had no means to do.

GHSL under-marks by +19.68 pp (Hanoi) and +19.80 pp (HCMC). The local retrains
are biased only +6.59 to +12.23, recovering 7.57–13.09 pp — 38–67 %, and more in
Hanoi than HCMC. This is the mechanism behind §6.2: a model can legitimately
score better than its own training target, because random per-pixel label error
cannot be fitted and is smoothed away, and because the predictors carry signal
the target never encoded.

Figures: **F14** `report/figs/fig_bias_recovery.png` — **BUILT**.
Arrows from GHSL's bias to each local retrain's, per city.
FACTS.md: bias-recovery table.

---

## 8. Limitations — 1.5 pp

**Claim:** Three constraints bound what the results support.

1. **Composite depth is confounded with predictor type in Vietnam.** Milan's
   median draws on ~30 looks per pixel, Hanoi's on 3.82 and HCMC's on 2.66. The
   embeddings zero-shot compares annual against annual; the S2 zero-shot does
   not. An embeddings-versus-S2 conclusion in Vietnam cannot be separated from
   depth. Refer back to F1.
2. **Plot-level independence is assumed and untested.** The 450 plots per city
   are treated as independent in every metric and paired test; no spatial
   autocorrelation check is applied at plot level.
3. **`RMSE_corr` is an upper bound, not a point estimate.** Sub-cells within a
   10 m pixel are spatially correlated, so the binomial correction understates
   true reference noise. Use it to bound map error, never to claim a specific
   map's error equals the corrected figure.

Also state: single interpreter, no inter-rater agreement estimate; plots
stratified by the product under test, so metrics are not area-weighted and are
not city-wide accuracy.

Figures: none.
FACTS.md: `RMSE_corr` note. EXPERIMENT_MAP.md: validation-unit and
composite-window sections.

---

## 9. Conclusions — 1 pp

**Claim:** Explicit Sentinel-2 composites outperform the foundation-model
embeddings against CLMS in Milan by a wide margin; against independent
photo-interpretation that margin **shrinks roughly sevenfold but remains
resolvable**; zero-shot transfer to Vietnam fails and local retraining is
required; and both training products score no better than the models fitted to
them — which measures the quality of the labels, not a limit on the maps.

Four numbered conclusions:

1. **Composite choice matters more than the foundation model, on same-source validation.**
   Percentile 9.46 against embeddings 14.12 RMSE — a 33 % reduction, consistent
   across RMSE, MAE and R². The advantage is mechanistically interpretable: the
   low red and high NIR percentiles a median discards carry most of the signal
   (§4.3).

2. **Against independent reference the four-way spread compresses 6.4-fold —
   from 33.0 % to 5.2 % of the worst map — yet paired testing still resolves two
   tiers** (§6.2). State both halves. Most of the same-source validation separation was
   agreement with CLMS; a real, detectable difference nonetheless survives. It is
   neither "confirmed" nor "eliminated" by validation, and writing it as either
   misreports the result.

3. **Zero-shot transfer fails; local retraining is necessary.** R² at or below
   zero in three of four city × predictor combinations, recovering to 0.52–0.65
   when retrained. The failure mechanism is range mismatch, and in HCMC the
   transferred embedding map is saturated outright (§7.2). Retraining is not
   uniformly better — it is worse above 80 % imperviousness (§5.2).

4. **The training products are not ceilings.** CLMS scores 26.253 and GHSL 40.345 /
   37.355 against photo-interpretation, no better than the models fitted to them.
   This measures **label quality**: it says further gains are unlikely to come
   from features or estimators alone while the labels disagree with
   interpretation this much. It does **not** bound achievable accuracy — §7.3
   measures the models recovering **38–67 %** of GHSL's systematic deficit,
   which is a model outperforming its own labels. Any sentence implying the
   target caps the map contradicts §6.3 and §7.3 and must not be written.

Figures: none.
FACTS.md: Table A Milan rows; Table B primary-rule rows; paired-significance
table; bias-recovery table.

---

# Consolidated figure list

| # | Figure | Section | Status | Source |
|---|---|---|---|---|
| F1 | `fig_composite_depth.png` (`report/figs`) | 2.3, ref. 8 | **BUILT** | gap 5 |
| F2 | `fig01_spatial_split.png` (`outputs_v2`) | 3.1 | EXISTS / KEEP | FIGURES.md |
| F3 | `fig06_inflation_heatmap.png` | 3.2 | EXISTS / KEEP | FIGURES.md |
| F4 | `fig07_holdout_scatter.png` (percentile) | 4.1 | EXISTS / KEEP | FIGURES.md |
| F5 | `figC_perclass_GEE_RF.png` (percentile) | 4.1 | EXISTS / KEEP | FIGURES.md |
| F6 | `figD_importance_RF.png` (percentile) | 4.3 | EXISTS / KEEP | FIGURES.md |
| F7 | `fig01_transfer_comparison.png` | 5.1 | EXISTS / KEEP | FIGURES.md |
| F8 | `fig_obs_vs_pred_hanoi_hcmc.png` | 5.1 | EXISTS / KEEP | FIGURES.md |
| F9 | `fig02_per_class_mae.png` | 5.2 | EXISTS / KEEP | FIGURES.md |
| F10 | `fig02_forest_ci.png` | 6.1 | EXISTS / KEEP | FIGURES.md |
| F11 | `fig01_scatter_grid.png` | 6.1 | EXISTS / KEEP | FIGURES.md |
| F12 | `fig_samesource_vs_independent.png` (`report/figs`) | 7.1 | **BUILT** | gap 1 |
| F13 | `fig_hcmc_prediction_histogram.png` (`report/figs`) | 7.2 | **BUILT** | gaps 3 + 4 merged |
| F14 | `fig_bias_recovery.png` (`report/figs`) | 7.3 | **BUILT** | gap 4 |

**Total 14 figures** — 9 from notebooks (all KEEP) and 4 built into
`report/figs/` by `code/make_report_figs.py`. Within the 12–14 target.

Tables (not counted as figures): same-source validation summary (§4.1), paired tests (§4.2),
CV-vs-holdout (§4.3), rule sensitivity (§6.3).

## Disposition of the seven gaps

| Gap | Disposition |
|---|---|
| 1 · same-source vs independent | **BUILD** — F12, §7.1. Ranked first in FIGURE_GAPS.md |
| 2 · Milan two-tier | **DROP as a figure** — §4.2 carries it as a table; six rows do not need a plot |
| 3 · Vietnam level-matching | **MERGE into F13** — the HCMC histogram shows the level means and the saturation in one frame |
| 4 · Bias recovery | **BUILD** — F14, §7.3 |
| 5 · Composite depth | **BUILD** — F1, §2.3, referenced again in §8 |
| 6 · CV-vs-holdout reversal | **DROP** — §4.3 is a paragraph plus a table row |
| 7 · Rule sensitivity slopes | **DROP** — §6.3 carries it as a table |

Four builds, one merge, three dropped.

---

# Reference report — citable anchors

`reference/RELAZIONE FINALE - Zgela_LCZ-UHI-GEO_Incarico_Report_signed (1).pdf`
— 12 pages. Matej Žgela (10994288), PhD student, Dept. of Civil and
Environmental Engineering. Open call BANDO N. 2026_VALCOMP_DICA_9, ID 18754,
supporting the ITALY–VIETNAM *Local Climate Zones, Urban Heat Island and
Geomatics* (LCZ-UHI-GEO) project, CUP D47G24000110001.

The report has **no numbered subsections** — one numbered heading ("1.
Imperviousness Mapping Using Satellite Embeddings", p. 1). Cite by **page and
figure number**:

Two numbered headings only: **"1. Imperviousness Mapping Using Satellite
Embeddings"** (p. 1, with an unnumbered subsection *b. Model training and
evaluation* on p. 4), **"2. Method Transferability and Application in Vietnam"**
(p. 8), **"3. Conclusions"** (p. 10).

| Anchor | Page | Use in this report |
|---|---|---|
| Fig. 1 — training/test point distribution, ANN analysis | 2 | §3.1 sampling design |
| Fig. 2 — IMD value distribution at point locations | 3 | §3.1 stratification |
| Fig. 3 — top 6 discriminative AlphaEarth bands (Kruskal–Wallis) | 3–4 | §2.2 embeddings |
| Fig. 4 — CV RMSE, best models | 5 | §3.2 tuning, §4.3 |
| Fig. 5 — RMSE and MAE per IMD class | 6 | §4.1 |
| Fig. 6 — holdout test accuracy, RF | 6 | §4.1 |
| Fig. 7 — impurity and permutation importance, top 20 bands | 7 | §4.4 |
| Fig. 8 — observed/predicted rasters and difference | 7 | §4.4 |
| Fig. 9 — transfer vs local retrain metrics | 9 | §5.1 |
| Fig. 10 — per-class MAE, transfer vs local | 9 | §5.2 |
| Fig. 11 — GHSL vs predicted IMD | 10 | §2.1, §6.2 |

### Specifics available for the compressed subsections

**§3.1 sampling and blocking** (Žgela pp. 2, 4) — the reference IMD map
classified into 7 groups (0 %, 1–20, 21–40, 41–60, 61–80, 81–99, 100 %);
stratified random sampling of **500 points per group = 3 500 total**; spatial
randomness verified by average nearest neighbour index, **highest 1.02 (class 0),
lowest 0.75 (class 6)** — the clustering of fully impervious pixels acknowledged
as a sampling limitation. Split by 1 km × 1 km blocks assigned whole to train or
test, 250 m buffer removing test points within 250 m of a training point,
yielding **2 449 training and 1 014 test points (~70/30)** — the same 1 014 this
project reports. Tuning by spatially aware 5-fold CV over 500 m / 1 km / 2 km
blocks.

**§2.2 embeddings** (Žgela pp. 3–4, 6) — all 64 bands tested per IMD group by
Kruskal–Wallis H-test; **60 of 64 differ significantly across classes**, with
bands 16, 8, 41, 58, 30 and 55 most discriminative. A side experiment on feature
selection found **all 64 bands outperform any reduced subset** (p. 5).
Permutation importance later confirms **B16 and B08** as the top two (p. 6).

**§2.1 GHS-BUILT-S road exclusion** (Žgela pp. 8, 10) — his own words: the
product "doesn't include all impervious surfaces such as roads", and this is
"an inherent limitation of the chosen reference dataset". He adds that no other
suitable 2018 reference existed for Vietnam. Cite him for the limitation rather
than asserting it independently.

**§7.3 bias recovery — Žgela observed this qualitatively first** (p. 10). He
notes that roads and unroofed impervious areas "are visibly better represented in
the predicted maps, although still imperfectly, as the model itself was trained
against the GHS-BUILT-S reference", and that this "highlights the ability of the
model to recover additional information beyond what was explicitly provided
during training." **This project's contribution is to quantify that observation**
— 7.57–13.09 pp, 38–67 % of the deficit — not to discover it. §7.3 must be
framed as quantification and cite p. 10.

**§5.1 — his transfer conclusion matches** (p. 8): the Milan model transfer "led
to significantly lower accuracy, indicating that a model trained on data from one
city cannot be straightforwardly applied to another geographic region", with
local retraining raising R² "from negative values to about 0.50–0.60". This
project reproduces that with a second predictor set. Note his per-class caveat
(p. 9): retraining helps mainly in C0–C3 and is *worse* in C5–C6.

## The reproduction claim is confirmed

Žgela, p. 5, verbatim: *"RF outperformed SVR across all metrics: R² = 0.837 vs
0.822, MAE = 10.68% vs 11.40%, RMSE = 14.12% vs 14.76%, and Bias = +0.62% vs
+0.27%. RF is therefore selected as the final model."*

This project's independent re-run gives **RMSE 14.123, MAE 10.675, R² 0.837,
Bias +0.624** for `GEE_RF` and **14.756 / 11.400 / 0.822 / +0.274** for
`GEE_SVR` (FACTS.md Table A). **Every figure matches to the published precision,
for both estimators.** §1 may assert the exact reproduction as fact and cite
p. 5.

Two further points from p. 5 that bear on §4.3:

- Žgela reports the **same CV-versus-holdout reversal**: SVR won CV at 11.5 %
  (500 m block) while RF was ~1.6 % worse, and RF then won every holdout metric.
  This project's §4.3 finding is therefore a **reproduction**, not a new
  observation — say so, and cite p. 5.
- He selects RF for the same reason. Note that his stated cause is that a third
  estimator is unsupported in GEE's Python API; **SVR itself is supported and is
  used here** (`ee.Classifier.libsvm`), so §4.3 should not repeat any claim that
  SVR could not be rastered.

# Resolved since the interview

All three code changes are made **and the notebooks re-run** (2026-08-31 /
2026-09-01, all exit 0).

- **Vietnam per-class R²** — notebooks 02 and 03, cell 17, guarded against
  zero-variance classes (`np.ptp(obs_c) > 0`, else NaN). Both re-run; `R2` is now
  in `per_class_metrics.csv` in both transfer directories. See the §5.2 warning:
  every defined value is negative and must not be quoted as a performance figure.
- **Feature importance CSV** — notebooks 01 (cell 46) and 01b (cell 47) write
  `feature_importance_RF.csv`: band, impurity importance, permutation mean and
  std, rank. 01b re-run on the percentile composite; §4.4 now has its numbers.
- **Reproducibility confirmed as a side effect.** All three re-runs reproduced
  their headline metrics **bit-identically** against `FACTS.md` — Vietnam
  transfer (both predictor sets, both cities, both scenarios) and the Milan
  percentile holdout (`GEE_RF` 9.462 / 6.389 / 0.927 / −0.104, `GEE_SVR` 9.051 /
  5.810 / 0.933 / −0.513). The changes were purely additive and the pipeline is
  deterministic. Worth one sentence in §3 or the conclusions.

**Notebook 01b is left on `COMPOSITE_METHOD='percentile'`.** Its output directory
was regenerated on 2026-09-01, so the figures the deck embeds from it
(`fig06_inflation_heatmap.png`, `figD_importance_RF.png`,
`figE_raster_comparison_1.png`) now postdate the deck.

# Still outstanding

1. **A figure-numbering convention for the four new builds.** Existing files use
   notebook-local names (`fig01_`, `figA_`). The four new figures belong to no
   notebook — proposed `code/make_report_figs.py` writing to `report/figs/`,
   following the `make_presentation.py` house style recorded in FIGURES.md
   (accent `#0B6E4F`, DejaVu Sans, dpi 200).

2. **`data/FACTS.md` is unchanged and still correct**, but does not yet carry the
   new per-class R² or the feature importances. Re-running
   `code/collect_metrics.py` would not pick them up either — the collector reads
   `transferability_comparison.csv` and `holdout_test_metrics.csv`, not the
   per-class or importance tables. Extend the collector if those numbers should
   live in the fact base rather than being read from the CSVs directly.
