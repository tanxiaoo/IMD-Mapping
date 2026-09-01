"""Redraw two cited notebook-01b figures with their duplicating suptitles removed.

The report caption carries the description, so the top-level suptitle in
`fig07_holdout_scatter.png` and `figC_perclass_GEE_RF.png` only repeats it and
exposes internal run tags (`[S2]`) and estimator keys (`GEE_RF`). Per-panel
subplot titles are kept -- they label the panels and are not duplication.

Fixing this at source would mean re-executing notebook 01b, which CLAUDE.md
forbids for a labelling change: it re-tunes RF and SVR, re-exports a raster to
Earth Engine, and overwrites the CSVs `collect_metrics.py` builds FACTS.md from.
So these are redrawn from the CSVs the notebook already wrote, following the
same rule already used for `fig_cv_inflation` (F3) and
`fig_milan_raster_comparison` (F15).

The plotted values are the notebook's. Panel geometry, colours, limits, marker
sizes and annotation boxes are copied verbatim from cells 39 and 45; only the
suptitle is dropped. Figures are rewritten at their existing paths, so
`report.md`, `data/FIGURES.md` and `report/OUTLINE.md` keep working unchanged.

The residuals CSV carries a third estimator that is out of scope for this
report. Only the RF and SVR columns are read.

Usage:  python code/redraw_notebook_figs.py [run_dir]
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── Notebook 01b cell 4, verbatim ────────────────────────────────────────────
plt.rcParams.update({
    'figure.dpi': 130, 'font.size': 10,
    'axes.titlesize': 11, 'axes.labelsize': 10,
    'axes.spines.top': False, 'axes.spines.right': False,
})
CLASS_COLORS = ['#2166ac', '#74add1', '#abd9e9', '#fee090',
                '#f46d43', '#d73027', '#a50026']
MODEL_COLORS = {'RF': '#2ecc71', 'SVR': '#3498db'}

REPO = Path(__file__).resolve().parent.parent
DEFAULT_RUN = REPO / 'outputs_S2_percentile_p10p25p50p75p90'

# The panels are named GEE_RF / GEE_SVR while MODEL_COLORS is keyed RF / SVR, so
# the notebook's `.get(name, '#7f8c8d')` falls through to grey for both. Kept.
PANEL_FALLBACK = '#7f8c8d'


def redraw_fig07(run_dir: Path) -> Path:
    """Figure 7 -- holdout scatter, from holdout_residuals.csv + holdout_test_metrics.csv."""
    res = pd.read_csv(run_dir / 'holdout_residuals.csv')
    met = pd.read_csv(run_dir / 'holdout_test_metrics.csv').set_index('Model')

    panels = ['GEE_RF', 'GEE_SVR']          # excluded estimator's column not read
    fig, axes = plt.subplots(1, len(panels), figsize=(5 * len(panels), 5))

    for ax, name in zip(axes, panels):
        pred_col = 'pred_' + name.replace('GEE_', '')
        yt = res['IMD'].to_numpy(dtype=float)
        yp = res[pred_col].to_numpy(dtype=float)
        keep = ~(np.isnan(yt) | np.isnan(yp))
        yt, yp = yt[keep], yp[keep]

        m = met.loc[name]
        color = MODEL_COLORS.get(name, PANEL_FALLBACK)

        ax.scatter(yt, yp, c=color, s=8, alpha=0.4, linewidths=0)
        ax.plot([0, 100], [0, 100], 'k--', lw=1.5)
        ax.set_xlim(-5, 105); ax.set_ylim(-5, 105)
        ax.set_xlabel('Observed IMD (%)'); ax.set_ylabel('Predicted IMD (%)')
        ax.set_title(name, fontweight='bold', color=color)
        ax.text(0.05, 0.95,
                f'RMSE={m["RMSE"]:.2f}%\nMAE={m["MAE"]:.2f}%\n'
                f'R2={m["R2"]:.3f}\nBias={m["Bias"]:+.2f}%',
                transform=ax.transAxes, va='top', fontsize=9,
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white', alpha=0.8))
        ax.set_aspect('equal')
        print(f'  {name}: n={len(yt)}  RMSE={m["RMSE"]}  MAE={m["MAE"]}  '
              f'R2={m["R2"]}  Bias={m["Bias"]}')

    # No suptitle: the report caption carries the description.
    plt.tight_layout()
    out = run_dir / 'fig07_holdout_scatter.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


def redraw_figC(run_dir: Path, name: str = 'GEE_RF') -> Path:
    """Figure C -- per-class accuracy, from perclass_metrics_<name>.csv."""
    cls_df = pd.read_csv(run_dir / f'perclass_metrics_{name}.csv')

    fig, axes_c = plt.subplots(1, 3, figsize=(16, 5))
    for ax, metric, ylabel in zip(axes_c, ['RMSE', 'MAE', 'Bias'],
                                  ['RMSE (%)', 'MAE (%)', 'Bias (obs-pred) %']):
        colors_c = [CLASS_COLORS[c] for c in cls_df['Class']]
        bars = ax.bar(cls_df['Class'], cls_df[metric],
                      color=colors_c, edgecolor='white', lw=0.5)
        if metric == 'Bias':
            ax.axhline(0, color='black', lw=1, ls='--')
        for bar, val in zip(bars, cls_df[metric]):
            ypos = bar.get_height() + (0.1 if val >= 0 else -0.5)
            ax.text(bar.get_x() + bar.get_width() / 2, ypos, f'{val:.1f}',
                    ha='center', va='bottom', fontsize=8)
        ax.set_xticks(cls_df['Class'])
        ax.set_xticklabels([f'C{c}' for c in cls_df['Class']])
        ax.set_xlabel('IMD Class'); ax.set_ylabel(ylabel)
        ax.set_title(f'{metric} per Class', fontweight='bold')
        print(f'  {metric}: ' + '  '.join(
            f'C{c}={v}' for c, v in zip(cls_df['Class'], cls_df[metric])))

    # No suptitle: the report caption carries the description.
    plt.tight_layout()
    out = run_dir / f'figC_perclass_{name}.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


def main() -> None:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RUN
    if not run_dir.is_dir():
        raise SystemExit(f'No such run directory: {run_dir}')
    print(f'Run directory: {run_dir}')
    print('Figure 7 (holdout scatter):')
    print(f'  -> {redraw_fig07(run_dir)}')
    print('Figure C (per-class, GEE_RF):')
    print(f'  -> {redraw_figC(run_dir)}')


if __name__ == '__main__':
    main()
