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
  arguments. It reruns until the cross-references settle and runs the BibTeX
  pass the bibliography needs.
- `report/` is a self-contained Overleaf project: it compiles from
  `report.tex`, `refs.bib` and `figs/` alone, with no file outside it. Keep it
  that way — never add a `../` path to `\graphicspath` or `\input`.
- References are `\cite` keys against `report/refs.bib`, numbered by BibTeX
  (natbib, `unsrtnat`). Never hardcode a `[3]`: BibTeX assigns the numbers and
  a literal one goes stale exactly as a hardcoded figure number does.
- After regenerating any cited figure, run `python code/sync_figs.py` to
  refresh the copies under `report/figs/`. It is idempotent, and it exits 1
  naming any cited figure it cannot find.
- Cross-reference every float with `\cref{}` against the label bound to its own
  caption. Never write a literal "Figure 7" or "Table 3" in the prose: LaTeX
  numbers the floats, and a hardcoded number goes stale the moment one moves.
- One section per turn. Never write the whole report in one pass.
- Match `reference/` for tone: numbered sections, plain declarative
  sentences, figures captioned below.
- British English. No em dashes.
- After each section, run: `python code/audit_numbers.py report/`
- Figures are placed at their referenced positions with numbered captions below, matching reference/.

## Full audit

`code/audit_numbers.py` is the quick per-section check and defaults to
`data/FACTS.md` alone. For a full audit of the finished report, use the
generalised auditor from the `research-report` skill, which additionally checks
bare integers and takes both fact bases:

```
python ~/.claude/skills/research-report/scripts/audit_numbers.py \
    --facts data/FACTS.md --facts data/EXPERIMENT_MAP.md \
    --report report/report.tex --outline report/OUTLINE.md \
    --stale-term "Track A" --stale-term "Track B" \
    --allow-number 99 --allow-number 1000
```

**Pass both fact bases.** Design parameters (64 embedding bands, 500 points per
group, 250 m buffer, 2 449 train / 1 014 test) live in `EXPERIMENT_MAP.md`, not
`FACTS.md`. Omitting it reports 18 false positives on numbers that are genuinely
sourced.

**What the two `--allow-number` values waive, and the risk.** Both are
structural rather than measurements: `99` is a class boundary in the printed
range "81 to 99", and `1000` is a block size written `1000\,m`. Neither is a
result, so neither belongs in the fact base — but the allowance is by value, not
by context. **If 99 or 1000 ever becomes a real claim, the allowance hides it**:
the number would pass unchecked whether or not the fact base supports it. Before
adding a number to this list, confirm it can never appear as a result; before
quoting either value as a measurement, remove its allowance and re-run.

The skill's auditor deliberately does **not** strip `in` as a unit, so
"0.42 in the second run" is checked rather than silently dropped — a
construction that occurs 18 times in `report.tex`. Run it with `--self-test`
after any change to the report's numeric or figure conventions: it injects
known-bad values and confirms the checks still fail on them.

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
  is a deliberate departure from `make_presentation.py` (repo root, not
  `code/`), whose slide titles are written as conclusions.

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
