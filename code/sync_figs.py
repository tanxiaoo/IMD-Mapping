"""Copy every figure cited by report/report.tex into report/figs/.

`report/` is a self-contained Overleaf project: it must compile with no file
outside it. Four of its figures are built by `make_report_figs.py` straight into
`report/figs/`, but the rest live in the notebook run directories
(`outputs_v2/`, `outputs_validation/`, `outputs_transfer_*/`, ...) and were
previously reached with a `../` entry in \graphicspath. That works in this
checkout and nowhere else.

This script copies them in instead. It does not re-path the pipeline: the
notebooks keep writing where they always wrote, and `report/figs/` holds copies
that this script refreshes.

LAYOUT
------
The copy mirrors the source directory under `figs/`:

    outputs_v2/fig01_spatial_split.png  ->  report/figs/outputs_v2/fig01_spatial_split.png

so filenames are unchanged and `\graphicspath{{figs/}}` resolves every existing
\includegraphics path without editing a single one. Mirroring rather than
flattening is not cosmetic: `fig01_transfer_comparison.png` exists in both
`outputs_transfer_v2/` and `outputs_transfer_S2_median/`, and the report cites
both. A flat copy would silently drop one of them.

Figures already inside `report/figs/` (the four from `make_report_figs.py`) are
cited as `figs/fig_*.png`, resolve as themselves, and are left alone.

IDEMPOTENCE
-----------
A file is copied when it is missing or when its content differs from the source
(size, then SHA-256). Content rather than mtime: a rebuild that reproduces an
identical PNG should report "current", and a `git checkout` that resets mtimes
should not trigger a spurious copy. Re-running the script when nothing has
changed copies nothing and exits 0.

Usage:  python code/sync_figs.py [--report PATH] [--dry-run]

Exit status is 1 if any cited figure could not be found, so the script can gate
a build.
"""

import argparse
import hashlib
import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPORT = os.path.join(REPO, 'report', 'report.tex')
FIGS = os.path.join(REPO, 'report', 'figs')

# \includegraphics[...]{path} -- the optional argument may carry a % line break
# between it and the brace group, as the landscape scatter grid does.
INCLUDE_RE = re.compile(
    r'\\includegraphics\s*(?:\[[^\]]*\])?\s*%?\s*\{([^}]*)\}', re.DOTALL)


def cited_paths(tex_path):
    """Figure paths as written in the .tex, in citation order, de-duplicated."""
    with open(tex_path, encoding='utf-8') as fh:
        text = fh.read()
    # Drop commented-out lines so a disabled figure is not treated as cited.
    text = re.sub(r'(?<!\\)%[^\n]*', '', text)
    seen, out = set(), []
    for m in INCLUDE_RE.finditer(text):
        ref = m.group(1).strip().replace('\\', '/')
        if ref and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def same_content(src, dst):
    if not os.path.exists(dst):
        return False
    if os.path.getsize(src) != os.path.getsize(dst):
        return False
    return _digest(src) == _digest(dst)


def resolve(ref):
    """Where a cited path lives now, and where its copy belongs under figs/.

    Returns (source_abs, dest_abs) or (None, None) when the figure is already
    inside report/figs/ and needs no copy, or (None, ref) when it is missing.
    """
    # Already a figs/ figure: cited as figs/foo.png, lives at report/figs/foo.png.
    if ref.startswith('figs/'):
        inside = os.path.join(REPO, 'report', ref)
        return (None, inside if os.path.exists(inside) else None)
    src = os.path.join(REPO, ref)
    if not os.path.exists(src):
        return (None, None)
    return (src, os.path.join(FIGS, ref))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--report', default=DEFAULT_REPORT,
                    help='path to report.tex (default: report/report.tex)')
    ap.add_argument('--dry-run', action='store_true',
                    help='report what would be copied, change nothing')
    args = ap.parse_args()

    if not os.path.exists(args.report):
        print(f'sync_figs: no such report: {args.report}')
        return 2

    refs = cited_paths(args.report)
    copied, current, in_place, missing = [], [], [], []

    for ref in refs:
        src, dst = resolve(ref)
        if src is None:
            if dst is None:
                missing.append(ref)
            else:
                in_place.append(ref)
            continue
        if same_content(src, dst):
            current.append(ref)
            continue
        if not args.dry_run:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        copied.append(ref)

    verb = 'would copy' if args.dry_run else 'copied'
    print(f'sync_figs: {len(refs)} figures cited by '
          f'{os.path.relpath(args.report, REPO)}')
    print(f'  {verb:>10}: {len(copied)}')
    for ref in copied:
        print(f'      + {ref}')
    print(f'  {"current":>10}: {len(current)}')
    for ref in current:
        print(f'      = {ref}')
    print(f'  {"in figs/":>10}: {len(in_place)}   '
          f'(built by make_report_figs.py, not copied)')
    for ref in in_place:
        print(f'      . {ref}')
    if missing:
        print(f'  {"MISSING":>10}: {len(missing)}')
        for ref in missing:
            print(f'      ! {ref}  -- cited but not found under {REPO}')
        print('\nsync_figs: report/ will NOT compile standalone until these '
              'are produced.')
        return 1
    print('\nsync_figs: every cited figure is present under report/figs/.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
