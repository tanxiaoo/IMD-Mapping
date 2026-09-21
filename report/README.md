# Report

`report.tex` is the single source. Everything else here is generated or input.

Three files at this root are the deliverables — the only things anyone
outside the project is handed. Everything else supports them and lives in a
subfolder.

| Path | What it is |
|---|---|
| `report.tex` | **Deliverable.** The report. Edit this. |
| `report.pdf` | **Deliverable.** Built output. Rebuild it, do not edit it. |
| `IMD_Mapping.pptx` | **Deliverable.** The presentation. |
| `refs.bib` | Bibliography. BibTeX assigns the numbers. |
| `latexmkrc` | Build configuration: engine, output paths, `BIBINPUTS`. |
| `facts/` | The written record: `FACTS.md`, `EXPERIMENT_MAP.md`, `FIGURES.md`, `FIGURE_GAPS.md`, `OUTLINE.md`. Version-controlled. |
| `figs/` | Every cited figure. Seven built by `code/make_report_figs.py`; the rest copied from the run directories by `code/sync_figs.py`, into a folder named after the run. |
| `presentation/` | Deck sources — slide code, its figures, the builder notebooks. Gitignored. |
| `build/` | LaTeX auxiliaries (`.aux`, `.log`, …), gitignored. |

`report.pdf` and `IMD_Mapping.pptx` are build products, which elsewhere in this
repository is reason to ignore a file. They are committed anyway: they are what
gets handed over, and a reader without XeLaTeX still needs them.

## Building the PDF

From this directory:

```
latexmk
```

That is the whole command. `latexmkrc` selects XeLaTeX and sets the paths, so
`report.pdf` is written here next to `report.tex` and the auxiliary files go to
`build/`. latexmk reruns the engine as many times as the cross-references need,
so there is no "compile twice" step to remember.

XeLaTeX is required rather than optional: the text carries U+2212 minus signs,
mid dots and the name Žgela.

Other forms:

```
latexmk -pv        # build, then open the PDF in the default viewer
latexmk -pvc       # rebuild automatically on every save
latexmk -C         # delete the PDF and everything in build/
```

**If the build fails with `Unable to open "report.pdf"`,** the PDF is open in a
viewer holding a write lock. Close it, or use `latexmk -pvc`, whose viewer
reloads in place.

## After editing

```
python code/audit_numbers.py report/
```

from the repository root. It checks that every number traces to
`report/facts/FACTS.md`, every figure file exists, every `\label` is defined once and
referenced, and every citation resolves. Run it after each section, not only at
the end.

## Figures

The report generates figure titles and captions; the figure code generates only
the visualisation. No figure carries a rendered figure number — see the
`# Figures` section of `CLAUDE.md` for why, and `report/facts/FIGURES.md` for the
inventory and how to rebuild a stale one.

Reference floats with `\cref{fig:...}` / `\cref{tab:...}`. Never write a literal
"Figure 7" in the prose: LaTeX assigns the numbers and a hardcoded one goes
stale as soon as a float moves.

## History

The report was drafted in Markdown as `report.md` and exported to `.docx` and
PDF. That route was retired on 2026-09-01 once the LaTeX conversion was verified
— section headings, all 26 float labels, every citation and every numeric value
checked across the two. `report.md` and the `.docx` exports were then deleted;
`git log -- report/report.md` recovers them if an old wording is ever needed.
