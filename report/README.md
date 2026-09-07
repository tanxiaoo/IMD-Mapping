# Report

`report.tex` is the single source. Everything else here is generated or input.

| Path | What it is |
|---|---|
| `report.tex` | The report. Edit this. |
| `report.pdf` | Built output, gitignored. Rebuild it, do not edit it. |
| `latexmkrc` | Build configuration: engine and output paths. |
| `build/` | Auxiliary files (`.aux`, `.log`, …), gitignored. |
| `figs/` | The four figures built by `code/make_report_figs.py`. |
| `OUTLINE.md` | Section plan, claims and figure assignments. |

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
`data/FACTS.md`, every figure file exists, every `\label` is defined once and
referenced, and every citation resolves. Run it after each section, not only at
the end.

## Figures

The report generates figure titles and captions; the figure code generates only
the visualisation. No figure carries a rendered figure number — see the
`# Figures` section of `CLAUDE.md` for why, and `data/FIGURES.md` for the
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
