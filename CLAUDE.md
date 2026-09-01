# Project

Report and presentation on impervious surface density (IMD) mapping from
Sentinel-2 composites and AlphaEarth embeddings. Milan, Hanoi, HCMC, 2018.
Companion to `reference/` — the AlphaEarth report by Matej Žgela.

# Fact base — read before writing anything

- `data/FACTS.md` — all metrics
- `data/EXPERIMENT_MAP.md` — provenance and design decisions
- `data/FIGURES.md` — figure inventory
- `report/OUTLINE.md` — section plan, claims, figure assignments

# HARD RULES

- **IMPORTANT: never write a numeric result not in `data/FACTS.md`.**
  If one is needed and missing, write `[TBC]` and list it at the end.
- Never reference a figure not in `data/FIGURES.md` or `report/figs/`.
- Say "same-source validation" and "independent validation".
  Never "Track A" or "Track B".
- Bias is observed minus predicted. Positive means the map under-predicts.
  Never silently flip this.
- The two validations are never compared directly or merged.
- Never mention MLP.
- Cite Žgela for the AlphaEarth method, the shared Milan sample set, and
  anything his report established first.
- **Figure code generates the visualisation; the report generates the figure
  title and caption.** No figure carries a top-level `suptitle` that names or
  describes it, and no figure renders a figure number. See `# Figures`.

# Writing

- The report is LaTeX at `report/report.tex`. It is the single source.
  `report.md` was retired on 2026-09-01 after the conversion was verified;
  recover it from git history if an old wording is ever needed.
- Build the PDF with `cd report && latexmk`. It writes `report/report.pdf`
  beside the source and keeps the auxiliary files in `report/build/`.
  `latexmkrc` sets the engine (XeLaTeX) and both paths, so `latexmk` takes no
  arguments. Run it twice-equivalent automatically; it reruns until the
  cross-references settle.
- Cross-reference every float with `\cref{}` against the label bound to its own
  caption. Never write a literal "Figure 7" or "Table 3" in the prose: LaTeX
  numbers the floats, and a hardcoded number goes stale the moment one moves.
- One section per turn. Never write the whole report in one pass.
- Match `reference/` for tone: numbered sections, plain declarative
  sentences, figures captioned below.
- British English. No em dashes.
- After each section, run: `python code/audit_numbers.py report/`
- Figures are placed at their referenced positions with numbered captions below, matching reference/.

# Figures

**Figure code generates the visualisation; the report generates the title and
caption.** The image carries what a reader cannot infer from the plot itself;
the report carries what the figure means.

Belongs in the image:

- Per-panel subplot titles (`RMSE per Class`, `GEE_RF`, `Hanoi`). These label
  panels, and dropping them makes a multi-panel figure unreadable.
- Axis labels, units, legends, tick labels.
- In-plot annotations that are measurements: metric boxes, bar value labels.
- Run-identifying parameters **only** where the same filename exists in several
  run directories and the plot cannot distinguish them — for example the
  composite that produced a raster panel. Name the run, not the finding.

Never in the image:

- A figure number. The report numbers figures by page order, and it renumbers
  as sections move. A number rendered into a PNG silently goes stale, and
  `audit_numbers.py` checks caption-to-image agreement but **cannot read a
  number inside an image**, so nothing catches it. Keeping numbers out of
  figures removes that blind spot rather than policing it.
- A restatement of the caption. If the suptitle and the caption say the same
  thing, the suptitle goes.
- Internal names: `[S2]` run tags, `Figure A`/`Figure C` notebook ids, variable
  or estimator keys as description. A panel title of `GEE_RF` is fine; a
  suptitle of `Figure C · [S2] Per-Class Accuracy -- GEE_RF` is not.
- Conclusions. Figures state readings; every claim belongs to the caption. This
  is a deliberate departure from `make_presentation.py`, whose slide titles are
  written as conclusions.

There is no separate figure-title file. Titles live in the report caption beside
the prose that has to agree with them, and `data/FIGURES.md` remains the
inventory of what each figure shows.

# Regenerating

- `python code/collect_metrics.py` rebuilds `data/FACTS.md` from the run
  directories. `python code/make_report_figs.py` rebuilds the four figures in
  `report/figs/` from FACTS.md.
- To change a notebook figure's labelling, redraw it from the CSV the notebook
  already wrote. Re-executing a notebook re-tunes models and re-exports rasters
  to Earth Engine, which takes many minutes and risks drift.
- Never edit a notebook while `nbconvert` is executing it: nbconvert reads the
  file at startup, so the run silently uses the pre-edit copy.
