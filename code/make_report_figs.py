"""Build the report figures that no notebook produces.

Every value is parsed from data/FACTS.md. Nothing is hardcoded: if a number the
figure needs is absent from the fact base, the script raises rather than
substituting a literal, so a figure can never drift from the numbers it claims
to show.

House style follows make_presentation.py, as recorded in data/FIGURES.md.

Usage:  python code/make_report_figs.py            # all built figures
        python code/make_report_figs.py F12        # one figure
"""

import json
import os
import re
import sys

import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = os.path.join(REPO, 'data', 'FACTS.md')
FIGS = os.path.join(REPO, 'report', 'figs')

# ── House style ──────────────────────────────────────────────────────────────
# These figures sit in the REPORT beside the notebook figures, not in the deck,
# so the conventions come from the notebooks (01/01b/02/03/04) rather than from
# make_presentation.py. Matched against outputs_v2/figA_holdout_accuracy_GEE_RF:
# notebook rcParams verbatim, dpi 150, 'Figure N · Description' suptitle at 13pt
# bold, axes titles 11pt bold, axis labels 10pt, plain matplotlib defaults for
# font family and tick colour. No kicker, no conclusion-as-title, no in-figure
# caption -- the claim belongs to the report text.
DPI = 150

plt.rcParams.update({
    'figure.dpi': 130, 'font.size': 10,
    'axes.titlesize': 11, 'axes.labelsize': 10,
    'axes.spines.top': False, 'axes.spines.right': False,
})

# The only thing carried over from the deck: per-predictor colours, which are
# semantic and consistent across the whole project.
CMAP = {
    'S2 median':             '#b0b7bd',
    'S2 stack':              '#7d93a3',
    'S2 percentile':         '#0B6E4F',
    'AlphaEarth embeddings': '#C2724A',
}
REF_GREY = '#6b6b6b'          # CLMS / GHSL, the training targets


# ── FACTS.md parsing ─────────────────────────────────────────────────────────
def _tables():
    """Every markdown table in FACTS.md, as (header, [row dicts])."""
    out, header, rows = [], None, []
    for line in open(FACTS, encoding='utf-8'):
        line = line.rstrip('\n')
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if all(set(c) <= set('-: ') and c for c in cells):
                continue                       # separator row
            if header is None:
                header = cells
            else:
                rows.append(dict(zip(header, cells)))
        else:
            if header and rows:
                out.append((header, rows))
            header, rows = None, []
    if header and rows:
        out.append((header, rows))
    return out


def facts_rows(**where):
    """Rows from any FACTS.md table matching every key=value constraint.

    Matching is on the cell text with markdown emphasis stripped, so
    '**strict** (primary)' is addressable as 'strict'.
    """
    def norm(v):
        return re.sub(r'\*\*|\s*\(primary\)', '', v).strip()

    hits = []
    for header, rows in _tables():
        if not all(k in header for k in where):
            continue
        for r in rows:
            if all(norm(r[k]) == v for k, v in where.items()):
                hits.append(r)
    return hits


def facts_value(column, **where):
    """Exactly one numeric value from FACTS.md, or raise saying what is absent.

    Raising is the point: a missing number must stop the build, never fall back
    to a literal that the fact base cannot vouch for.
    """
    hits = facts_rows(**where)
    if not hits:
        raise LookupError(
            f'FACTS.md has no row matching {where}. The figure needs '
            f'{column!r} from it. Add the row (or extend '
            f'code/collect_metrics.py) rather than hardcoding the value.')
    vals = {h[column] for h in hits if h.get(column) not in (None, '')}
    if len(vals) != 1:
        raise LookupError(
            f'{where} matched {len(hits)} rows with {len(vals)} distinct '
            f'{column!r} values ({sorted(vals)}). Constrain the query further.')
    raw = vals.pop()
    if raw == 'MISSING':
        raise LookupError(f'{column!r} is MISSING in FACTS.md for {where}.')
    return float(raw)


# ── F12 · same-source vs independent validation ──────────────────────────────
# Table A predictor_set -> Table B map_id. The two tables name the same
# predictor sets differently, so the correspondence is declared once, here.
PREDICTORS = [
    ('S2 percentile',         'S2_percentile'),
    ('S2 stack',              'S2_stack'),
    ('S2 median',             'S2_median'),
    ('AlphaEarth embeddings', 'emb_RF'),
]


def f12_values():
    """Plotted values, read from FACTS.md. Returns (rows, clms_independent)."""
    rows = []
    for a_name, b_name in PREDICTORS:
        rows.append(dict(
            predictor=a_name,
            same_source=facts_value('RMSE', city='Milan', predictor_set=a_name,
                                    model='GEE_RF'),
            independent=facts_value('RMSE', city='Milan', map_id=b_name,
                                    rule='strict'),
        ))
    clms = facts_value('RMSE', city='Milan', map_id='CLMS', rule='strict')
    return rows, clms


def build_f12():
    rows, clms = f12_values()

    a_vals = [r['same_source'] for r in rows]
    b_model = [r['independent'] for r in rows]
    b_vals = b_model + [clms]

    # ── Scaling ──────────────────────────────────────────────────────────────
    # ONE shared y axis, at true values, covering both groups with headroom.
    # The within-group differences look small because they ARE small relative
    # to the gap between the two validations, and that is the finding: the
    # separation between predictor sets collapses once the reference changes.
    # The axis is deliberately NOT zoomed, broken, or split into two scales --
    # any of those would inflate a 1.34 pp spread into a visual argument the
    # data does not support.
    y_lo, y_hi = 5.0, 30.0

    fig, ax = plt.subplots(figsize=(8.0, 5.6))
    ax.set_ylim(y_lo, y_hi)

    x0, x1 = 0.0, 1.0
    for r in rows:
        c = CMAP[r['predictor']]
        ax.plot([x0, x1], [r['same_source'], r['independent']], '-o',
                color=c, lw=2.2, ms=6, label=r['predictor'], zorder=3)

    # CLMS: independent validation only -- it is the same-source reference and
    # cannot be scored against itself, so this marker has no left-hand end.
    ax.plot([x1], [clms], 'D', color=REF_GREY, ms=7, zorder=3,
            label='CLMS (training target, independent only)')

    # Value labels beside every point. Within each column the values crowd, so
    # walk them downward and hold a minimum gap; the leader line shows which
    # point a displaced label belongs to.
    def place(items, x, dx, ha):
        min_gap = 1.05                       # pp, ~one label height at 5-30
        prev = None
        for value, colour in sorted(items, key=lambda t: t[0], reverse=True):
            y = value
            if prev is not None and prev - y < min_gap:
                y = prev - min_gap
            prev = y
            ax.annotate(f'{value:.2f}', xy=(x, value), xycoords='data',
                        xytext=(x + dx, y), textcoords='data',
                        ha=ha, va='center', fontsize=8.5, color=colour,
                        annotation_clip=False,
                        arrowprops=dict(arrowstyle='-', color=colour, lw=0.7,
                                        shrinkA=0, shrinkB=3, alpha=0.55))

    place([(r['same_source'], CMAP[r['predictor']]) for r in rows], x0, -0.07,
          'right')
    place([(r['independent'], CMAP[r['predictor']]) for r in rows]
          + [(clms, REF_GREY)], x1, 0.07, 'left')

    spread_a = max(a_vals) - min(a_vals)
    spread_b = max(b_model) - min(b_model)

    ax.set_xlim(-0.34, 1.34)
    ax.set_xticks([x0, x1])
    ax.set_xticklabels(
        ['same-source validation\n(vs CLMS, n = 1 014)',
         'independent validation\n(vs photo-interpretation, n = 450)'])
    ax.tick_params(axis='x', length=0, pad=8)
    ax.set_ylabel('RMSE (IMD percentage points)')

    # Inside the axes, lower right: both series rise left-to-right, so the
    # region below the independent-validation points is empty at every x.
    ax.legend(loc='lower right', fontsize=8, framealpha=0.9,
              handlelength=2.2, borderpad=0.7, labelspacing=0.5)

    ax.set_title(f'Spread {spread_a:.2f} pp same-source, {spread_b:.2f} pp '
                 f'independent', fontweight='bold')
    fig.suptitle('Figure 15 · Milan predictor sets under both validations',
                 fontsize=13, fontweight='bold', y=0.99)

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_samesource_vs_independent.png')
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # ── Plotted values, for checking against FACTS.md ────────────────────────
    print('F12 · fig_samesource_vs_independent — plotted values')
    print(f'{"predictor":24s} {"same-source":>12s} {"independent":>12s} '
          f'{"change":>9s}')
    print('-' * 61)
    for r in rows:
        print(f'{r["predictor"]:24s} {r["same_source"]:12.3f} '
              f'{r["independent"]:12.3f} '
              f'{r["independent"] - r["same_source"]:+9.3f}')
    print(f'{"CLMS (training target)":24s} {"—":>12s} {clms:12.3f} {"—":>9s}')
    print('-' * 61)
    print(f'{"spread":24s} {spread_a:12.3f} {spread_b:12.3f}')
    print(f'{"as % of worst map":24s} {100 * spread_a / max(a_vals):11.1f}% '
          f'{100 * spread_b / max(b_model):11.1f}%')
    print('')
    print(f'compression: {spread_a / spread_b:.1f}x absolute, '
          f'{(spread_a / max(a_vals)) / (spread_b / max(b_model)):.1f}x relative')
    print(f'shared y axis: {y_lo:.0f}-{y_hi:.0f} pp, true values, not zoomed')
    print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


# ── F1 · composite depth ─────────────────────────────────────────────────────
# The usable-date lists live in each run's extraction metadata, which is the
# same source data/EXPERIMENT_MAP.md's composite-date table was built from.
# EXPERIMENT_MAP.md abbreviates Milan's 30 dates as a range, so the metadata is
# read directly and the counts are cross-checked against the table below.
DEPTH_RUNS = [
    ('Milan', 'samples_S2_median/s2_extraction_metadata.json'),
    ('Hanoi', 'samples_S2_median_Hanoi/s2_extraction_metadata.json'),
    ('HCMC',  'samples_S2_median_HCMC/s2_extraction_metadata.json'),
]

# Two acquisitions closer than this are the same scene state, not two seasons.
EFFECTIVE_LOOK_DAYS = 10


def f1_values():
    """Usable dates per city, plus the percentile minimum. Nothing hardcoded."""
    import datetime as _dt

    out = []
    for city, rel in DEPTH_RUNS:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            raise LookupError(
                f'{rel} is missing; it holds {city}\'s screened dates. '
                'Re-run the extraction notebook rather than hardcoding them.')
        with open(path, encoding='utf-8') as fh:
            meta = json.load(fh)
        dates = sorted(_dt.date.fromisoformat(d)
                       for d in meta['selected_dates'])
        if not dates:
            raise LookupError(f'{rel} lists no selected_dates for {city}.')

        # Group acquisitions closer together than EFFECTIVE_LOOK_DAYS: they
        # sample the same scene state, so they are one look, not two.
        # Measured from the FIRST date in the cluster, not the last -- chaining
        # off the last would let a run of 5-day steps collapse two months of
        # Milan into a single "look", which is plainly wrong.
        clusters = [[dates[0]]]
        for d in dates[1:]:
            if (d - clusters[-1][0]).days < EFFECTIVE_LOOK_DAYS:
                clusters[-1].append(d)
            else:
                clusters.append([d])

        out.append(dict(city=city, dates=dates, clusters=clusters,
                        obs_per_pixel=meta.get('obs_per_pixel'),
                        source=rel))

    # The percentile floor is a function of the percentile SET, and the set is
    # a per-run choice. s2_utils.PERCENTILES still defaults to the retired
    # 3-percentile set (floor 10), so taking the default would understate the
    # threshold this project actually faced. Read the set from the percentile
    # run that is in use, and derive the floor from it.
    pctl_rel = ('samples_S2_percentile_p10p25p50p75p90/'
                's2_extraction_metadata.json')
    pctl_path = os.path.join(REPO, pctl_rel)
    if not os.path.exists(pctl_path):
        raise LookupError(
            f'{pctl_rel} is missing; it declares the percentile set whose '
            'date floor this figure states. Do not substitute the s2_utils '
            'default -- it is the retired 3-percentile set.')
    with open(pctl_path, encoding='utf-8') as fh:
        pctl = json.load(fh)['percentiles']

    sys.path.insert(0, REPO)
    from s2_utils import min_dates_for
    return out, min_dates_for(pctl), len(pctl)


def build_f1():
    cities, min_dates, n_pctl = f1_values()

    import datetime as _dt
    year = cities[0]['dates'][0].year
    jan1 = _dt.date(year, 1, 1)
    doy = lambda d: (d - jan1).days + 1                       # noqa: E731

    fig, ax = plt.subplots(figsize=(8.6, 3.6))

    # One row per city, Milan at the top so the eye reads dense -> sparse.
    ypos = {c['city']: len(cities) - 1 - i for i, c in enumerate(cities)}

    # Month bands: alternating shading is easier to read than 12 gridlines.
    month_starts = [_dt.date(year, m, 1) for m in range(1, 13)]
    for m, start in enumerate(month_starts):
        if m % 2:
            end = (_dt.date(year, m + 2, 1) if m < 11
                   else _dt.date(year + 1, 1, 1))
            ax.axvspan(doy(start), doy(end) - 1, color='#f2f2f2', zorder=0,
                       linewidth=0)

    for c in cities:
        y = ypos[c['city']]
        # Milan is the source city, Hanoi and HCMC the transfer targets. The
        # split the figure argues is source-vs-target, so one colour each side
        # rather than the per-predictor palette (which is about composites,
        # not cities).
        colour = '#0B6E4F' if c['city'] == 'Milan' else '#C2724A'

        # No bracket, no "= 1 look" annotation. That two December marks sit
        # five days apart is visible in the plot; what it IMPLIES about
        # effective composite depth is an interpretation, and interpretation
        # belongs in the caption. The clustering is still computed and printed
        # to the console so the caption can be written from measured values.

        ax.plot([doy(d) for d in c['dates']], [y] * len(c['dates']),
                marker='|', linestyle='none', color=colour,
                markersize=15, markeredgewidth=2.0, zorder=3)

        # Readings only: the date count and the measured obs/pixel. "Effective
        # looks" is a derived interpretation and stays out of the image.
        label = f'{len(c["dates"])} dates'
        if c['obs_per_pixel']:
            label += f' · {c["obs_per_pixel"]:.2f} obs/px'
        ax.annotate(label, xy=(doy(_dt.date(year, 12, 31)) + 6, y),
                    ha='left', va='center', fontsize=8.5, color=colour,
                    annotation_clip=False)

    # The percentile floor is the §2.3 argument, not a reading off this plot,
    # so it is not drawn. min_dates is still computed and printed to the
    # console for the caption to quote.

    ax.set_yticks([ypos[c['city']] for c in cities])
    ax.set_yticklabels([c['city'] for c in cities], fontsize=10)
    ax.set_ylim(-0.75, len(cities) - 0.5)

    mid = [doy(_dt.date(year, m, 15)) for m in range(1, 13)]
    ax.set_xticks(mid)
    ax.set_xticklabels(list('JFMAMJJASOND'), fontsize=9)
    ax.set_xlim(1, doy(_dt.date(year, 12, 31)))
    ax.set_xlabel(f'{year}')
    ax.tick_params(axis='both', length=0)
    for side in ('left', 'bottom'):
        ax.spines[side].set_visible(False)

    ax.set_title('Usable Sentinel-2 acquisitions after cloud screening',
                 fontweight='bold')
    fig.suptitle('Figure 1 · Composite depth by city',
                 fontsize=13, fontweight='bold', y=1.06)

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_composite_depth.png')
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # ── Plotted dates, for checking against EXPERIMENT_MAP.md ───────────────
    print('F1 · fig_composite_depth — plotted dates')
    print(f'percentile floor: >= {min_dates} dates for {n_pctl} percentiles '
          '(s2_utils.min_dates_for)')
    print('')
    for c in cities:
        looks = len(c['clusters'])
        obs = (f'{c["obs_per_pixel"]:.2f}' if c['obs_per_pixel'] else '—')
        print(f'{c["city"]:6s} n={len(c["dates"]):2d}  effective looks={looks:2d}  '
              f'obs/pixel={obs:>5s}  clears {min_dates}? '
              f'{"YES" if len(c["dates"]) >= min_dates else "no"}')
        print(f'        months: '
              f'{sorted({d.month for d in c["dates"]})}')
        for i in range(0, len(c['dates']), 6):
            print('        ' + '  '.join(d.isoformat()
                                         for d in c['dates'][i:i + 6]))
        for cl in c['clusters']:
            if len(cl) > 1:
                gap = (cl[-1] - cl[0]).days
                print(f'        clustered: '
                      f'{", ".join(d.isoformat() for d in cl)} '
                      f'({gap} days apart -> 1 effective look)')
        print(f'        source: {c["source"]}')
        print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


# ── F13 · HCMC predicted-IMD distributions ───────────────────────────────────
# Column order = the order the maps appear in the report's argument: the two
# zero-shots (which sit high) then the two local retrains (which sit low).
HCMC_MAPS = [
    ('emb_zeroshot',       'AlphaEarth embeddings · zero-shot'),
    ('S2_median_zeroshot', 'S2 median · zero-shot'),
    ('emb_localrf',        'AlphaEarth embeddings · local retrain'),
    ('S2_median_localrf',  'S2 median · local retrain'),
]
REFERENCE_COL = '(reference)'


def _pct(cell):
    """Percentage out of a '116 (25.8%)' bin cell."""
    m = re.search(r'\(([\d.]+)%\)', cell)
    if not m:
        raise LookupError(f'Cannot read a percentage from bin cell {cell!r}.')
    return float(m.group(1))


def f13_values():
    """Bin table and summary stats for the HCMC maps, read from FACTS.md.

    FACTS.md carries the SAME table shape for Hanoi and for HCMC, one after the
    other, and neither carries a city column -- the city is named only in the
    prose heading above each. Selecting by column shape alone therefore matches
    both and silently takes whichever comes first, which is Hanoi. Every lookup
    here is scoped to the HCMC half of the file by position, and the scoping is
    asserted rather than assumed.
    """
    text = open(FACTS, encoding='utf-8').read()
    marker = text.find('**HCMC.**')
    if marker < 0:
        raise LookupError(
            "FACTS.md has no '**HCMC.**' range-diagnostics heading, which is "
            'what scopes this figure to the right city. Re-run '
            'code/collect_metrics.py.')
    # The retention table that follows both cities' blocks repeats map_id with
    # a different column set, so the HCMC window ends where it begins.
    end = text.find('**Tail and spread retention', marker)
    hcmc = text[marker:end if end > 0 else len(text)]

    def hcmc_tables():
        """Tables inside the HCMC window only."""
        out, header, rows = [], None, []
        for line in hcmc.split('\n'):
            if line.startswith('|'):
                cells = [c.strip() for c in line.strip('|').split('|')]
                if all(set(c) <= set('-: ') and c for c in cells):
                    continue
                if header is None:
                    header = cells
                else:
                    rows.append(dict(zip(header, cells)))
            else:
                if header and rows:
                    out.append((header, rows))
                header, rows = None, []
        if header and rows:
            out.append((header, rows))
        return out

    tables = hcmc_tables()

    # Bin table: identified by its 'bin' column plus the reference column.
    rows = next((t for h, t in tables
                 if 'bin' in h and REFERENCE_COL in h), [])
    if not rows:
        raise LookupError(
            'The HCMC section of FACTS.md has no bin-distribution table (a '
            "table with a 'bin' column and a '(reference)' column). Re-run "
            'code/collect_metrics.py.')

    edges = [r['bin'] for r in rows]
    dist = {}
    for col in [m for m, _ in HCMC_MAPS] + [REFERENCE_COL]:
        if col not in rows[0]:
            raise LookupError(f'Bin table has no column {col!r}.')
        dist[col] = [_pct(r[col]) for r in rows]

    # Summary stats: the HCMC table carrying an IQR column.
    stat_rows = next((t for h, t in tables if 'IQR' in h and 'map_id' in h), [])
    if not stat_rows:
        raise LookupError(
            'The HCMC section of FACTS.md has no summary table with an IQR '
            'column. Re-run code/collect_metrics.py.')

    stats = {}
    for col in [m for m, _ in HCMC_MAPS] + [REFERENCE_COL]:
        hit = [r for r in stat_rows if r.get('map_id') == col]
        if len(hit) != 1:
            raise LookupError(
                f'Expected exactly one HCMC summary row for {col!r}, found '
                f'{len(hit)}.')
        r = hit[0]
        stats[col] = {k: float(r[k].rstrip('%'))
                      for k in ('mean', 'sd', 'min', 'max', 'IQR',
                                'pct_gt80', 'pct_lt20')}

    # The city scoping is the whole point of the window above, so verify it
    # landed rather than trusting the heading search: HCMC's reference mean is
    # 51.06 and Hanoi's is 46.05, and taking the wrong table would be silent.
    ref_mean = stats[REFERENCE_COL]['mean']
    hcmc_ref = facts_value('mean_reference', city='HCMC', map_id='emb_zeroshot')
    if abs(ref_mean - hcmc_ref) > 0.01:
        raise LookupError(
            f'Scoping check failed: the selected reference mean is {ref_mean}, '
            f"but FACTS.md gives HCMC's as {hcmc_ref}. The window landed on "
            'the wrong city.')

    return edges, dist, stats


def build_f13():
    edges, dist, stats = f13_values()
    maps = [m for m, _ in HCMC_MAPS]
    ref = dist[REFERENCE_COL]
    x = np.arange(len(edges))

    # Five panels in ONE ROW: the four maps, then the reference as its own
    # histogram at the end rather than ghosted behind each map. Side by side
    # on a shared y axis, the shapes compare directly and the reference reads
    # as the peer distribution it is, not as a backdrop.
    panels = [(col, title, (CMAP['AlphaEarth embeddings']
                            if col.startswith('emb') else CMAP['S2 stack']))
              for col, title in HCMC_MAPS]
    panels.append((REFERENCE_COL, 'photo-interpreted reference', REF_GREY))
    n_panel = len(panels)

    fig = plt.figure(figsize=(13.2, 5.2))
    # Two INDEPENDENT gridspecs rather than one shared 2-row grid. The strip
    # needs a wide left gutter for its row labels; the panels do not, and in a
    # shared grid they inherit it and leave the top-left corner empty. Giving
    # each row its own left margin lets the histograms use the full width.
    gs = fig.add_gridspec(1, n_panel, left=0.055, right=0.995,
                          top=0.82, bottom=0.48, wspace=0.16)
    gs_strip = fig.add_gridspec(1, 1, left=0.175, right=0.995,
                                top=0.36, bottom=0.10)

    y_max = max(max(v) for v in dist.values()) * 1.12

    for i, (col, title, colour) in enumerate(panels):
        ax = fig.add_subplot(gs[0, i])
        ax.bar(x, dist[col], width=0.82, color=colour, linewidth=0, zorder=2)

        ax.set_ylim(0, y_max)
        ax.set_xlim(-0.7, len(edges) - 0.3)
        # Every second bin label, else ten ranges collide at this panel width.
        ax.set_xticks(x[::2])
        ax.set_xticklabels([edges[k] for k in range(0, len(edges), 2)],
                           fontsize=7.5)
        ax.tick_params(axis='both', labelsize=7.5, length=0)
        # Shared y scale, labelled once on the left-hand panel only.
        if i == 0:
            ax.set_ylabel('% of plots', fontsize=9)
        else:
            ax.set_yticklabels([])
        # Two-line titles keep the panels narrow without truncating names.
        ax.set_title(title.replace(' · ', '\n'), fontsize=8.5,
                     fontweight='bold', loc='left', linespacing=1.4)
        ax.set_xlabel('Predicted IMD (%)', fontsize=8.5)
        for side in ('left', 'bottom'):
            ax.spines[side].set_color(REF_GREY)

    # ── Summary strip: observed range, IQR and mean, per map ────────────────
    axs = fig.add_subplot(gs_strip[0, 0])
    order = maps + [REFERENCE_COL]
    labels = [t for _, t in HCMC_MAPS] + ['photo-interpreted reference']

    for j, col in enumerate(order):
        y = len(order) - 1 - j
        s = stats[col]
        colour = (REF_GREY if col == REFERENCE_COL else
                  CMAP['AlphaEarth embeddings'] if col.startswith('emb')
                  else CMAP['S2 stack'])
        # Full observed range, then the interquartile block on top of it.
        axs.plot([s['min'], s['max']], [y, y], '-', color=colour, lw=1.4,
                 alpha=0.55, zorder=2, solid_capstyle='butt')
        half = s['IQR'] / 2
        axs.barh(y, s['IQR'], left=max(s['mean'] - half, 0), height=0.36,
                 color=colour, alpha=0.30, linewidth=0, zorder=3)
        axs.plot([s['mean']], [y], 'o', color=colour, ms=7,
                 markeredgecolor='white', mew=1.2, zorder=4)
        # The mean is labelled on the row itself, just above the dot. min and
        # max are NOT labelled in place: with five rows at this spacing a
        # label offset vertically lands between rows and reads as belonging to
        # the neighbour. They go in the numeric column at the right instead,
        # where each value is unambiguously on its own row.
        axs.annotate(f'{s["mean"]:.1f}', (s['mean'], y), xytext=(0, 8),
                     textcoords='offset points', ha='center', va='bottom',
                     fontsize=8, color=colour, fontweight='bold')

    axs.set_yticks(range(len(order)))
    axs.set_yticklabels(labels[::-1], fontsize=9)
    axs.set_ylim(-0.75, len(order) - 0.15)
    axs.set_xlim(-3, 175)
    axs.set_xticks([0, 20, 40, 60, 80, 100])
    axs.set_xlabel('Predicted IMD (%)  ·  bar = observed range, '
                   'block = IQR about the mean, dot = mean', fontsize=9)
    axs.tick_params(axis='both', labelsize=8, length=0)
    for side in ('left', 'bottom'):
        axs.spines[side].set_color(REF_GREY)

    # IQR and 'below 20%' as a numeric column: both are readings, not claims.
    for j, col in enumerate(order):
        y = len(order) - 1 - j
        s = stats[col]
        colour = (REF_GREY if col == REFERENCE_COL else
                  CMAP['AlphaEarth embeddings'] if col.startswith('emb')
                  else CMAP['S2 stack'])
        axs.annotate(f'{s["min"]:5.1f} – {s["max"]:5.1f}    '
                     f'IQR {s["IQR"]:5.1f}    <20%: {s["pct_lt20"]:4.1f}%',
                     xy=(107, y), ha='left', va='center', fontsize=8,
                     color=colour, annotation_clip=False,
                     family='DejaVu Sans Mono')

    axs.set_title('Observed range, interquartile spread and mean',
                  fontsize=9.5, fontweight='bold', loc='left')
    axs.annotate('  min –   max        IQR      <20%',
                 xy=(107, len(order) - 0.45), ha='left', va='bottom',
                 fontsize=7.5, color=REF_GREY, annotation_clip=False,
                 family='DejaVu Sans Mono')

    fig.suptitle('Figure 16 · HCMC predicted IMD distributions '
                 '(n = 450 plots)', fontsize=13, fontweight='bold', y=0.97)

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_hcmc_prediction_histogram.png')
    # Explicit margins are set on both gridspecs above, so tight bbox is
    # NOT used here -- it would recompute them and undo the wide-panel
    # layout.
    fig.savefig(path, dpi=DPI)
    plt.close(fig)

    # ── Plotted values, for checking against FACTS.md ───────────────────────
    print('F13 · fig_hcmc_prediction_histogram — plotted values')
    print('')
    print('Distribution (% of 450 plots per bin)')
    hdr = f'{"bin":>8s}' + ''.join(f'{c[:17]:>18s}'
                                   for c in maps + [REFERENCE_COL])
    print(hdr)
    print('-' * len(hdr))
    for i, b in enumerate(edges):
        print(f'{b:>8s}' + ''.join(f'{dist[c][i]:17.1f}%'
                                   for c in maps + [REFERENCE_COL]))
    print('')
    print('Summary')
    print(f'{"map":>20s} {"mean":>7s} {"sd":>7s} {"min":>7s} {"max":>7s} '
          f'{"IQR":>7s} {"<20%":>7s} {">80%":>7s}')
    print('-' * 78)
    for col in maps + [REFERENCE_COL]:
        s = stats[col]
        print(f'{col:>20s} {s["mean"]:7.2f} {s["sd"]:7.2f} {s["min"]:7.1f} '
              f'{s["max"]:7.1f} {s["IQR"]:7.1f} {s["pct_lt20"]:6.1f}% '
              f'{s["pct_gt80"]:6.1f}%')
    print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


# ── F14 · bias recovery ──────────────────────────────────────────────────────
BIAS_CITIES = ['Hanoi', 'HCMC']
RETRAINS = [
    ('emb_localrf',       'AlphaEarth embeddings'),
    ('S2_median_localrf', 'S2 median'),
]


def f14_values():
    """Target bias and each local retrain's bias, per city, from FACTS.md."""
    out = []
    for city in BIAS_CITIES:
        rows = [r for r in facts_rows(city=city) if 'recovered_pp' in r]
        if not rows:
            raise LookupError(
                f'FACTS.md has no bias-recovery row for {city!r} (a row with a '
                "'recovered_pp' column). Re-run code/collect_metrics.py.")
        targets = {r['target'] for r in rows}
        t_bias = {float(r['target_bias']) for r in rows}
        if len(targets) != 1 or len(t_bias) != 1:
            raise LookupError(
                f'{city}: expected one target with one bias, got '
                f'{sorted(targets)} / {sorted(t_bias)}.')
        maps = []
        for map_id, label in RETRAINS:
            hit = [r for r in rows if r['map_id'] == map_id]
            if len(hit) != 1:
                raise LookupError(
                    f'{city}: expected exactly one bias-recovery row for '
                    f'{map_id!r}, found {len(hit)}.')
            r = hit[0]
            maps.append(dict(map_id=map_id, label=label,
                             bias=float(r['map_bias']),
                             recovered=float(r['recovered_pp'])))
        out.append(dict(city=city, target=targets.pop(),
                        target_bias=t_bias.pop(), maps=maps))
    return out


def build_f14():
    cities = f14_values()

    fig, axes = plt.subplots(1, len(cities), figsize=(9.6, 4.4), sharey=True)
    if len(cities) == 1:
        axes = [axes]

    all_bias = [c['target_bias'] for c in cities] + \
               [m['bias'] for c in cities for m in c['maps']]
    y_hi = max(all_bias) * 1.22
    # Plot each retrain at its own list index. An indirection map here had
    # reversed the columns against their tick labels: matplotlib sorts tick
    # POSITIONS but takes labels in the order given, so a non-monotonic
    # position list silently mislabels every column.

    for ax, c in zip(axes, cities):
        # Zero: the value both the target and the models are moving toward.
        ax.axhline(0, color=REF_GREY, lw=1.2, zorder=1)
        ax.annotate('0  (no bias)', xy=(0.985, 0), xycoords=('axes fraction',
                                                             'data'),
                    xytext=(0, 4), textcoords='offset points',
                    ha='right', va='bottom', fontsize=8, color=REF_GREY)

        for i, m in enumerate(c['maps']):
            x = float(i)
            colour = (CMAP['AlphaEarth embeddings']
                      if m['map_id'].startswith('emb') else CMAP['S2 stack'])

            # Segment from the training target's bias down to the model's.
            ax.annotate('', xy=(x, m['bias']), xytext=(x, c['target_bias']),
                        arrowprops=dict(arrowstyle='-|>', color=colour,
                                        lw=2.0, shrinkA=4, shrinkB=4,
                                        mutation_scale=14))
            ax.plot([x], [c['target_bias']], 'D', color=REF_GREY, ms=8,
                    markeredgecolor='white', mew=1.2, zorder=3)
            ax.plot([x], [m['bias']], 'o', color=colour, ms=8,
                    markeredgecolor='white', mew=1.2, zorder=3)

            ax.annotate(f'{c["target_bias"]:+.2f}', (x, c['target_bias']),
                        xytext=(0, 9), textcoords='offset points',
                        ha='center', va='bottom', fontsize=8.5,
                        color=REF_GREY, fontweight='bold')
            ax.annotate(f'{m["bias"]:+.2f}', (x, m['bias']),
                        xytext=(0, -10), textcoords='offset points',
                        ha='center', va='top', fontsize=8.5, color=colour,
                        fontweight='bold')
            # The closed gap, as a number only.
            ax.annotate(f'{m["recovered"]:.2f} pp',
                        (x, (c['target_bias'] + m['bias']) / 2),
                        xytext=(8, 0), textcoords='offset points',
                        ha='left', va='center', fontsize=8.5, color=colour)

        ax.set_xlim(-0.62, 1.62)
        ax.set_ylim(-1.5, y_hi)
        ax.set_xticks(range(len(c['maps'])))
        ax.set_xticklabels([m['label'] for m in c['maps']], fontsize=9)
        ax.tick_params(axis='both', labelsize=8.5, length=0)
        ax.set_title(f'{c["city"]}', fontsize=11, fontweight='bold',
                     loc='left')
        for side in ('left', 'bottom'):
            ax.spines[side].set_color(REF_GREY)
        ax.spines['bottom'].set_visible(False)

    axes[0].set_ylabel('Bias vs photo-interpretation (pp)\n'
                       'observed − predicted; positive = under-predicts',
                       fontsize=9.5, linespacing=1.5)

    # One legend, naming what the two marker shapes are.
    handles = [
        plt.Line2D([], [], marker='D', color=REF_GREY, linestyle='none',
                   ms=8, markeredgecolor='white', mew=1.2,
                   label=f'{cities[0]["target"]} (training target)'),
        plt.Line2D([], [], marker='o', color=REF_GREY, linestyle='none',
                   ms=8, markeredgecolor='white', mew=1.2,
                   label='local retrain'),
    ]
    axes[-1].legend(handles=handles, loc='upper right', fontsize=8.5,
                    framealpha=0.9, handletextpad=0.5)

    fig.suptitle('Figure 17 · Bias against photo-interpretation, '
                 'training target and local retrains',
                 fontsize=13, fontweight='bold', y=1.01)
    fig.tight_layout()

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_bias_recovery.png')
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # ── Plotted values, for checking against FACTS.md ───────────────────────
    print('F14 · fig_bias_recovery — plotted values')
    print(f'{"city":6s} {"target":6s} {"target_bias":>12s} {"map":>22s} '
          f'{"map_bias":>9s} {"recovered_pp":>13s}')
    print('-' * 74)
    for c in cities:
        for m in c['maps']:
            print(f'{c["city"]:6s} {c["target"]:6s} '
                  f'{c["target_bias"]:+12.2f} {m["map_id"]:>22s} '
                  f'{m["bias"]:+9.2f} {m["recovered"]:13.2f}')
    print('-' * 74)
    print('bias = observed - predicted; positive = the map under-predicts')
    print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


# ── F15 · Milan raster comparison ────────────────────────────────────────────
# The one figure here built from rasters rather than from FACTS.md. It is a
# relabelling of the notebook's figE_raster_comparison_1.png, which FIGURES.md
# records as NEEDS-EDIT: its suptitle is commented out in 01b, so the three
# composite runs' copies are indistinguishable outside their directory path.
#
# Rebuilt rather than re-executed. Notebook 01b would re-tune models and
# re-export rasters (CLAUDE.md), but this figure only READS two GeoTIFFs that
# already exist, so redrawing them standalone is safe and changes no model.
# The panel geometry, colours, scale and limits are copied from 01b verbatim;
# the only change is a suptitle naming the run.
RASTER_OBS = 'data/IMD_2018_CLMS_UTM32N.tif'
RASTER_PRED = ('outputs_S2_percentile_p10p25p50p75p90/'
               'IMD_predicted_RF_S2_Milan.tif')
DISPLAY_SCALE = 2          # 01b's decimation factor, kept for comparability


def build_f15():
    import matplotlib.ticker as mticker
    from matplotlib.colors import ListedColormap
    import rioxarray as rxr

    obs_path = os.path.join(REPO, RASTER_OBS)
    pred_path = os.path.join(REPO, RASTER_PRED)
    for p in (obs_path, pred_path):
        if not os.path.exists(p):
            raise SystemExit(f'F15 needs {os.path.relpath(p, REPO)}, '
                             'which is not on disk.')

    obs = rxr.open_rasterio(obs_path, masked=False).squeeze(
        'band', drop=True)[::DISPLAY_SCALE, ::DISPLAY_SCALE]
    pred = rxr.open_rasterio(pred_path, masked=False).squeeze(
        'band', drop=True)[::DISPLAY_SCALE, ::DISPLAY_SCALE]
    if pred.rio.crs != obs.rio.crs or pred.shape != obs.shape:
        pred = pred.rio.reproject_match(obs)
    diff = pred - obs

    imd_cmap = ListedColormap(
        ['#1a9641', '#a6d96a', '#ffffbf', '#fdae61', '#d7191c'])

    def show(ax, da, **kw):
        b = da.rio.bounds()
        im = ax.imshow(da.values, extent=(b[0], b[2], b[1], b[3]), **kw)
        ax.set_aspect('equal')
        ax.xaxis.set_major_locator(mticker.MaxNLocator(nbins=4))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=4))
        ax.tick_params(axis='both', labelsize=8)
        ax.set_xlabel('Easting [m]', fontsize=9)
        ax.set_ylabel('Northing [m]', fontsize=9)
        return im

    fig, ax = plt.subplots(2, 2, figsize=(15, 12),
                           gridspec_kw={'wspace': 0.25, 'hspace': 0.04})
    im1 = show(ax[0, 0], obs, cmap=imd_cmap, vmin=0, vmax=100)
    ax[0, 0].set_title('Observed IMD (CLMS 2018)',
                       fontweight='bold', fontsize=12)
    show(ax[0, 1], pred, cmap=imd_cmap, vmin=0, vmax=100)
    ax[0, 1].set_title('Predicted IMD (S2 percentile, RF)',
                       fontweight='bold', fontsize=12)
    im3 = show(ax[1, 0], diff, cmap='RdBu_r', vmin=-30, vmax=30)
    ax[1, 0].set_title('Difference (Predicted - Observed)',
                       fontweight='bold', fontsize=12)
    ax[1, 1].axis('off')

    fig.colorbar(im1, ax=ax[0, :], orientation='vertical',
                 fraction=0.025, pad=0.02, label='IMD (%)')
    fig.colorbar(im3, ax=ax[1, :], orientation='vertical',
                 fraction=0.025, pad=0.02, label='Pred - Obs (%)')

    # The label FIGURES.md asks for: a statement of what produced the panels,
    # not a conclusion about them.
    fig.suptitle('Figure 7 · Milan IMD, observed against predicted — '
                 'S2 percentile composite (p10/p25/p50/p75/p90), '
                 'random forest',
                 fontsize=13, fontweight='bold', y=0.94)

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_milan_raster_comparison.png')
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    d = diff.values.astype('float64')
    d = d[np.isfinite(d)]
    print('F15 · fig_milan_raster_comparison — inputs and difference summary')
    print(f'  observed  : {RASTER_OBS}')
    print(f'  predicted : {RASTER_PRED}')
    print(f'  decimation: every {DISPLAY_SCALE}nd pixel (display only)')
    print(f'  difference: mean {d.mean():+.2f}, sd {d.std():.2f}, '
          f'range {d.min():+.1f} to {d.max():+.1f} (pp, pred - obs)')
    print('  NOTE: raster-wide and city-wide; not the 1014-point holdout in '
          'Table A, and not quoted in the report.')
    print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


# ── F3 · spatial-vs-random CV inflation ──────────────────────────────────────
# A redraw of the notebook's fig06_inflation_heatmap.png, which FIGURES.md
# records as usable but which carries one row per TUNED model -- including a
# third estimator that is out of scope for this report and whose name the
# figure would render. Filtering the estimator out is the whole reason this
# rebuild exists.
#
# Redrawn from inflation_analysis.csv rather than by re-executing notebook 01,
# per CLAUDE.md: re-running the notebook would re-tune models and re-export
# rasters. The CSV is the tabular twin of the notebook figure, so the values
# are the notebook's; only the row filter and the labelling change.
INFLATION_CSV = 'outputs_v2/inflation_analysis.csv'
REPORTED_MODELS = ('RF', 'SVR')


def f3_values():
    """Inflation rows for the reported estimators, read from the run's CSV."""
    import csv

    path = os.path.join(REPO, INFLATION_CSV)
    if not os.path.exists(path):
        raise LookupError(
            f'{INFLATION_CSV} is missing; it is the tabular twin of the '
            'notebook inflation heatmap. Re-run notebook 01 rather than '
            'hardcoding the values.')
    with open(path, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))

    kept = [r for r in rows if r['Model'] in REPORTED_MODELS]
    if {r['Model'] for r in kept} != set(REPORTED_MODELS):
        raise LookupError(
            f'{INFLATION_CSV} does not carry rows for every reported '
            f'estimator {REPORTED_MODELS}; found '
            f'{sorted({r["Model"] for r in rows})}.')

    blocks = sorted({r['Block'] for r in kept}, key=lambda b: int(b[:-1]))
    return kept, blocks, len(rows) - len(kept)


def build_f3():
    kept, blocks, n_dropped = f3_values()

    by = {(r['Model'], r['Block']): r for r in kept}
    tuning = {r['Model']: r['Tuning_block'] for r in kept}

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.2))
    for ax, col, title, fmt in [
        (axes[0], 'RMSE_diff', 'ΔRMSE inflation (pp)', '.2f'),
        (axes[1], 'Pct_inflation', 'RMSE inflation (%)', '.1f'),
    ]:
        grid = np.array([[float(by[(m, b)][col]) for b in blocks]
                         for m in REPORTED_MODELS])
        # Symmetric limits about zero: the finding is that the values sit at
        # zero, and a sequential scale normalised to the data would paint a
        # 0.1 pp spread as though it were a gradient.
        lim = max(1.0, float(np.abs(grid).max()))
        im = ax.imshow(grid, cmap='RdBu_r', aspect='auto',
                       vmin=-lim, vmax=lim)
        ax.set_xticks(range(len(blocks)))
        ax.set_xticklabels(blocks)
        ax.set_yticks(range(len(REPORTED_MODELS)))
        ax.set_yticklabels(list(REPORTED_MODELS))
        ax.tick_params(axis='both', length=0)
        for i, m in enumerate(REPORTED_MODELS):
            for j, b in enumerate(blocks):
                ax.text(j, i, f'{grid[i, j]:{fmt}}', ha='center', va='center',
                        fontsize=10.5,
                        fontweight='bold' if b == tuning[m] else 'normal')
        ax.set_title(title, fontweight='bold')
        ax.set_xlabel('Spatial block size', fontsize=9)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)

    fig.suptitle('Figure 3 · Spatial against random cross-validation RMSE, '
                 'training set\n(bold = the block each model was tuned at)',
                 fontsize=13, fontweight='bold', y=1.10)
    fig.tight_layout()

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_cv_inflation.png')
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # ── Plotted values, for checking against the CSV ────────────────────────
    print('F3 · fig_cv_inflation — plotted values')
    print(f'  source: {INFLATION_CSV}')
    print(f'  {n_dropped} row(s) for estimators out of scope were filtered out '
          'before plotting')
    print('')
    print(f'{"model":>6s} {"block":>7s} {"random":>8s} {"spatial":>8s} '
          f'{"diff":>7s} {"pct":>7s}  tuned at')
    print('-' * 64)
    worst = 0.0
    for m in REPORTED_MODELS:
        for b in blocks:
            r = by[(m, b)]
            pct = float(r['Pct_inflation'])
            worst = max(worst, abs(pct))
            print(f'{m:>6s} {b:>7s} {float(r["Random_RMSE"]):8.2f} '
                  f'{float(r["Spatial_RMSE"]):8.2f} '
                  f'{float(r["RMSE_diff"]):+7.2f} {pct:+7.1f} '
                  f' {r["Tuning_block"] if b == r["Tuning_block"] else ""}')
    print('-' * 64)
    print(f'largest absolute inflation over the reported estimators: '
          f'{worst:.1f}%')
    print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


# ── F17 · Milan predictor-set ranking ────────────────────────────────────────
# Table 1 tabulates the four predictor sets on RMSE, MAE and R2; this shows the
# same four rows so the ranking is visible rather than only read off. The claim
# it supports is that the ordering is IDENTICAL on all three metrics, which is
# a statement about three columns at once and is exactly what a table makes the
# reader verify by eye.
#
# Built rather than taken from a notebook. figA_holdout_accuracy_* would have
# been the notebook candidate, but its left panel duplicates F4 and its right
# panel duplicates F5, and its title carries the wrong tuning block (see
# data/FIGURES.md).
RANK_METRICS = [
    ('RMSE', 'RMSE (IMD pp)',  'lower is better'),
    ('MAE',  'MAE (IMD pp)',   'lower is better'),
    ('R2',   'R²',        'higher is better'),
]


def f17_values():
    """The four Milan predictor sets on three metrics, read from FACTS.md."""
    rows = []
    for a_name, _ in PREDICTORS:
        rec = {'predictor': a_name}
        for key, _, _ in RANK_METRICS:
            rec[key] = facts_value(key, city='Milan', predictor_set=a_name,
                                   model='GEE_RF')
        rows.append(rec)
    # Rank on RMSE, best first. Ordering the bars by the result rather than by
    # band count is the point: the reader should see the ranking, not recover it.
    return sorted(rows, key=lambda r: r['RMSE'])


def build_f17():
    rows = f17_values()
    labels = [r['predictor'] for r in rows]
    colours = [CMAP[r['predictor']] for r in rows]
    y = np.arange(len(rows))[::-1]          # best at the top

    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.4))

    for ax, (key, xlabel, sense) in zip(axes, RANK_METRICS):
        vals = [r[key] for r in rows]
        ax.barh(y, vals, height=0.62, color=colours, linewidth=0, zorder=2)

        # Headroom for the value labels, and a floor at zero so bar LENGTH is
        # proportional to the value. A truncated axis would exaggerate the
        # spread, which is the whole quantity under discussion in 7.1.
        ax.set_xlim(0, max(vals) * 1.28)
        for yi, v in zip(y, vals):
            ax.annotate(f'{v:.3f}', xy=(v, yi), xytext=(4, 0),
                        textcoords='offset points', va='center', ha='left',
                        fontsize=8.5, fontweight='bold')

        ax.set_yticks(y)
        ax.set_yticklabels(labels if ax is axes[0] else [], fontsize=9)
        ax.set_xlabel(f'{xlabel}  ({sense})', fontsize=9)
        ax.tick_params(axis='both', labelsize=8, length=0)
        ax.set_axisbelow(True)
        ax.grid(axis='x', color='#ececec', zorder=0)
        for side in ('left', 'bottom'):
            ax.spines[side].set_color(REF_GREY)

    axes[0].set_title('Ranked on RMSE, best at top', fontsize=9.5,
                      fontweight='bold', loc='left')

    fig.suptitle('Figure 5 · Milan predictor sets on the spatial holdout '
                 '(GEE random forest, n = 1 014, vs CLMS)',
                 fontsize=13, fontweight='bold', y=1.03)
    fig.tight_layout()

    os.makedirs(FIGS, exist_ok=True)
    path = os.path.join(FIGS, 'fig_milan_predictor_ranking.png')
    fig.savefig(path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)

    # ── Plotted values, for checking against FACTS.md ───────────────────────
    print('F17 · fig_milan_predictor_ranking — plotted values')
    print(f'{"predictor":24s} {"RMSE":>9s} {"MAE":>9s} {"R2":>9s}')
    print('-' * 54)
    for r in rows:
        print(f'{r["predictor"]:24s} {r["RMSE"]:9.3f} {r["MAE"]:9.3f} '
              f'{r["R2"]:9.3f}')
    print('-' * 54)
    order = {k: [r['predictor'] for r in
                 sorted(rows, key=lambda x: x[k], reverse=(k == 'R2'))]
             for k, _, _ in RANK_METRICS}
    same = len({tuple(v) for v in order.values()}) == 1
    print(f'ordering identical on RMSE, MAE and R2: {same}')
    if not same:
        for k, v in order.items():
            print(f'  {k}: {v}')
    print('')
    print(f'Saved {os.path.relpath(path, REPO)}')
    return path


FIGURES = {'F1': build_f1, 'F3': build_f3, 'F12': build_f12,
           'F13': build_f13, 'F14': build_f14, 'F15': build_f15,
           'F17': build_f17}


def main():
    want = [a.upper() for a in sys.argv[1:]] or list(FIGURES)
    unknown = [w for w in want if w not in FIGURES]
    if unknown:
        raise SystemExit(f'Not built yet: {unknown}. Available: '
                         f'{sorted(FIGURES)}')
    for name in want:
        FIGURES[name]()


if __name__ == '__main__':
    main()
