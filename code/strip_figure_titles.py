"""Remove the rendered suptitle band from notebook figures cited by the report.

CLAUDE.md: *figure code generates the visualisation; the report generates the
figure title and caption.* Eight cited notebook figures broke that rule. They
rendered a title into the PNG, and seven of the eight rendered a figure NUMBER
with it -- a number from the producing notebook, unrelated to the report's own
numbering:

    fig01_spatial_split.png        "Figure 1 - Spatial Train/Test Split"   -> report Figure 2
    figD_importance_RF.png         "Figure D - Feature Importance ..."     -> report Figure 8
    fig01_transfer_comparison.png  "Figure 1 - Same-source validation ..." -> report Figures 9, 10
    fig_obs_vs_pred_hanoi_hcmc.png "Observed vs Predicted IMD ..."         -> report Figure 11
    fig02_per_class_mae.png        "Figure 2 - Per-Class MAE ..."          -> report Figure 12
    fig02_forest_ci.png            "Figure 2 - Map accuracy ..."           -> report Figure 13
    fig01_scatter_grid.png         "Figure 1 - Reference vs predicted ..." -> report Figure 14

This is precisely the blind spot CLAUDE.md describes: `audit_numbers.py` checks
caption-to-image agreement but cannot read a number *inside* an image, so a
figure captioned "Figure 14" while displaying "Figure 1" passes every check.
Two of these suptitles were also conclusions ("Agreement with the training
target, not accuracy"), which the rule reserves for the caption.

No information is lost. Every one of these titles is already carried, more
fully, by the report's own \\caption{} -- verified against report.tex before
this script was written. That is why CLAUDE.md states there is no separate
figure-title file: the title lives in the caption beside the prose that has to
agree with it.

WHY A CROP RATHER THAN A REDRAW
-------------------------------
`redraw_notebook_figs.py` redraws two figures from their CSVs, which is the
right tool when the CSV holds everything the panel shows. These eight do not
qualify: three plot rasters that exist only as Earth Engine exports, and the
rest would need their full panel geometry reconstructed, risking a change to
the plotted data while fixing a label. Re-executing the notebooks is what
CLAUDE.md forbids for a labelling change -- it re-tunes models and re-exports
rasters.

Cropping the title band touches no plotted pixel. The band is located by
scanning for leading rows that carry ink and the blank gap that follows, then
the image is cut at that gap, so the result is the same figure minus its
suptitle. Row ranges are not hardcoded: each is found per image and asserted
against the expected band height, so a regenerated figure whose layout moved
fails loudly instead of being silently mis-cropped.

Idempotent: an image whose title band is already gone is detected and skipped,
so re-running after a notebook re-run is safe.

Usage:  python code/strip_figure_titles.py [--check]

        --check  report what would change without writing (exit 1 if any
                 figure still carries a title band)
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent

# path -> how many leading ink runs are title (the rest are panel content).
#
# `lines` counts the ink runs that belong to the suptitle. Figure 11's title
# wraps onto a second line ("Hanoi & HCMC") that is part of the suptitle, while
# its third run is the per-panel titles, which stay. Figures 2 and 12 carry a
# two-line suptitle whose second line is a parameter string.
# (path, title lines, height while still titled)
TARGETS = [
    ('outputs_v2/fig01_spatial_split.png', 2, 1088),
    ('outputs_S2_percentile_p10p25p50p75p90/figD_importance_RF.png', 1, 767),
    ('outputs_transfer_v2/fig01_transfer_comparison.png', 1, 1660),
    ('outputs_transfer_S2_median/fig01_transfer_comparison.png', 1, 1660),
    ('outputs_transfer_v2/fig02_per_class_mae.png', 2, 787),
    ('outputs_validation/fig02_forest_ci.png', 1, 907),
    ('outputs_validation/fig01_scatter_grid.png', 1, 1463),
]

# fig_obs_vs_pred_hanoi_hcmc.png cannot be cropped. Its suptitle runs to two
# lines ("Observed vs Predicted IMD -- AlphaEarth embedding (64 dims)" then
# "Hanoi & HCMC"), and the second line sits at rows 52-74 while the first row
# of panel titles starts at 76 -- the bands nearly touch, and the panel titles
# themselves are staggered across two more bands. No horizontal cut separates
# title from content.
#
# So this one is erased rather than cut: the two title lines are painted to the
# background colour, leaving the panels and their titles exactly where the
# report's caption and the figure's own layout expect them. The rows are found
# the same way as everywhere else, and the same "is this really a title line"
# guards apply, so a changed layout refuses rather than erasing a panel.
ERASE = [
    ('outputs_transfer_v2/fig_obs_vs_pred_hanoi_hcmc.png', 2, 1566),
]

# A suptitle line is a short horizontal band. Anything taller than this is
# plot content, and cropping it would cut into the figure.
#
# The limit applies to the INKED title itself, not to the title plus the
# whitespace tight_layout leaves under it. That gap is legitimately large --
# 110px on the transfer figures -- and bounding the two together would refuse
# every correctly laid out figure.
MAX_TITLE_LINE = 40      # px, one line of suptitle at these DPIs
MAX_TITLE_INK = 90       # px, the inked band, for a two-line title
WHITE = 240              # a pixel darker than this counts as ink

# A suptitle sits at the very top of the canvas; every one of these figures
# starts its title by row 20. Panel titles sit lower. Used only by the erase
# path, where height cannot serve as the already-done fingerprint.
TITLE_STARTS_BY = 30     # px


def ink_runs(gray, limit_frac=0.35):
    """Row ranges carrying ink in the top `limit_frac` of the image."""
    a = np.asarray(gray)
    h = a.shape[0]
    ink = (a < WHITE).sum(axis=1)
    limit = int(h * limit_frac)
    runs = []
    r = 0
    while r < limit:
        if ink[r] > 0:
            s = r
            while r < limit and ink[r] > 0:
                r += 1
            runs.append((s, r - 1))
        else:
            r += 1
    return runs


def plan(path, lines, expect_h=None):
    """Rows to cut, or None with a reason when nothing should change.

    `expect_h` is the height the image has while it still carries its title.
    Height is the fingerprint that makes this safe to re-run: a stripped image
    is shorter, so it is recognised and skipped. Without it a second run would
    cut the panel titles, which look exactly like a suptitle to a row scan --
    the figures would degrade silently on every re-run.
    """
    im = Image.open(path)
    if expect_h is not None and im.size[1] != expect_h:
        return None, im, (f'height {im.size[1]}px, not the {expect_h}px of a '
                          f'titled figure -- already stripped, or regenerated '
                          f'with a new layout')
    runs = ink_runs(im.convert('L'))
    if len(runs) <= lines:
        return None, im, 'no separable title band (already stripped?)'

    band = runs[:lines]
    for s, e in band:
        if e - s + 1 > MAX_TITLE_LINE:
            return None, im, (f'top ink run rows {s}-{e} is '
                              f'{e - s + 1}px tall, taller than a title line '
                              f'({MAX_TITLE_LINE}px) -- layout changed, not '
                              f'cropping')

    # The inked extent of the title, top of the first line to bottom of the
    # last. This is what must look like a title; the gap below it is layout.
    title_ink = band[-1][1] - band[0][0] + 1
    if title_ink > MAX_TITLE_INK:
        return None, im, (f'title ink spans {title_ink}px, over the '
                          f'{MAX_TITLE_INK}px limit -- layout changed, not '
                          f'cropping')

    # Cut from the top of the title to just above the first kept run, leaving
    # that run the same top margin the title had, so the figure keeps a margin
    # rather than starting hard against the panel.
    pad = band[0][0]
    cut = max(0, runs[lines][0] - pad)
    return cut, im, None


def plan_erase(path, lines, expect_h):
    """Row span to paint out, or None with a reason."""
    im = Image.open(path)
    if im.size[1] != expect_h:
        return None, im, (f'height {im.size[1]}px, not the {expect_h}px of a '
                          f'titled figure -- already stripped, or regenerated '
                          f'with a new layout')
    runs = ink_runs(im.convert('L'))
    if len(runs) <= lines:
        return None, im, 'no separable title band (already stripped?)'
    band = runs[:lines]
    for s, e in band:
        if e - s + 1 > MAX_TITLE_LINE:
            return None, im, (f'top ink run rows {s}-{e} is {e - s + 1}px '
                              f'tall, taller than a title line -- layout '
                              f'changed, not erasing')

    # Erasing does not change the image height, so the height fingerprint that
    # protects the cropped figures cannot detect a second run here. Use the
    # position instead: while the title is present the first ink starts near
    # the top of the image. Once erased, the first ink is the panel titles,
    # which sit lower. Refusing when the band starts below TITLE_STARTS_BY is
    # what stops a re-run from painting out the panel titles.
    if band[0][0] > TITLE_STARTS_BY:
        return None, im, (f'first ink at row {band[0][0]}, below the '
                          f'{TITLE_STARTS_BY}px a suptitle starts at -- '
                          f'already erased')
    return (band[0][0], band[-1][1]), im, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true',
                    help='report without writing; exit 1 if any title remains')
    args = ap.parse_args()

    changed, skipped = [], []

    for rel, lines, expect_h in TARGETS:
        path = REPO / rel
        if not path.exists():
            skipped.append((rel, 'missing on disk'))
            continue
        cut, im, why = plan(path, lines, expect_h)
        if cut is None:
            skipped.append((rel, why))
            continue
        w, h = im.size
        changed.append(('crop', rel, f'{cut}px band, {w}x{h} -> {w}x{h - cut}'))
        if not args.check:
            im.crop((0, cut, w, h)).save(path)

    for rel, lines, expect_h in ERASE:
        path = REPO / rel
        if not path.exists():
            skipped.append((rel, 'missing on disk'))
            continue
        span, im, why = plan_erase(path, lines, expect_h)
        if span is None:
            skipped.append((rel, why))
            continue
        top, bot = span
        changed.append(('erase', rel, f'rows {top}-{bot} painted out'))
        if not args.check:
            rgb = im.convert('RGB')
            # Sample the page background from a margin row above the title.
            bg = rgb.getpixel((2, max(0, top - 4)))
            a = np.asarray(rgb).copy()
            a[top:bot + 1, :, :] = bg
            Image.fromarray(a).save(path)

    verb = 'would strip' if args.check else 'stripped'
    for how, rel, detail in changed:
        print(f'  {verb} [{how:5s}] {detail:34s} {rel}')
    for rel, why in skipped:
        print(f'  skipped                                    {rel}  ({why})')

    print()
    print(f'{len(changed)} {verb}, {len(skipped)} skipped')
    if args.check and changed:
        print('FAIL: figures still carry a rendered title band')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
