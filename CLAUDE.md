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

# Writing

- Draft in Markdown at `report/report.md`. Export to `.docx` only at the end.
- One section per turn. Never write the whole report in one pass.
- Match `reference/` for tone: numbered sections, plain declarative
  sentences, figures captioned below.
- British English. No em dashes.
- After each section, run: `python code/audit_numbers.py report/`

# Regenerating

- `python code/collect_metrics.py` rebuilds `data/FACTS.md` from the run
  directories. `python code/make_report_figs.py` rebuilds the four figures in
  `report/figs/` from FACTS.md.
- To change a notebook figure's labelling, redraw it from the CSV the notebook
  already wrote. Re-executing a notebook re-tunes models and re-exports rasters
  to Earth Engine, which takes many minutes and risks drift.
- Never edit a notebook while `nbconvert` is executing it: nbconvert reads the
  file at startup, so the run silently uses the pre-edit copy.
