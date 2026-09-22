# Deliverables

The two files handed over: the report and the presentation.

| File | What it is |
|---|---|
| `report.pdf` | the full write-up |
| `IMD_Mapping.pptx` | the presentation |

Both are built in `report/` and copied here when a version is finished. The
copies in `report/` are gitignored; these are the tracked ones, so this folder
is where the current handed-over versions live.

`report/report.tex` is the LaTeX source `report.pdf` is built from. Build it
with `cd report && latexmk`, then copy the result here and commit.

Note that both are large binaries and git keeps every version, so each update
adds its full size to the repository history rather than replacing the last
one. Update them when a version is actually finished rather than on every
small change.
