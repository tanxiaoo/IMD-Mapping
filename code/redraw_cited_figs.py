"""Redraw the cited notebook figures whose PNGs predate the figure-title fix.

Commit 9b5c792 ("Separate figure code from figure titles") removed the numbered
suptitles -- `Figure 1 · Reference vs predicted IMD (centre pixel, strict rule)`
and the rest -- from notebooks 01, 01b, 02, 03 and 04. The notebook SOURCE has
been correct ever since. The PNGs on disk were never rebuilt, so eight cited
figures still displayed a title, seven of them with a figure number from the
producing notebook that disagreed with the report's own numbering.

The LaTeX conversion is what made this visible: LaTeX prints its own number
directly beneath an image already showing a different one. `audit_numbers.py`
cannot catch it, because it checks caption-to-image agreement but cannot read a
number inside a PNG.

This script rebuilds those eight from the CSVs and rasters the notebooks already
wrote, exactly as `redraw_notebook_figs.py` does for F4 and F6. Re-executing the
notebooks is what CLAUDE.md forbids for a labelling change: it re-tunes models,
re-exports rasters to Earth Engine and overwrites the CSVs `collect_metrics.py`
builds `FACTS.md` from.

WHAT IS AND IS NOT A TITLE
--------------------------
The rule is not "remove every suptitle". CLAUDE.md permits run-identifying
parameters *where the same filename exists in several run directories and the
plot cannot distinguish them*. So the corrected notebooks legitimately still
emit, and these redraws reproduce:

    F2  fig01_spatial_split       Train: 2449 pts | Test: 1014 pts | Buffer: 250m
    F8  figD_importance_RF        RF · Sentinel-2 (tuning block=1000m)
    F9  fig01_transfer_comparison scored against GHSL (Milan baseline against CLMS)
    F10 fig01_transfer_comparison scored against GHSL (Milan baseline against CLMS)
    F11 fig_obs_vs_pred_hanoi_hcmc AlphaEarth embedding (64 dims)
    F12 fig02_per_class_mae       spatial test set | 1000m blocks, 250m buffer
    F13 fig02_forest_ci           (none)
    F14 fig01_scatter_grid        (none)

F9 and F10 share a filename across `outputs_transfer_v2` and
`outputs_transfer_S2_median`, which is precisely the case the rule allows a
run-identifying line for. What none of them carries is a figure number, a
restatement of the caption, or a conclusion.

Plotted values, panel geometry, colours and annotations are the notebooks'.

Usage:  python code/redraw_cited_figs.py [--only F2,F8,...]
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent

# Notebook cell 4, verbatim -- shared by 01/01b/02/03.
plt.rcParams.update({
    'figure.dpi': 130, 'font.size': 10,
    'axes.titlesize': 11, 'axes.labelsize': 10,
    'axes.spines.top': False, 'axes.spines.right': False,
})
MODEL_COLORS = {'RF': '#2ecc71', 'SVR': '#3498db'}

SPLIT_BLOCK_M = 1000
BUFFER_M = 250


# ── F9 / F10 · transfer comparison (notebook 02/03 cell 13) ──────────────────
def redraw_transfer_comparison(run_dir: Path, suptitle: str) -> Path:
    comp_df = pd.read_csv(run_dir / 'transferability_comparison.csv')

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    axes = axes.ravel()
    scenario_colors = {
        'Milan (baseline)':         '#34495e',
        'A - Milan model transfer': '#e74c3c',
        'B - Local retrain':        '#27ae60',
    }
    for ax, metric, ylabel in zip(axes, ['RMSE', 'MAE', 'R2', 'Bias'],
                                  ['RMSE (%)', 'MAE (%)', 'R2', 'Bias (%)']):
        bar_colors = [scenario_colors[s] for s in comp_df['Scenario']]
        labels = [f'{r["City"]}\n{r["Scenario"].split("-")[0].strip()}'
                  for _, r in comp_df.iterrows()]
        bars = ax.bar(range(len(comp_df)), comp_df[metric],
                      color=bar_colors, edgecolor='white', linewidth=0.5)
        if metric == 'Bias':
            ax.axhline(0, color='black', lw=1, ls='--')
        for bar, val in zip(bars, comp_df[metric]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f'{val:.2f}', ha='center', va='bottom', fontsize=8)
        ax.set_xticks(range(len(comp_df)))
        ax.set_xticklabels(labels, fontsize=8, rotation=20, ha='right')
        ax.set_ylabel(ylabel)
        ax.set_title(metric, fontweight='bold')

    patches = [mpatches.Patch(color=c, label=s)
               for s, c in scenario_colors.items()]
    fig.legend(handles=patches, loc='upper center', bbox_to_anchor=(0.5, 1.02),
               ncol=3, fontsize=10, frameon=False)
    # Names the reference, not the finding: every bar here is scored against
    # GHSL, so a bias bar near zero means agreement with GHSL and not accuracy.
    fig.suptitle(suptitle, fontsize=11, fontweight='bold', y=1.05)
    plt.tight_layout()
    out = run_dir / 'fig01_transfer_comparison.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


# ── F12 · per-class MAE (notebook 02 cell 17) ────────────────────────────────
def redraw_per_class_mae(run_dir: Path) -> Path:
    per_cls_df = pd.read_csv(run_dir / 'per_class_metrics.csv')
    cities = list(dict.fromkeys(per_cls_df['City']))

    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    for ax, city_name in zip(axes, cities):
        sub = per_cls_df[per_cls_df['City'] == city_name]
        classes = sorted(sub['Class'].unique())
        x_pos = np.array(classes, dtype=float)
        width = 0.4

        def mae_for(scen):
            out = []
            for c in classes:
                v = sub[(sub['Class'] == c) &
                        (sub['Scenario'] == scen)]['MAE'].values
                out.append(v[0] if len(v) else 0)
            return out

        ax.bar(x_pos - width / 2, mae_for('Milan model transfer'), width,
               color='#e74c3c', label='Milan model transfer', edgecolor='white')
        ax.bar(x_pos + width / 2, mae_for('Local'), width,
               color='#27ae60', label='Local retrain', edgecolor='white')
        ax.set_xticks(x_pos)
        ax.set_xticklabels([f'C{c}' for c in classes])
        ax.set_xlabel('IMD Class')
        ax.set_ylabel('MAE (%)')
        ax.set_title(f'{city_name} -- MAE per Class', fontweight='bold')
        ax.legend(fontsize=9)

    fig.suptitle(f'spatial test set | {SPLIT_BLOCK_M}m blocks, '
                 f'{BUFFER_M}m buffer', fontsize=10, y=1.02)
    plt.tight_layout()
    out = run_dir / 'fig02_per_class_mae.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


# ── F8 · band importance (notebook 01b cell 47) ──────────────────────────────
def redraw_importance(run_dir: Path, block: str = '1000m') -> Path:
    imp_df = pd.read_csv(run_dir / 'feature_importance_RF.csv')
    # The CSV is already sorted by permutation importance, which is the order
    # cell 47's `sort_idx` produces.
    bands = imp_df['band'].tolist()

    fig, axes_d = plt.subplots(1, 2, figsize=(16, 5))

    ax = axes_d[0]
    imp = imp_df['impurity_importance'].to_numpy()
    ax.bar(range(len(bands)), imp,
           color=plt.cm.viridis(imp / imp.max()), edgecolor='none')
    ax.set_xticks(range(len(bands)))
    ax.set_xticklabels(bands, rotation=90, fontsize=7)
    ax.set_ylabel('Mean Decrease Impurity')
    ax.set_title('RF Impurity Importance', fontweight='bold')

    ax = axes_d[1]
    n_top = min(20, len(bands))
    perm = imp_df['perm_importance'].to_numpy()[:n_top]
    perr = imp_df['perm_std'].to_numpy()[:n_top]
    ax.barh(range(n_top), perm[::-1], xerr=perr[::-1],
            color=MODEL_COLORS['RF'], alpha=0.85, edgecolor='none',
            error_kw={'linewidth': 0.8, 'color': 'black'})
    ax.set_yticks(range(n_top))
    ax.set_yticklabels(bands[:n_top][::-1], fontsize=8)
    ax.set_xlabel('Mean accuracy decrease (RMSE units)')
    ttl = 'All bands' if n_top == len(bands) else f'Top {n_top}'
    ax.set_title(f'Permutation Importance -- {ttl} (RF)', fontweight='bold')

    # Run-identifying: figD_importance_RF.png exists in four run directories and
    # the panels cannot tell them apart. Names the run, not the finding.
    fig.suptitle(f'RF · Sentinel-2 (tuning block={block})',
                 fontsize=13, fontweight='bold', y=1.01)
    plt.tight_layout()
    out = run_dir / 'figD_importance_RF.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


# ── F2 · spatial split (notebook 01 cell 12) ─────────────────────────────────
def redraw_spatial_split() -> Path:
    import geopandas as gpd

    run_dir = REPO / 'outputs_v2'
    gdf_all = gpd.read_file(REPO / 'outputs_sampling' / 'sample_points_all.gpkg')
    gdf_train = gpd.read_file(run_dir / 'spatial_train_pts.gpkg')
    gdf_test = gpd.read_file(run_dir / 'spatial_test_pts.gpkg')

    # The buffer-removed points are not saved on their own. They are exactly
    # what the split discarded: everything in the 3 500-point sample that is
    # neither kept-train nor kept-test. Recovering them by set difference on
    # rounded coordinates reproduces cell 12's `removed_coords` without
    # re-running the split.
    def xy(g):
        return np.column_stack([g.geometry.x.to_numpy(), g.geometry.y.to_numpy()])

    def keys(arr):
        return {(round(x, 9), round(y, 9)) for x, y in arr}

    c_all, c_tr, c_te = xy(gdf_all), xy(gdf_train), xy(gdf_test)
    kept = keys(c_tr) | keys(c_te)
    removed_coords = np.array([p for p in c_all
                               if (round(p[0], 9), round(p[1], 9)) not in kept])

    n_classes = int(gdf_all['IMD_class'].max()) + 1
    fold_colors_tt = {'train': '#3498db', 'test': '#e74c3c',
                      'removed': '#95a5a6'}

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    ax = axes[0]
    ax.scatter(c_tr[:, 0], c_tr[:, 1], c=fold_colors_tt['train'], s=5,
               alpha=0.5, linewidths=0, label=f'Train (n={len(gdf_train)})')
    ax.scatter(c_te[:, 0], c_te[:, 1], c=fold_colors_tt['test'], s=8,
               alpha=0.7, linewidths=0, label=f'Test (n={len(gdf_test)})')
    if len(removed_coords):
        ax.scatter(removed_coords[:, 0], removed_coords[:, 1],
                   c=fold_colors_tt['removed'], s=6, alpha=0.5, marker='x',
                   label=f'Removed by buffer (n={len(removed_coords)})')

    # The grid is drawn in the projected CRS the split was computed in; the
    # saved points are geographic, so the block size is converted to degrees
    # at this latitude rather than applied to lon/lat directly.
    x0, x1 = c_all[:, 0].min(), c_all[:, 0].max()
    y0, y1 = c_all[:, 1].min(), c_all[:, 1].max()
    deg_y = SPLIT_BLOCK_M / 111_320.0
    deg_x = SPLIT_BLOCK_M / (111_320.0 * np.cos(np.deg2rad((y0 + y1) / 2)))
    for x in np.arange(x0 // deg_x * deg_x, x1 + deg_x, deg_x):
        ax.axvline(x, color='grey', lw=0.3, alpha=0.4)
    for yv in np.arange(y0 // deg_y * deg_y, y1 + deg_y, deg_y):
        ax.axhline(yv, color='grey', lw=0.3, alpha=0.4)

    ax.set_title(f'Spatial Train/Test Split ({SPLIT_BLOCK_M}m blocks)',
                 fontweight='bold')
    ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
    ax.set_aspect('equal')
    ax.legend(fontsize=9)

    ax = axes[1]
    x_cls = np.arange(n_classes)
    w = 0.35
    train_counts = [int((gdf_train['IMD_class'] == c).sum())
                    for c in range(n_classes)]
    test_counts = [int((gdf_test['IMD_class'] == c).sum())
                   for c in range(n_classes)]
    ax.bar(x_cls - w / 2, train_counts, w, color=fold_colors_tt['train'],
           alpha=0.85, label='Train')
    ax.bar(x_cls + w / 2, test_counts, w, color=fold_colors_tt['test'],
           alpha=0.85, label='Test')
    ax.set_xticks(x_cls)
    ax.set_xticklabels([f'C{c}' for c in range(n_classes)])
    ax.set_xlabel('IMD Class'); ax.set_ylabel('Point count')
    ax.set_title('Class Distribution — Train vs Test', fontweight='bold')
    ax.legend(fontsize=9)

    fig.suptitle(f'Train: {len(gdf_train)} pts | Test: {len(gdf_test)} pts | '
                 f'Buffer: {BUFFER_M}m', fontsize=10, y=1.01)
    plt.tight_layout()
    out = run_dir / 'fig01_spatial_split.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


# ── F11 · observed/transfer/retrain rasters (notebook 02 cell 23) ────────────
def redraw_obs_vs_pred() -> Path:
    import matplotlib.ticker as mticker
    import rioxarray as rxr
    from matplotlib.colors import ListedColormap

    run_dir = REPO / 'outputs_transfer_v2'
    comp = pd.read_csv(run_dir / 'transferability_comparison.csv')

    # Notebook 02 cell 3.
    IMD_PALETTE = ['#1a9641', '#a6d96a', '#ffffbf', '#fdae61', '#d7191c']
    DISPLAY_SCALE = 5
    imd_cmap = ListedColormap(IMD_PALETTE)
    SCENARIOS = [('zeroshot', 'Milan transfer', 'A - Milan model transfer'),
                 ('localrf', 'Local retrain', 'B - Local retrain')]
    # The notebook config points at ./data/; the rasters live at the repo root.
    CITIES = {'Hanoi': REPO / 'IMD_2018_Hanoi.tif',
              'HCMC': REPO / 'IMD_2018_HCMC.tif'}

    def imshow_aspect(ax, da, **kw):
        b = da.rio.bounds()
        im = ax.imshow(da.values, extent=(b[0], b[2], b[1], b[3]), **kw)
        ax.set_aspect('equal')
        ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=4))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4))
        ax.tick_params(axis='both', labelsize=8)
        ax.set_xlabel('Easting [m]', fontsize=9)
        ax.set_ylabel('Northing [m]', fontsize=9)
        return im

    fig, axes = plt.subplots(len(CITIES), 3, figsize=(18, 6 * len(CITIES)),
                             gridspec_kw={'wspace': 0.20, 'hspace': 0.25})
    axes = np.atleast_2d(axes)
    im = None

    for row, (city, ghsl_path) in enumerate(CITIES.items()):
        preds = {}
        for tag, _, _ in SCENARIOS:
            p = run_dir / f'IMD_{city}_10m_{tag}.tif'
            if not p.exists():
                raise FileNotFoundError(f'{p} -- the GEE export is missing.')
            preds[tag] = rxr.open_rasterio(p, masked=True).squeeze('band',
                                                                   drop=True)
        ref = preds['localrf']
        ghsl = rxr.open_rasterio(ghsl_path, masked=True).squeeze('band',
                                                                drop=True)
        if ghsl.rio.crs != ref.rio.crs:
            ghsl = ghsl.rio.reproject(ref.rio.crs)
        ghsl = ghsl.rio.clip_box(*ref.rio.bounds()).rio.reproject_match(ref)
        # Water comes from the prediction's own NaN mask, as in the notebook.
        ghsl = ghsl.where(~np.isnan(ref))

        im = imshow_aspect(axes[row, 0],
                           ghsl[::DISPLAY_SCALE, ::DISPLAY_SCALE],
                           cmap=imd_cmap, vmin=0, vmax=100)
        axes[row, 0].set_title(f'{city} — GHSL observed', fontweight='bold',
                               fontsize=12)

        for col, (tag, label, scen) in enumerate(SCENARIOS, start=1):
            m = comp[(comp['City'] == city) &
                     (comp['Scenario'] == scen)].iloc[0]
            im = imshow_aspect(axes[row, col],
                               preds[tag][::DISPLAY_SCALE, ::DISPLAY_SCALE],
                               cmap=imd_cmap, vmin=0, vmax=100)
            axes[row, col].set_title(
                f'{city} — {label}\n'
                f'RMSE={m["RMSE"]:.1f}  R2={m["R2"]:.2f}  '
                f'Bias={m["Bias"]:+.1f}',
                fontweight='bold', fontsize=12)

    fig.colorbar(im, ax=axes, orientation='vertical', fraction=0.02, pad=0.03,
                 label='IMD (%)')
    # Run-identifying: the same panel layout is produced for the S2 median run.
    fig.suptitle('AlphaEarth embedding (64 dims)', fontsize=14,
                 fontweight='bold', y=0.94)
    out = run_dir / 'fig_obs_vs_pred_hanoi_hcmc.png'
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return out


REDRAWS = {
    'F2':  redraw_spatial_split,
    'F11': redraw_obs_vs_pred,
    'F9':  lambda: redraw_transfer_comparison(
        REPO / 'outputs_transfer_v2',
        'scored against GHSL (Milan baseline against CLMS)'),
    'F10': lambda: redraw_transfer_comparison(
        REPO / 'outputs_transfer_S2_median',
        'scored against GHSL (Milan baseline against CLMS)'),
    'F12': lambda: redraw_per_class_mae(REPO / 'outputs_transfer_v2'),
    'F8':  lambda: redraw_importance(
        REPO / 'outputs_S2_percentile_p10p25p50p75p90'),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only', default=None,
                    help='comma-separated figure ids, e.g. F8,F9')
    args = ap.parse_args()

    want = ([s.strip().upper() for s in args.only.split(',')]
            if args.only else list(REDRAWS))
    unknown = [w for w in want if w not in REDRAWS]
    if unknown:
        raise SystemExit(f'Unknown figure id(s): {", ".join(unknown)}. '
                         f'Known: {", ".join(REDRAWS)}')

    for fid in want:
        print(f'{fid}:')
        print(f'  -> {REDRAWS[fid]()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
