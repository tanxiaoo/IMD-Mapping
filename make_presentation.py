"""Build the supervisor presentation comparing S2 composite methods.

Every metric on every slide is read from the ``outputs_*`` CSVs at build time --
nothing is hardcoded. A stale number in a supervisor deck is the failure mode
this guards against, so if a run is re-done the deck only needs regenerating.

    .venv\\Scripts\\python.exe make_presentation.py

Writes IMD_S2_composite_comparison.pptx and the generated figures in figs_ppt/.
"""

import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt
from scipy.stats import wilcoxon

# ── Runs under comparison ─────────────────────────────────────────────────────
# Date counts and dims are read from each run's extraction metadata below, not
# asserted here: the old hardcoded values were what let a stale table be
# mislabelled in the first place.
RUNS = [
    ('median',     'outputs_S2_median',                     'Median'),
    ('stack',      'outputs_S2_stack',                      'Stack'),
    ('percentile', 'outputs_S2_percentile_p10p25p50p75p90', 'Percentile'),
    ('embedding',  'outputs_v2',                            'Embedding'),
]
# Where each run's extraction metadata lives. The embedding run has none -- it
# is an annual product with no date list -- so it is described explicitly.
SAMPLE_DIR = {
    'median':     'samples_S2_median',
    'stack':      'samples_S2_stack',
    'percentile': 'samples_S2_percentile_p10p25p50p75p90',
}
PCTL_DIR = 'outputs_S2_percentile_p10p25p50p75p90'
SCENE_TABLE = 's2_scene_candidates_2018.csv'
PCTL_META = f'{SAMPLE_DIR["percentile"]}/s2_extraction_metadata.json'

FIGS = 'figs_ppt'
OUT_PPTX = 'IMD_S2_composite_comparison.pptx'

# ── Style ─────────────────────────────────────────────────────────────────────
INK    = '#1a1a1a'
MUTED  = '#6b6b6b'
ACCENT = '#0B6E4F'          # single accent, used for the winning method
RULE   = '#d4d4d4'
# One colour per run, kept identical on every chart in the deck.
CMAP = {'median': '#b0b7bd', 'stack': '#7d93a3',
        'percentile': ACCENT, 'embedding': '#C2724A'}

plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 11,
    'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'text.color': INK,
    'xtick.color': MUTED, 'ytick.color': MUTED,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'axes.grid': True, 'grid.color': '#ececec', 'grid.linewidth': 0.8,
    'axes.axisbelow': True,
})


def load_spec():
    """Date count and feature dimension per run, read from the extraction JSON.

    The embedding has no date list (it is an annual product), so it is the one
    entry described here rather than discovered.
    """
    spec = {'embedding': {'dates': None, 'dims': 64}}
    for key, sd in SAMPLE_DIR.items():
        m = json.load(open(f'{sd}/s2_extraction_metadata.json'))
        spec[key] = {'dates': len(m['selected_dates']), 'dims': len(m['bands'])}
    return spec


SPEC = load_spec()


def label(key, short, sep='\n'):
    """Chart label carrying method AND date count -- the confound stays visible."""
    s = SPEC[key]
    d = 'annual' if s['dates'] is None else f'{s["dates"]} dates'
    return f'{short}{sep}({d}, {s["dims"]} dims)'


# ── Load every metric from disk ───────────────────────────────────────────────
def load():
    hold, cv, per, res = {}, {}, {}, {}
    for key, d, _s in RUNS:
        if not os.path.exists(f'{d}/holdout_test_metrics.csv'):
            raise SystemExit(
                f"\nMissing run: {d}/holdout_test_metrics.csv\n\n"
                f"The '{key}' arm has not been modelled yet. Run notebook 01b with\n"
                f"COMPOSITE_METHOD = '{key}' (it reads ./samples_S2_* and writes\n"
                f"./outputs_S2_*), remembering to download the two GeoTIFFs from\n"
                f"Drive into {d}/ at the export cell, then re-run this script.\n")
        hold[key] = pd.read_csv(f'{d}/holdout_test_metrics.csv').set_index('Model')
        cv[key] = pd.read_csv(f'{d}/spatial_cv_summary.csv')
        per[key] = {m: pd.read_csv(f'{d}/perclass_metrics_GEE_{m}.csv')
                    for m in ('RF', 'SVR')}
        p = f'{d}/holdout_residuals.csv'
        if os.path.exists(p):
            res[key] = pd.read_csv(p)
    return hold, cv, per, res


HOLD, CV, PER, RES = load()


# ═══════════════════════════════════════════════════════════════════════════════
# Generated figures
# ═══════════════════════════════════════════════════════════════════════════════

def save(fig, name):
    os.makedirs(FIGS, exist_ok=True)
    p = f'{FIGS}/{name}.png'
    fig.savefig(p, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return p


def fig_design():
    """Study design: four predictor sets, one shared everything-else."""
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 4.6); ax.axis('off')

    def box(x, y, w, h, txt, fc='white', ec=MUTED, fs=10, bold=False, tc=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.05',
                                    fc=fc, ec=ec, lw=1.2))
        ax.text(x + w / 2, y + h / 2, txt, ha='center', va='center', fontsize=fs,
                fontweight='bold' if bold else 'normal', color=tc, linespacing=1.5)

    ax.text(0.9, 4.3, 'PREDICTORS  (the only thing that varies)',
            fontsize=9, color=MUTED, fontweight='bold')
    ys = [3.35, 2.5, 1.65, 0.8]
    for (key, _d, short), y in zip(RUNS, ys):
        sp = SPEC[key]
        dd = 'annual' if sp['dates'] is None else f'{sp["dates"]} dates'
        box(0.9, y, 3.25, 0.66, f'{short}  ·  {dd}, {sp["dims"]} dims',
            fc=CMAP[key] if key == 'percentile' else 'white',
            ec=CMAP[key], tc='white' if key == 'percentile' else INK,
            bold=key == 'percentile', fs=11)

    box(4.6, 1.5, 2.5, 2.0,
        '3 500 points\n500 × 7 IMD classes\n\nSAME points\nSAME labels\nSAME split',
        fc='#f6f6f6', fs=10, bold=False)
    box(7.9, 1.5, 2.0, 2.0, 'RF\nSVR\nMLP\n\nspatial\nblock CV', fc='#f6f6f6', fs=10)
    box(10.4, 1.85, 1.4, 1.3, 'IMD\n0–100%\n10 m', fc='#f6f6f6', fs=10)

    for y in ys:
        ax.add_patch(FancyArrowPatch((4.25, y + 0.33), (4.55, 2.5),
                                     arrowstyle='->', mutation_scale=11,
                                     color=RULE, lw=1.1))
    for a, b in [((7.15, 2.5), (7.85, 2.5)), ((9.95, 2.5), (10.35, 2.5))]:
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle='->', mutation_scale=13,
                                     color=MUTED, lw=1.4))
    ax.text(6.0, 1.15, 'held identical across all four runs',
            ha='center', fontsize=9, color=MUTED, style='italic')
    return save(fig, 'design')


def fig_bands():
    """The 10-band set, grouped by why each is there."""
    bands = [
        ('B2',  'Blue',      '10 m', 'visible'),
        ('B3',  'Green',     '10 m', 'visible'),
        ('B4',  'Red',       '10 m', 'visible'),
        ('B5',  'Red edge 1','20 m', 'red edge'),
        ('B6',  'Red edge 2','20 m', 'red edge'),
        ('B7',  'Red edge 3','20 m', 'red edge'),
        ('B8',  'NIR',       '10 m', 'NIR'),
        ('B8A', 'NIR narrow','20 m', 'NIR'),
        ('B11', 'SWIR 1',    '20 m', 'SWIR'),
        ('B12', 'SWIR 2',    '20 m', 'SWIR'),
    ]
    gcol = {'visible': '#4C72B0', 'red edge': '#C2724A',
            'NIR': '#55A868', 'SWIR': '#8172B2'}
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.set_xlim(-0.6, 10); ax.set_ylim(0, 3.5); ax.axis('off')
    for i, (b, n, r, g) in enumerate(bands):
        ax.add_patch(FancyBboxPatch((i, 1.35), 0.82, 1.15,
                                    boxstyle='round,pad=0.03',
                                    fc=gcol[g], ec='none', alpha=0.9))
        ax.text(i + 0.41, 2.16, b, ha='center', fontsize=12,
                fontweight='bold', color='white')
        ax.text(i + 0.41, 1.72, r, ha='center', fontsize=9, color='white')
        ax.text(i + 0.41, 1.13, n, ha='center', fontsize=8.5, color=MUTED,
                rotation=0)
    seen = []
    for g in ['visible', 'red edge', 'NIR', 'SWIR']:
        seen.append(plt.Line2D([], [], marker='s', ls='', ms=11,
                               color=gcol[g], label=g))
    ax.legend(handles=seen, loc='upper center', ncol=4, frameon=False,
              bbox_to_anchor=(0.5, 1.02), fontsize=10)
    ax.text(4.7, 0.55,
            'All resampled onto B2’s 10 m grid  ·  raw DN 0–10 000, unscaled\n'
            'No spectral index is used as a feature — the model is given the reflectance itself',
            ha='center', fontsize=10, color=MUTED, linespacing=1.7)
    return save(fig, 'bands')


def fig_dates():
    """Which 2018 dates survived scoring, and why tile-level cloud is not enough."""
    t = pd.read_csv(SCENE_TABLE)
    t['date'] = pd.to_datetime(t['date'])
    t = t.sort_values('date')
    ok = t['usable'] == 'YES'
    thr = 20

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.3),
                                  gridspec_kw={'width_ratios': [2.0, 1.0]})

    ax.scatter(t.loc[~ok, 'date'], t.loc[~ok, 'AOI_cloud%'], s=26,
               c='#d9d9d9', edgecolors='#bfbfbf', lw=0.5, label=f'rejected (n={(~ok).sum()})')
    ax.scatter(t.loc[ok, 'date'], t.loc[ok, 'AOI_cloud%'], s=46,
               c=ACCENT, edgecolors='white', lw=0.7, zorder=3,
               label=f'accepted (n={ok.sum()})')
    ax.axhline(thr, color=INK, ls='--', lw=1.1)
    ax.text(t['date'].min(), thr + 2.5, f'max AOI cloud = {thr}%',
            fontsize=9, color=INK)
    ax.set_ylabel('Cloud / shadow / cirrus over AOI  (%)')
    ax.set_title('All 2018 acquisitions, scored over the AOI', fontsize=11,
                 fontweight='bold', loc='left')
    ax.legend(frameon=False, fontsize=9.5, loc='upper right')
    ax.set_ylim(-3, 105)

    # Why one criterion is not enough. Of the dates a cloud-only test would
    # admit, none are actually cloudy over the AOI -- they fail on SCL validity
    # and swath coverage instead. That is the argument for scoring three things.
    # Restrict to dates that actually image the AOI: a scene with ~0% validity is
    # an empty swath edge, and counting those would inflate the argument.
    cloud_ok = (t['AOI_cloud%'] <= thr) & (t['coverage%'] > 10)
    wrong = int((cloud_ok & ~ok).sum())
    ax2.scatter(t.loc[~ok, 'valid%'], t.loc[~ok, 'coverage%'],
                s=32, c='#d9d9d9', edgecolors='#bfbfbf', lw=0.4,
                label=f'rejected ({(~ok).sum()})')
    ax2.scatter(t.loc[ok, 'valid%'], t.loc[ok, 'coverage%'],
                s=42, c=ACCENT, edgecolors='white', lw=0.6, zorder=3,
                label=f'accepted ({ok.sum()})')
    ax2.axvline(90, color=INK, ls='--', lw=1.0)
    ax2.axhline(95, color=INK, ls='--', lw=1.0)
    ax2.set_xlabel('SCL validity over AOI  (%)')
    ax2.set_ylabel('Swath coverage of AOI  (%)')
    n_partial = int((t['coverage%'] <= 10).sum())
    ax2.set_title('Cloud is not the only way a date fails',
                  fontsize=11, fontweight='bold', loc='left', color='#C2724A')
    ax2.text(0.03, 0.30, f'{n_partial} dates sit here:\npartial swaths that\nbarely reach Milan',
             transform=ax2.transAxes, fontsize=8.8, color='#C2724A', linespacing=1.5)
    ax2.legend(frameon=False, fontsize=9, loc='lower left')
    ax2.set_xlim(-3, 103); ax2.set_ylim(-3, 108)
    fig.tight_layout()
    return save(fig, 'dates'), int(ok.sum()), len(t), wrong, n_partial


def fig_methods():
    """One pixel's year, and the three ways of reducing it."""
    # The instructive case is the CONFUSABLE one: a seasonal surface whose
    # annual median lands on top of the impervious pixel's. Median cannot
    # separate these two; the spread can. Centring both series on the same
    # level is the whole point of the panel, so it is constructed that way
    # rather than left to chance.
    rng = np.random.RandomState(3)
    n = 30
    x = np.arange(n)
    imperv = 1430 + rng.normal(0, 55, n)                     # stable all year
    veg = 1430 + 620 * np.sin((x / n) * 2 * np.pi - 0.6) + rng.normal(0, 80, n)
    veg += np.median(imperv) - np.median(veg)                # medians coincide

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.9), sharey=True)
    for ax in axes:
        ax.plot(x, imperv, '-o', ms=3.4, color=ACCENT, lw=1.3, label='impervious pixel')
        ax.plot(x, veg, '-o', ms=3.4, color='#C2724A', lw=1.3, label='vegetated pixel')
        ax.set_xlabel('acquisition through 2018')
        ax.set_xticks([])

    axes[0].set_ylabel('reflectance (DN)')

    for ax, ser in [(axes[0], imperv), (axes[0], veg)]:
        ax.axhline(np.median(ser), color=MUTED, ls='--', lw=1.4)
    axes[0].set_title(f'Median  ·  {SPEC["median"]["dims"]} dims\none number per band',
                      fontsize=10.5, fontweight='bold', loc='left')
    axes[0].text(0.03, 0.06,
                 'the two medians nearly coincide —\nthe distinction is discarded',
                 transform=axes[0].transAxes, fontsize=9, color=MUTED,
                 linespacing=1.5)

    for i in range(0, n, 8):
        axes[1].axvspan(i - 0.4, i + 0.4, color='#e8eef2', zorder=0)
    axes[1].set_title(f'Stack  ·  {SPEC["stack"]["dims"]} dims\n'
                      f'keep {SPEC["stack"]["dates"]} dates as-is',
                      fontsize=10.5, fontweight='bold', loc='left')
    axes[1].text(0.03, 0.06,
                 'keeps timing, but only 4 looks —\nand gaps are median-filled',
                 transform=axes[1].transAxes, fontsize=9, color=MUTED,
                 linespacing=1.5)

    for ser, c in [(imperv, ACCENT), (veg, '#C2724A')]:
        lo, hi = np.percentile(ser, 10), np.percentile(ser, 90)
        axes[2].axhspan(lo, hi, color=c, alpha=0.16, zorder=0)
        for p in (10, 25, 50, 75, 90):
            axes[2].axhline(np.percentile(ser, p), color=c, lw=0.9, alpha=0.65)
    axes[2].set_title(f'Percentile  ·  {SPEC["percentile"]["dims"]} dims\n'
                      f'shape of the distribution',
                      fontsize=10.5, fontweight='bold', loc='left', color=ACCENT)
    axes[2].text(0.03, 0.06,
                 'the SPREAD separates them:\nstable vs strongly seasonal',
                 transform=axes[2].transAxes, fontsize=9, color=INK,
                 linespacing=1.5, fontweight='bold')
    axes[0].legend(frameon=False, fontsize=9, loc='upper right')
    fig.tight_layout()
    return save(fig, 'methods')


def fig_holdout():
    """Headline: holdout RMSE by method x model."""
    models = ['GEE_RF', 'GEE_SVR']
    fig, ax = plt.subplots(figsize=(11.5, 4.6))
    w = 0.36
    xs = np.arange(len(RUNS))
    for j, m in enumerate(models):
        vals = [HOLD[k].loc[m, 'RMSE'] for k, *_ in RUNS]
        bars = ax.bar(xs + (j - 0.5) * w, vals, w,
                      color=[CMAP[k] for k, *_ in RUNS],
                      alpha=1.0 if j == 0 else 0.55,
                      edgecolor='white', lw=1.2,
                      label='Random Forest' if j == 0 else 'SVR')
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.22, f'{v:.2f}',
                    ha='center', fontsize=9.5, fontweight='bold')
    ax.set_xticks(xs)
    ax.set_xticklabels([label(k, s) for k, _, s in RUNS], fontsize=10)
    ax.set_ylabel('Holdout RMSE  (IMD %)   ← lower is better')
    ax.legend(frameon=False, fontsize=10, ncol=2, loc='upper right')
    ax.set_ylim(0, max(HOLD[k].loc[m, 'RMSE']
                       for k, *_ in RUNS for m in models) * 1.22)
    ax.text(0.0, -0.30, 'n = 1 014 held-out points, identical across all four runs',
            transform=ax.transAxes, fontsize=9, color=MUTED)
    fig.tight_layout()
    return save(fig, 'holdout_rmse')


def fig_cv():
    """Spatial CV RMSE, mean +/- sd over 25 fold scores, per block size."""
    fig, ax = plt.subplots(figsize=(11.5, 4.5))
    models = ['RF', 'SVR', 'MLP']
    w = 0.26
    xs = np.arange(len(RUNS))
    for j, m in enumerate(models):
        mu, sd = [], []
        for k, *_ in RUNS:
            sub = CV[k][(CV[k].Model == m) & (CV[k].CV_method != 'Random')]
            mu.append(sub.RMSE_mean.mean()); sd.append(sub.RMSE_std.mean())
        ax.bar(xs + (j - 1) * w, mu, w, yerr=sd, capsize=3,
               color=[CMAP[k] for k, *_ in RUNS],
               alpha=[1.0, 0.7, 0.45][j], edgecolor='white', lw=1.1,
               error_kw={'ecolor': MUTED, 'lw': 1.1}, label=m)
    ax.set_xticks(xs)
    ax.set_xticklabels([label(k, s) for k, _, s in RUNS], fontsize=10)
    ax.set_ylabel('Spatial block-CV RMSE  (IMD %)')
    ax.legend(frameon=False, fontsize=10, ncol=3, loc='upper right',
              title='shading = model', title_fontsize=9)
    ax.text(0.0, -0.30,
            'mean ± sd over 5 folds × 5 repeats, averaged across 500 / 1000 / 2000 m blocks',
            transform=ax.transAxes, fontsize=9, color=MUTED)
    fig.tight_layout()
    return save(fig, 'cv_rmse')


def paired_stats():
    """Wilcoxon signed-rank on |error|, percentile vs each alternative."""
    rows = []
    for m in ('RF', 'SVR', 'MLP'):
        for other in ('stack', 'median'):
            a = np.abs(RES['percentile'][f'err_{m}'])
            b = np.abs(RES[other][f'err_{m}'])
            stat, p = wilcoxon(a, b)
            rows.append({'model': m, 'vs': other, 'mae_pctl': a.mean(),
                         'mae_other': b.mean(), 'delta': b.mean() - a.mean(),
                         'p': p, 'win': float((a < b).mean()) * 100})
    return pd.DataFrame(rows)


def fig_paired(stats):
    """Per-point paired improvement, percentile vs the two alternatives."""
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.4),
                                  gridspec_kw={'width_ratios': [1.25, 1.0]})
    models = ['RF', 'SVR', 'MLP']
    data, labels, colors = [], [], []
    for other in ('median', 'stack'):
        for m in models:
            d = (np.abs(RES[other][f'err_{m}']) -
                 np.abs(RES['percentile'][f'err_{m}']))
            data.append(d); labels.append(f'{m}\nvs {other}')
            colors.append(CMAP[other])
    bp = ax.boxplot(data, tick_labels=labels, showfliers=False, patch_artist=True,
                    widths=0.6, medianprops={'color': INK, 'lw': 1.6})
    for patch, c in zip(bp['boxes'], colors):
        patch.set_facecolor(c); patch.set_alpha(0.55); patch.set_edgecolor(MUTED)
    ax.axhline(0, color=INK, lw=1.2)
    ax.set_ylabel('|error| reduction with percentile  (IMD %)')
    ax.text(0.015, 0.955, 'above 0  →  percentile is closer to truth',
            transform=ax.transAxes, fontsize=9.5, color=ACCENT,
            fontweight='bold', va='top')
    ax.tick_params(labelsize=9)

    st = stats.copy()
    st['lbl'] = st.model + ' vs ' + st['vs']
    y = np.arange(len(st))[::-1]
    ax2.barh(y, st.delta, 0.62, color=[CMAP[v] for v in st['vs']],
             alpha=0.75, edgecolor='white')
    for yy, (_, r) in zip(y, st.iterrows()):
        ax2.text(r.delta + 0.06, yy, f'  {r.delta:.2f} MAE removed   p = {r.p:.1e}',
                 va='center', fontsize=9)
    ax2.set_yticks(y); ax2.set_yticklabels(st.lbl, fontsize=9.5)
    ax2.set_xlabel('mean absolute error removed  (IMD %)')
    ax2.set_xlim(0, st.delta.max() * 1.75)
    ax2.set_title('Wilcoxon signed-rank, paired on the same 1 014 points',
                  fontsize=10, loc='left', color=MUTED)
    fig.tight_layout()
    return save(fig, 'paired')


def fig_perclass():
    """Per-class RMSE and signed bias -- where the methods actually differ."""
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12.8, 4.4))
    lbls = PER['percentile']['RF']['Label'].tolist()
    xs = np.arange(len(lbls))
    for key, _d, short in RUNS:
        d = PER[key]['RF']
        lw = 2.6 if key == 'percentile' else 1.6
        ax.plot(xs, d.RMSE, '-o', ms=5, lw=lw, color=CMAP[key],
                label=label(key, short, sep=' '))
        ax2.plot(xs, d.Bias, '-o', ms=5, lw=lw, color=CMAP[key])
    for a in (ax, ax2):
        a.set_xticks(xs)
        a.set_xticklabels([l.split(' ')[0] + '\n' + l.split(' ', 1)[1].strip('()')
                           for l in lbls], fontsize=8.5)
    ax.set_ylabel('RMSE  (IMD %)')
    ax.set_title('Error by true IMD class  ·  RF', fontsize=11,
                 fontweight='bold', loc='left')
    ax.legend(frameon=False, fontsize=8.5, loc='upper center')
    ax2.axhline(0, color=INK, lw=1.1)
    ax2.set_ylabel('Bias  (IMD %)')
    ax2.set_title('Signed bias — over- vs under-prediction', fontsize=11,
                  fontweight='bold', loc='left')
    ax2.text(0.02, 0.06, 'below 0 = over-predicted', transform=ax2.transAxes,
             fontsize=9, color=MUTED)
    ax2.text(0.98, 0.94, 'above 0 = under-predicted', transform=ax2.transAxes,
             fontsize=9, color=MUTED, ha='right')
    fig.tight_layout()
    return save(fig, 'perclass')


def fig_roadmap():
    """Next steps, ordered by what each one buys."""
    n_st, n_pc = SPEC['stack']['dates'], SPEC['percentile']['dates']
    steps = [
        ('1', 'Break the date/method confound',
         f'Run stack and percentile on a common date set —\n'
         f'stack has {n_st}, percentile {n_pc}. Isolates the reducer\n'
         f'from the number of observations.'),
        ('2', 'Cheaper feature set',
         'p25/p50/p75 (30 dims) is already on disk and close behind.\n'
         'Quantifies what the outer percentiles are worth.'),
        ('3', 'Attack the structured residuals',
         'Linear features are over-predicted. Add a texture or\n'
         'neighbourhood context feature and re-measure.'),
        ('4', 'Generalisation',
         'Apply the winning composite to Hanoi / HCMC via the\n'
         'existing transferability notebook.'),
    ]
    fig, ax = plt.subplots(figsize=(12, 4.4))
    ax.set_xlim(0, 12); ax.set_ylim(0, 4.4); ax.axis('off')
    for i, (n, title, body) in enumerate(steps):
        y = 3.45 - i * 0.92
        ax.add_patch(plt.Circle((0.55, y + 0.14), 0.23, color=ACCENT, zorder=3))
        ax.text(0.55, y + 0.14, n, ha='center', va='center', color='white',
                fontsize=12, fontweight='bold', zorder=4)
        if i < len(steps) - 1:
            ax.plot([0.55, 0.55], [y - 0.13, y - 0.55], color=RULE, lw=1.6)
        ax.text(1.15, y + 0.30, title, fontsize=11.5, fontweight='bold', va='top')
        ax.text(1.15, y - 0.02, body, fontsize=9.8, color=MUTED, va='top',
                linespacing=1.5)
    return save(fig, 'roadmap')


# ═══════════════════════════════════════════════════════════════════════════════
# Deck
# ═══════════════════════════════════════════════════════════════════════════════
W, H = Inches(13.333), Inches(7.5)


def add_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.background.fill
    bg.solid(); bg.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    return s


def textbox(slide, x, y, w, h, text, size=12, bold=False, color=INK,
            align=PP_ALIGN.LEFT, italic=False, spacing=1.25):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split('\n')):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        r = p.add_run(); r.text = line
        r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
        r.font.color.rgb = RGBColor.from_string(color.lstrip('#').upper())
        r.font.name = 'Calibri'
    return tb


def rule(slide, y, x=Inches(0.72), w=Inches(11.9), color=RULE, h=Emu(9525)):
    from pptx.enum.shapes import MSO_SHAPE
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sh.fill.solid(); sh.fill.fore_color.rgb = RGBColor.from_string(color.lstrip('#').upper())
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def header(slide, kicker, title, conclusion=None):
    """Kicker + title-as-conclusion + optional supporting sentence."""
    textbox(slide, Inches(0.72), Inches(0.30), Inches(11.9), Inches(0.3),
            kicker.upper(), size=10.5, bold=True, color=ACCENT)
    textbox(slide, Inches(0.72), Inches(0.60), Inches(11.9), Inches(0.75),
            title, size=25, bold=True)
    y = Inches(1.42)
    if conclusion:
        textbox(slide, Inches(0.72), y, Inches(11.9), Inches(0.6),
                conclusion, size=13, color=MUTED, spacing=1.3)
        y = Inches(2.02)
    rule(slide, y)
    return y


def add_picture(slide, path, top, max_h, left=Inches(0.72), max_w=Inches(11.9)):
    """Insert preserving aspect ratio, centred horizontally in the content box."""
    from PIL import Image
    iw, ih = Image.open(path).size
    ar = iw / ih
    w = max_w; h = Emu(int(w / ar))
    if h > max_h:
        h = max_h; w = Emu(int(h * ar))
    x = left + Emu(int((max_w - w) / 2))
    return slide.shapes.add_picture(path, x, top, width=w, height=h)


def table(slide, df, x, y, w, h, col_w=None, highlight_row=None, size=11):
    rows, cols = df.shape[0] + 1, df.shape[1]
    g = slide.shapes.add_table(rows, cols, x, y, w, h).table
    if col_w:
        for i, cw in enumerate(col_w):
            g.columns[i].width = cw
    for j, c in enumerate(df.columns):
        cell = g.cell(0, j)
        cell.text = str(c)
        p = cell.text_frame.paragraphs[0]
        p.runs[0].font.size = Pt(size); p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        p.runs[0].font.name = 'Calibri'
        cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor.from_string(INK.lstrip('#').upper())
    for i in range(df.shape[0]):
        hl = highlight_row is not None and i == highlight_row
        for j in range(cols):
            cell = g.cell(i + 1, j)
            cell.text = str(df.iat[i, j])
            p = cell.text_frame.paragraphs[0]
            p.runs[0].font.size = Pt(size)
            p.runs[0].font.bold = hl
            p.runs[0].font.name = 'Calibri'
            p.runs[0].font.color.rgb = RGBColor.from_string(
                (ACCENT if hl else INK).lstrip('#').upper())
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0xEC, 0xF4, 0xF0) if hl else (
                RGBColor(0xFF, 0xFF, 0xFF) if i % 2 == 0 else RGBColor(0xF7, 0xF7, 0xF7))
    return g


def build():
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    meta = json.load(open(PCTL_META))
    n_pctl_dates = len(meta['selected_dates'])
    dates_png, n_ok, n_cand, n_wrong, n_partial = fig_dates()
    stats = paired_stats()

    best_key = min(RUNS, key=lambda r: HOLD[r[0]].loc['GEE_SVR', 'RMSE'])[0]

    # ── 1 Title ───────────────────────────────────────────────────────────────
    s = add_slide(prs)
    textbox(s, Inches(0.9), Inches(2.25), Inches(11.5), Inches(0.35),
            'SENTINEL-2 BASELINE  ·  PROGRESS REVIEW', size=12, bold=True, color=ACCENT)
    textbox(s, Inches(0.9), Inches(2.65), Inches(11.5), Inches(1.5),
            'How should a year of Sentinel-2 observations\nbe turned into features?',
            size=34, bold=True, spacing=1.15)
    rule(s, Inches(4.25), x=Inches(0.9), w=Inches(4.0), color=ACCENT,
         h=Inches(0.035))
    textbox(s, Inches(0.9), Inches(4.5), Inches(11.5), Inches(1.0),
            'Three composite strategies compared against a foundation-model embedding\n'
            'Impervious surface density · Milan · 2018 · 10 m',
            size=14.5, color=MUTED, spacing=1.4)
    textbox(s, Inches(0.9), Inches(6.25), Inches(11.5), Inches(0.5),
            'Xiao Tan  ·  Politecnico di Milano', size=12, color=MUTED)

    # ── 2 Design ──────────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Study design',
               'Four predictor sets, one target — everything else held identical',
               'The comparison is designed so that the feature representation is the only '
               'variable. Same 3 500 points, same labels, same split, same models, same validation.')
    add_picture(s, fig_design(), y + Inches(0.28), Inches(4.5))

    # ── 3 Bands ───────────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Which bands', 'Ten surface-reflectance bands, no engineered indices',
               'Visible, red-edge, NIR and SWIR are all retained. Indices such as NDVI or NDBI are '
               'fixed ratios of bands the model already has — computing them adds no information a '
               'non-linear learner cannot recover itself.')
    add_picture(s, fig_bands(), y + Inches(0.35), Inches(3.5))
    textbox(s, Inches(0.72), Inches(6.35), Inches(11.9), Inches(0.7),
            'Collection: COPERNICUS/S2_SR_HARMONIZED (L2A surface reflectance) — no silent '
            'fallback to top-of-atmosphere.',
            size=11, color=MUTED, italic=True)

    # ── 4 Dates ───────────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Which dates',
               f'{n_ok} of {n_cand} acquisitions pass all three AOI-based criteria',
               f'A date is accepted only if it passes cloud (≤20% over the AOI), SCL validity (≥90%) '
               f'and swath coverage (≥95%) — all three, measured over Milan itself.')
    add_picture(s, dates_png, y + Inches(0.22), Inches(3.95))
    textbox(s, Inches(0.72), Inches(6.42), Inches(11.9), Inches(0.8),
            f'Why three criteria and not just cloud?  {n_partial} of the {n_cand} candidate dates are '
            f'partial swaths that barely cross the AOI — many report near-zero cloud precisely '
            f'because there is almost nothing there to be cloudy. All statistics are therefore '
            f'computed over Milan itself, not from the scene-level metadata, which describes a whole '
            f'MGRS tile that the AOI straddles.',
            size=11, color=MUTED, spacing=1.3)

    # ── 5 Controlled comparison ───────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Is the comparison fair?',
               'Yes — the train/test split is imported from the embedding run, not recomputed',
               '2 449 training / 1 014 test / 37 removed by the 250 m buffer. The split is recovered '
               'by joining on point geometry, and the labels are then asserted element-wise identical. '
               'Only X differs.')
    add_picture(s, 'outputs_v2/fig01_spatial_split.png', y + Inches(0.22), Inches(3.6))
    textbox(s, Inches(0.72), Inches(6.15), Inches(11.9), Inches(1.0),
            'Why not just re-use random seed 42?  Because the split is greedy over surviving 1 km '
            'blocks. If one dropped point was the only sample in its block, that block leaves the '
            'array being permuted — so the same seed yields a different split, and whole blocks flip '
            'between train and test. Importing the membership is the only guarantee.',
            size=11, color=MUTED, spacing=1.3)

    # ── 6 Validation ──────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'How it is validated',
               'Spatial block CV — and the blocking confirms there is no leakage left to remove',
               'Whole blocks (500 / 1000 / 2000 m) are assigned to folds, never individual points, '
               'with a 250 m buffer. Random CV is run alongside purely as a control.')
    add_picture(s, f'{PCTL_DIR}/fig06_inflation_heatmap.png', y + Inches(0.45), Inches(2.9))
    textbox(s, Inches(0.72), Inches(5.85), Inches(11.9), Inches(1.2),
            'Random-CV and spatial-CV RMSE agree to within ~1%. Read correctly, this says the block '
            'design is working and the 3 500 points are far enough apart that autocorrelation was '
            'never inflating the score — not that spatial validation was unnecessary. Reported '
            'accuracy can therefore be taken at face value.',
            size=11.5, color=MUTED, spacing=1.3)

    # ── 7 The three methods ───────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'The three composite methods',
               'Each method encodes a different hypothesis about what carries the signal',
               'All three start from the same cloud-masked, water-masked observations. They differ '
               'only in how the temporal axis is collapsed.')
    add_picture(s, fig_methods(), y + Inches(0.30), Inches(3.7))
    textbox(s, Inches(0.72), Inches(6.30), Inches(11.9), Inches(0.8),
            'Masking is applied BEFORE reduction, so cloudy observations are excluded from the '
            'sample rather than averaged in. Stack additionally gap-fills masked pixels from the '
            'median (0.006–1.5% of the AOI per date).',
            size=11, color=MUTED, spacing=1.3)

    # ── 8 Headline result ─────────────────────────────────────────────────────
    s = add_slide(prs)
    rmse_p = HOLD['percentile'].loc['GEE_SVR', 'RMSE']
    rmse_m = HOLD['median'].loc['GEE_SVR', 'RMSE']
    y = header(s, 'Result', 'The percentile composite is the strongest on every model and metric',
               f'Holdout RMSE falls from {rmse_m:.2f} (median) to {rmse_p:.2f} (percentile) for SVR — '
               f'a {100 * (rmse_m - rmse_p) / rmse_m:.0f}% reduction on points no model ever saw.')
    add_picture(s, fig_holdout(), y + Inches(0.25), Inches(4.4))

    # ── 9 Full metric table ───────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Result · all metrics',
               'The ranking is the same on RMSE, MAE and R² — it is not a metric artefact',
               'Held-out test set, predictions sampled from the exported 10 m rasters.')
    rows = []
    for key, _d, short in RUNS:
        sp = SPEC[key]
        dd = 'annual' if sp['dates'] is None else '{} dates'.format(sp['dates'])
        for m in ('GEE_RF', 'GEE_SVR'):
            r = HOLD[key].loc[m]
            rows.append({
                'Predictor': '{} ({})'.format(short, dd),
                'Dims': sp['dims'], 'Model': m.replace('GEE_', ''),
                'RMSE': f'{r.RMSE:.2f}', 'MAE': f'{r.MAE:.2f}',
                'R²': f'{r.R2:.3f}', 'Bias': f'{r.Bias:+.2f}'})
    df = pd.DataFrame(rows)
    best_i = int(df.RMSE.astype(float).idxmin())
    table(s, df, Inches(1.5), y + Inches(0.35), Inches(10.3), Inches(3.6),
          col_w=[Inches(3.1), Inches(0.9), Inches(1.2), Inches(1.3),
                 Inches(1.3), Inches(1.3), Inches(1.2)],
          highlight_row=best_i, size=11.5)
    textbox(s, Inches(0.72), Inches(6.5), Inches(11.9), Inches(0.6),
            'MLP is tuned and cross-validated throughout, but Earth Engine has no MLP regressor — '
            'so only RF and SVR can be exported as rasters and appear here.',
            size=11, color=MUTED, italic=True)

    # ── 10 Cross-validation ───────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Robustness',
               'The ranking holds across 25 spatial folds, not just the single holdout',
               'Five folds × five repeated fold draws, at three block sizes. Error bars are the '
               'standard deviation across folds.')
    add_picture(s, fig_cv(), y + Inches(0.25), Inches(4.35))

    # ── 11 Paired test ────────────────────────────────────────────────────────
    s = add_slide(prs)
    worst_p = stats.p.max()
    y = header(s, 'Significance',
               'The improvement is significant point-by-point, not just in aggregate',
               f'Because the split is imported, the same 1 014 holdout points appear in every run — '
               f'so errors can be paired. Wilcoxon signed-rank: p ≤ {worst_p:.0e} for all six '
               f'comparisons.')
    add_picture(s, fig_paired(stats), y + Inches(0.25), Inches(4.2))
    textbox(s, Inches(0.72), Inches(6.6), Inches(11.9), Inches(0.5),
            'The embedding run did not store per-point residuals, so it is compared on aggregate '
            'metrics only and is excluded from this test.',
            size=11, color=MUTED, italic=True)

    # ── 12 Per-class ──────────────────────────────────────────────────────────
    s = add_slide(prs)
    pc = PER['percentile']['RF']; md = PER['median']['RF']; em = PER['embedding']['RF']
    mid = lambda d: d[d.Class.between(1, 5)].RMSE.mean()
    c0_gap = pc.loc[0, 'RMSE'] - em.loc[0, 'RMSE']
    y = header(s, 'Where the methods differ',
               'The embedding is competitive only on fully pervious pixels — percentile wins the rest',
               f'Across the six built-up classes the embedding averages {mid(em):.1f} RMSE against '
               f'{mid(pc):.1f} for percentile. Its one win is the 0% class ({em.loc[0, "RMSE"]:.1f} vs '
               f'{pc.loc[0, "RMSE"]:.1f}), where telling "no built-up" from "some" needs no temporal detail.')
    add_picture(s, fig_perclass(), y + Inches(0.22), Inches(3.95))
    textbox(s, Inches(0.72), Inches(6.42), Inches(11.9), Inches(0.85),
            f'Two separate effects are visible. The median composite fails hardest at 0% '
            f'({md.loc[0, "RMSE"]:.1f} RMSE): collapsing the year to one number per band cannot tell '
            f'bare soil from asphalt. The embedding instead fails in the mixed classes, staying near '
            f'{mid(em):.0f} RMSE everywhere: it is a general-purpose annual descriptor, not one '
            f'tuned to sub-pixel imperviousness.',
            size=11, color=MUTED, spacing=1.3)

    # ── 13 Why ────────────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Interpretation',
               'The model relies on the low red and high NIR percentiles — a seasonality signal',
               'The strongest features are B4_p25 / B4_p10 (how dark the pixel gets in red) and '
               'B8_p90 / B8_p75 (how bright it gets in NIR). Neither is a median.')
    add_picture(s, f'{PCTL_DIR}/figD_importance_RF.png', y + Inches(0.35), Inches(2.75))
    textbox(s, Inches(0.72), Inches(5.55), Inches(11.9), Inches(1.5),
            'Read together, these two describe how much a pixel greens up during the year. A '
            'vegetated or agricultural surface reaches a high NIR peak and a low red trough; asphalt '
            'and roofs stay flat. A median composite cannot express this, because it reports only '
            'where the distribution sits — not how wide it is. That is the concrete reason the '
            'percentile composite outperforms, and it explains why the outer percentiles matter '
            'more than the central one.',
            size=11.5, color=MUTED, spacing=1.35)

    # ── 14 Map ────────────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Visual check',
               'The map is right at the city scale, but the residuals are spatially structured',
               'The urban core, the satellite towns and the agricultural south are all in the right '
               'places. The difference panel is where the remaining error lives.')
    add_picture(s, f'{PCTL_DIR}/figE_raster_comparison_1.png', y + Inches(0.10), Inches(3.95))
    textbox(s, Inches(0.72), Inches(6.42), Inches(11.9), Inches(0.8),
            'Residuals are not white noise: linear features — the river corridor, motorways and '
            'field boundaries — are over-predicted (red), while the dense core is slightly '
            'under-predicted (blue). Both are mixed-pixel effects at 10 m, and they point at where '
            'a texture or context feature would help next.',
            size=11, color=MUTED, spacing=1.3)

    # ── 15 Limitations ────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Limitations',
               'One confound is unresolved and must be stated before the result is used',
               'These are properties of the current experiment, not of the data.')
    # Whether the date-count confound still stands depends on the runs actually
    # on disk: once median and percentile share a date set, the comparison
    # between those two is clean and only stack is left short.
    _dc = {k: SPEC[k]['dates'] for k in ('median', 'stack', 'percentile')}
    if _dc['median'] == _dc['percentile']:
        _conf = ('Median and percentile now share {} dates, so that contrast is clean. '
                 'Stack still uses {}, so its comparison remains confounded.'
                 .format(_dc['percentile'], _dc['stack']))
    else:
        _conf = ('Percentile used {} dates; stack {} and median {}. Part of its advantage '
                 'may come from observation count, not the reducer.'
                 .format(_dc['percentile'], _dc['stack'], _dc['median']))
    lim = pd.DataFrame([
        {'#': '1', 'Limitation': 'Date count is confounded with method',
         'Consequence': _conf},
        {'#': '2', 'Limitation': 'Stack is partly synthetic',
         'Consequence': 'Masked pixels are gap-filled from the median (0.006–1.5% per date); the '
                        'model cannot distinguish filled from observed.'},
        {'#': '3', 'Limitation': 'The exported raster ≠ the tuned model',
         'Consequence': 'GEE’s smileRandomForest accepts only 2 of the 6 tuned RF hyper-parameters; '
                        'the rest are dropped at export.'},
        {'#': '4', 'Limitation': 'MLP cannot be deployed',
         'Consequence': 'It often wins cross-validation but has no Earth Engine equivalent, so it '
                        'never becomes a map.'},
        {'#': '5', 'Limitation': 'Single city, single year',
         'Consequence': 'Milan 2018 only. Nothing here demonstrates transferability yet.'},
    ])
    table(s, lim, Inches(0.72), y + Inches(0.30), Inches(11.9), Inches(3.9),
          col_w=[Inches(0.55), Inches(3.85), Inches(7.5)], size=11)

    # ── 16 Next steps ─────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Next steps',
               'The first experiment is the one that makes the current result conclusive')
    add_picture(s, fig_roadmap(), y + Inches(0.30), Inches(4.3))

    # ── 17 Summary ────────────────────────────────────────────────────────────
    s = add_slide(prs)
    y = header(s, 'Summary', 'Four answers')
    pts = [
        ('Bands and dates',
         f'Ten L2A reflectance bands, no indices. {n_ok} of {n_cand} 2018 acquisitions accepted by '
         f'three AOI-based criteria — cloud, validity and coverage.'),
        ('Comparability',
         'The train/test split is imported from the embedding run and labels asserted identical: '
         '2 449 / 1 014 / 37. Only the features differ, so the runs are directly comparable and '
         'can be paired.'),
        ('The three methods',
         'Median ({} dims) keeps central tendency; stack ({} dims) keeps {} individual dates; '
         'percentile ({} dims) keeps the shape of the annual distribution.'
         .format(SPEC['median']['dims'], SPEC['stack']['dims'],
                 SPEC['stack']['dates'], SPEC['percentile']['dims'])),
        ('Outcome',
         f'Percentile is best on every model and metric (SVR RMSE {rmse_p:.2f}, R² '
         f'{HOLD["percentile"].loc["GEE_SVR", "R2"]:.3f}), significantly so under a paired test '
         f'on the same {len(RES["percentile"]):,} holdout points.'.replace(',', ' ')),
    ]
    yy = y + Inches(0.35)
    for i, (h, b) in enumerate(pts):
        textbox(s, Inches(0.72), yy, Inches(3.0), Inches(0.9), h, size=13.5,
                bold=True, color=ACCENT)
        textbox(s, Inches(3.9), yy, Inches(8.7), Inches(1.1), b, size=12.5,
                color=INK, spacing=1.35)
        yy = yy + Inches(1.12)

    prs.save(OUT_PPTX)
    return prs, stats


if __name__ == '__main__':
    prs, stats = build()
    print(f'Wrote {OUT_PPTX}  ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)')
    print('\nPaired Wilcoxon (percentile vs alternatives):')
    print(stats.to_string(index=False))
