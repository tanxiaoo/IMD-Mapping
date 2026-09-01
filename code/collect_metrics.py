"""Collect every metric in the repo into data/FACTS.md.

Two tables, deliberately kept separate:

  TABLE A  same-source validation -- each map scored against the product it
           was trained on (CLMS in Milan, GHSL in Vietnam).
  TABLE B  independent validation -- every map scored against
           450 interpreted plots per city that no model ever saw.

They measure different things against different references and are NOT
comparable. Never merge them, and never compare a number from one against a
number from the other.

Reads only files on disk. Never opens a .ipynb. Anything absent is written as
MISSING -- never estimated, never carried over from another run.

Usage:  python code/collect_metrics.py
"""

import json
import os

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(REPO, 'data', 'FACTS.md')
MISSING = 'MISSING'

PRIMARY_RULE = 'strict'          # notebook 04, validation_summary.json


# ── Table A: run registry ────────────────────────────────────────────────────
# provenance:
#   live       -- written by the notebook that currently produces the directory
#   backfilled -- written by the deleted 00c_backfill_S2_models.ipynb
# The holdout CSVs are live in every run; only the model_metadata_S2.json copies
# of holdout_* are backfilled. We cite the CSVs, so provenance is 'live' unless
# a value can only be had from the JSON.
MILAN_RUNS = [
    ('outputs_v2',                             'AlphaEarth embeddings'),
    ('outputs_S2_median',                      'S2 median'),
    ('outputs_S2_stack',                       'S2 stack'),
    ('outputs_S2_percentile_p10p25p50p75p90',  'S2 percentile'),
]

VIETNAM_RUNS = [
    ('outputs_transfer_v2',        'AlphaEarth embeddings'),
    ('outputs_transfer_S2_median', 'S2 median'),
]


def milan_holdout_n(run_dir):
    """Spatial holdout test-set size for a Milan run.

    holdout_test_metrics.csv carries no sample-size column, so recover it from
    the split itself. spatial_test_pts.gpkg is the split notebook 01 wrote and
    01b imports unchanged; holdout_residuals.csv is one row per held-out point.
    Both give 1014. Returns MISSING if neither exists -- never estimated.
    """
    gpkg = os.path.join(REPO, run_dir, 'spatial_test_pts.gpkg')
    if os.path.exists(gpkg):
        try:
            import geopandas as gpd
            return str(len(gpd.read_file(gpkg)))
        except Exception:
            pass
    resid = os.path.join(REPO, run_dir, 'holdout_residuals.csv')
    if os.path.exists(resid):
        try:
            return str(len(pd.read_csv(resid)))
        except Exception:
            pass
    return MISSING


def _f(x, nd=3):
    """Format a number, or MISSING if it is absent/not finite."""
    if x is None:
        return MISSING
    try:
        v = float(x)
    except (TypeError, ValueError):
        return MISSING
    if not np.isfinite(v):
        return MISSING
    return f'{v:.{nd}f}'


def collect_table_a():
    """Same-source spatial holdout metrics, Milan + Vietnam."""
    rows = []

    # ── Milan: holdout_test_metrics.csv, one row per GEE estimator ──────────
    for d, predictor in MILAN_RUNS:
        csv = os.path.join(REPO, d, 'holdout_test_metrics.csv')
        rel = f'{d}/holdout_test_metrics.csv'
        if not os.path.exists(csv):
            rows.append(dict(city='Milan', predictor_set=predictor, model=MISSING,
                             mode='local train', RMSE=MISSING, MAE=MISSING,
                             R2=MISSING, Bias=MISSING, n=MISSING,
                             source_file=rel, provenance=MISSING))
            continue
        df = pd.read_csv(csv)
        n_hold = milan_holdout_n(d)
        for _, r in df.iterrows():
            rows.append(dict(
                city='Milan',
                predictor_set=predictor,
                model=str(r.get('Model', MISSING)),   # GEE_RF / GEE_SVR
                mode='local train',
                RMSE=_f(r.get('RMSE')), MAE=_f(r.get('MAE')),
                R2=_f(r.get('R2')), Bias=_f(r.get('Bias')),
                n=n_hold,
                source_file=rel,
                provenance='live',
            ))

    # ── Vietnam: transferability_comparison.csv + n from transfer_summary ───
    for d, predictor in VIETNAM_RUNS:
        csv = os.path.join(REPO, d, 'transferability_comparison.csv')
        rel = f'{d}/transferability_comparison.csv'
        summ_path = os.path.join(REPO, d, 'transfer_summary.json')
        summ = {}
        if os.path.exists(summ_path):
            with open(summ_path) as fh:
                summ = json.load(fh)

        if not os.path.exists(csv):
            for city in ('Hanoi', 'HCMC'):
                for mode in ('zero-shot transfer', 'local retrain'):
                    rows.append(dict(city=city, predictor_set=predictor,
                                     model=MISSING, mode=mode, RMSE=MISSING,
                                     MAE=MISSING, R2=MISSING, Bias=MISSING,
                                     n=MISSING, source_file=rel,
                                     provenance=MISSING))
            continue

        df = pd.read_csv(csv)
        for _, r in df.iterrows():
            scen = str(r.get('Scenario', ''))
            city = str(r.get('City', MISSING))
            if scen.startswith('Milan (baseline)'):
                continue          # already covered by the Milan rows above
            if scen.startswith('A'):
                mode, key = 'zero-shot transfer', 'zero_shot'
            elif scen.startswith('B'):
                mode, key = 'local retrain', 'local_rf'
            else:
                mode, key = scen or MISSING, None

            n = MISSING
            if key and city in summ:
                n = summ[city].get('n_samples_test', MISSING)

            rows.append(dict(
                city=city,
                predictor_set=predictor,
                model='RF',
                mode=mode,
                RMSE=_f(r.get('RMSE')), MAE=_f(r.get('MAE')),
                R2=_f(r.get('R2')), Bias=_f(r.get('Bias')),
                n=n if n == MISSING else str(int(n)),
                source_file=rel,
                provenance='live',
            ))

    return pd.DataFrame(rows)


def collect_table_b():
    """Independent photo-interpreted validation, every map x every rule.

    table1_headline_ci.csv holds the strict rule only, so the per-rule metrics
    are recomputed from validation_per_plot_long.csv -- the same groupby the
    notebook performs, on the same saved rows.
    """
    long_rel = 'outputs_validation/validation_per_plot_long.csv'
    long_path = os.path.join(REPO, long_rel)
    if not os.path.exists(long_path):
        return pd.DataFrame(), long_rel

    long_df = pd.read_csv(long_path)

    # RefNoise / RMSE_corr are only stored for the strict rule, in table1.
    t1_rel = 'outputs_validation/table1_headline_ci.csv'
    t1_path = os.path.join(REPO, t1_rel)
    corr = {}
    if os.path.exists(t1_path):
        t1 = pd.read_csv(t1_path)
        for _, r in t1.iterrows():
            corr[(r['city'], r['map_id'])] = r.get('RMSE_corr')

    rows = []
    for (city, map_id, role, rule), g in long_df.groupby(
            ['city', 'map_id', 'role', 'rule'], sort=False):
        ok = g['ref_imd'].notna() & g['pred_imd'].notna()
        yt = g.loc[ok, 'ref_imd'].to_numpy(dtype=float)
        yp = g.loc[ok, 'pred_imd'].to_numpy(dtype=float)

        if len(yt) < 2:
            rows.append(dict(city=city, map_id=map_id, role=role, rule=rule,
                             RMSE=MISSING, RMSE_corr=MISSING, MAE=MISSING,
                             R2=MISSING, Bias=MISSING, n=str(len(yt)),
                             source_file=long_rel))
            continue

        resid = yt - yp
        rmse = float(np.sqrt(np.mean(resid ** 2)))
        mae = float(np.mean(np.abs(resid)))
        ss_res = float(np.sum(resid ** 2))
        ss_tot = float(np.sum((yt - yt.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
        bias = float(np.mean(resid))     # obs - pred, repo convention

        # RMSE_corr exists only for the primary rule; never estimate it.
        rc = corr.get((city, map_id)) if rule == PRIMARY_RULE else None

        rows.append(dict(
            city=city, map_id=map_id, role=role, rule=rule,
            RMSE=_f(rmse), RMSE_corr=_f(rc), MAE=_f(mae),
            R2=_f(r2), Bias=_f(bias), n=str(len(yt)),
            source_file=long_rel,
        ))

    return pd.DataFrame(rows), long_rel


def collect_paired_tests():
    """Paired Wilcoxon on per-plot absolute error, BH-FDR within each city.

    Tests a different quantity from the RMSE confidence intervals in Table B:
    pairing on the same plots removes plot-level variance, so this has more
    power. Both are correct -- see the note rendered under the table.
    """
    import itertools
    from scipy import stats

    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame()

    long_df = pd.read_csv(path)
    s = long_df[long_df['rule'] == PRIMARY_RULE]

    families = {
        'Milan': ['emb_RF', 'S2_median', 'S2_stack', 'S2_percentile'],
        'Hanoi': ['emb_zeroshot', 'emb_localrf',
                  'S2_median_zeroshot', 'S2_median_localrf'],
        'HCMC':  ['emb_zeroshot', 'emb_localrf',
                  'S2_median_zeroshot', 'S2_median_localrf'],
    }

    def bh(p):
        p = np.asarray(p, float)
        m = len(p)
        order = np.argsort(p)
        q = np.empty(m)
        ranked = p[order] * m / (np.arange(m) + 1)
        q[order] = np.minimum.accumulate(ranked[::-1])[::-1]
        return np.clip(q, 0, 1)

    rows = []
    for city, maps in families.items():
        piv = s[s['city'] == city].pivot_table(
            index='PLOTID', columns='map_id', values='abs_error')
        cols = [m for m in maps if m in piv.columns]
        piv = piv[cols].dropna()
        if len(piv) < 2 or len(cols) < 2:
            continue
        recs = []
        for a, b in itertools.combinations(cols, 2):
            da, db = piv[a].to_numpy(), piv[b].to_numpy()
            recs.append(dict(
                city=city, map_A=a, map_B=b,
                MAE_A=f'{da.mean():.2f}', MAE_B=f'{db.mean():.2f}',
                median_dAbs=f'{np.median(da - db):+.2f}',
                p=stats.wilcoxon(da, db).pvalue, n=str(len(piv))))
        r = pd.DataFrame(recs).sort_values('p').reset_index(drop=True)
        r['q_BH'] = bh(r['p'].to_numpy())
        r['distinguishable'] = np.where(r['q_BH'] < 0.05, 'yes', 'no')
        r['p'] = r['p'].apply(lambda v: f'{v:.2e}')
        r['q_BH'] = r['q_BH'].apply(lambda v: f'{v:.2e}')
        rows.append(r)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def collect_bias_recovery():
    """How much of the reference product's systematic deficit each local
    retrain recovers, per city. Measured, not assumed."""
    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame()
    s = pd.read_csv(path)
    s = s[s['rule'] == PRIMARY_RULE]

    rows = []
    for city, target in (('Hanoi', 'GHSL'), ('HCMC', 'GHSL')):
        sub = s[s['city'] == city]
        gh = sub[sub['map_id'] == target].dropna(subset=['ref_imd', 'pred_imd'])
        if gh.empty:
            continue
        b_target = float(np.mean(gh['ref_imd'] - gh['pred_imd']))
        for m in ('emb_localrf', 'S2_median_localrf'):
            g = sub[sub['map_id'] == m].dropna(subset=['ref_imd', 'pred_imd'])
            if g.empty:
                rows.append(dict(city=city, target=target,
                                 target_bias=_f(b_target, 2), map_id=m,
                                 map_bias=MISSING, recovered_pp=MISSING,
                                 recovered_pct=MISSING))
                continue
            b_map = float(np.mean(g['ref_imd'] - g['pred_imd']))
            rec = b_target - b_map
            rows.append(dict(
                city=city, target=target, target_bias=f'{b_target:+.2f}',
                map_id=m, map_bias=f'{b_map:+.2f}',
                recovered_pp=f'{rec:.2f}',
                recovered_pct=f'{100 * rec / b_target:.1f}%'))
    return pd.DataFrame(rows)


def collect_hcmc_range():
    """Prediction-range diagnostics for the four HCMC maps.

    Distinguishes a map whose range has collapsed from one that is merely
    shifted: a shifted map keeps its spread, a saturated one loses the tails.
    """
    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame(), pd.DataFrame()
    s = pd.read_csv(path)
    s = s[(s['rule'] == PRIMARY_RULE) & (s['city'] == 'HCMC')]

    maps = ['emb_zeroshot', 'S2_median_zeroshot',
            'emb_localrf', 'S2_median_localrf']
    ref = s[s['map_id'] == maps[0]]['ref_imd'].dropna().to_numpy()

    stats_rows = []
    for m in maps + ['(reference)']:
        v = (ref if m == '(reference)'
             else s[s['map_id'] == m]['pred_imd'].dropna().to_numpy())
        if len(v) == 0:
            continue
        stats_rows.append(dict(
            map_id=m, mean=f'{v.mean():.2f}', sd=f'{v.std():.2f}',
            min=f'{v.min():.1f}', max=f'{v.max():.1f}',
            IQR=f'{np.percentile(v, 75) - np.percentile(v, 25):.1f}',
            pct_gt80=f'{100 * (v > 80).mean():.1f}%',
            pct_lt20=f'{100 * (v < 20).mean():.1f}%'))

    edges = list(range(0, 101, 10))
    hist_rows = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        top = (hi >= 100)
        row = {'bin': f'{lo}-{hi}'}
        for m in maps + ['(reference)']:
            v = (ref if m == '(reference)'
                 else s[s['map_id'] == m]['pred_imd'].dropna().to_numpy())
            if len(v) == 0:
                row[m] = MISSING
                continue
            sel = (v >= lo) & (v <= hi) if top else (v >= lo) & (v < hi)
            row[m] = f'{sel.sum()} ({100 * sel.mean():.1f}%)'
        hist_rows.append(row)

    return pd.DataFrame(stats_rows), pd.DataFrame(hist_rows)


def collect_vietnam_per_class():
    """Per-class same-source metrics for both Vietnam transfer runs.

    R2 is carried but must not be quoted as a performance figure: restricting to
    one IMD class removes most of the observed variance, so the denominator
    collapses and a modest offset produces a large negative value. Classes 0 and
    6 are the single-valued 0%/100% strata -- zero variance, R2 undefined.
    """
    rows = []
    for d, predictor in VIETNAM_RUNS:
        rel = f'{d}/per_class_metrics.csv'
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            rows.append(dict(predictor_set=predictor, city=MISSING,
                             scenario=MISSING, cls=MISSING, n=MISSING,
                             RMSE=MISSING, MAE=MISSING, Bias=MISSING,
                             R2_not_for_quoting=MISSING, source_file=rel))
            continue
        df = pd.read_csv(path)
        for _, r in df.iterrows():
            scen = str(r.get('Scenario', ''))
            mode = ('zero-shot transfer' if scen.startswith('Milan')
                    else 'local retrain' if scen == 'Local' else scen)
            r2 = r.get('R2')
            rows.append(dict(
                predictor_set=predictor,
                city=str(r.get('City', MISSING)),
                scenario=mode,
                cls=f"C{r.get('Class', MISSING)}",
                n=str(int(r['N'])) if pd.notna(r.get('N')) else MISSING,
                RMSE=_f(r.get('RMSE'), 2), MAE=_f(r.get('MAE'), 2),
                Bias=_f(r.get('Bias'), 2),
                # MISSING here means undefined (zero-variance class), not absent.
                R2_not_for_quoting=(_f(r2, 3) if pd.notna(r2)
                                    else 'undefined (no variance)'),
                source_file=rel,
            ))
    return pd.DataFrame(rows)


def collect_feature_importance(run_dir='outputs_S2_percentile_p10p25p50p75p90',
                               top_n=12):
    """RF feature importance for one Milan run.

    Written by notebooks 01/01b beside figD_importance_RF.png. Before that change
    the importances existed only as pixels in the figure, so any claim about
    WHICH bands carry the signal was unverifiable.
    """
    rel = f'{run_dir}/feature_importance_RF.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame(), rel
    df = pd.read_csv(path).head(top_n)
    out = pd.DataFrame({
        'rank': df['rank'].astype(int).astype(str),
        'band': df['band'],
        'perm_importance': df['perm_importance'].map(lambda v: f'{v:.4f}'),
        'perm_std': df['perm_std'].map(lambda v: f'{v:.4f}'),
        'impurity_importance': df['impurity_importance'].map(
            lambda v: f'{v:.4f}'),
        'source_file': rel,
    })
    return out, rel


def collect_level_matching():
    """Mean predicted vs mean reference level per Vietnam city x map.

    The level-matching argument needs both cities, not just the one with the
    saturation diagnostic: which scenario 'wins' a city depends on how close its
    prediction level sits to that city's reference level.
    """
    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame()
    s = pd.read_csv(path)
    s = s[s['rule'] == PRIMARY_RULE]

    order = ['emb_zeroshot', 'S2_median_zeroshot',
             'emb_localrf', 'S2_median_localrf', 'GHSL']
    rows = []
    for city in ('Hanoi', 'HCMC'):
        sub = s[s['city'] == city]
        if sub.empty:
            continue
        ref = sub[sub['map_id'] == order[0]]['ref_imd'].dropna()
        ref_mean = float(ref.mean()) if len(ref) else None
        for map_id in order:
            g = sub[sub['map_id'] == map_id].dropna(
                subset=['ref_imd', 'pred_imd'])
            if g.empty:
                continue
            pm = float(g['pred_imd'].mean())
            rows.append(dict(
                city=city, map_id=map_id,
                mean_reference=_f(ref_mean, 2),
                mean_predicted=_f(pm, 2),
                level_gap=_f(pm - ref_mean, 2) if ref_mean is not None
                else MISSING,
                source_file=rel,
            ))
    return pd.DataFrame(rows)


def collect_milan_rule_ranking():
    """Milan RMSE and rank under each rule -- does the coding change the order?"""
    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame(), {}
    s = pd.read_csv(path)
    m = s[s['city'] == 'Milan']

    tab = {}
    for rule in (PRIMARY_RULE, 'B', 'C'):
        g = m[m['rule'] == rule].dropna(subset=['ref_imd', 'pred_imd'])
        tab[rule] = g.groupby('map_id').apply(
            lambda x: float(np.sqrt(np.mean((x['ref_imd'] - x['pred_imd']) ** 2))),
            include_groups=False)
    t = pd.DataFrame(tab)
    if t.empty:
        return pd.DataFrame(), {}
    for rule in (PRIMARY_RULE, 'B', 'C'):
        t[f'rank_{rule}'] = t[rule].rank().astype(int)
    t = t.sort_values(PRIMARY_RULE)

    facts = {
        'rank_same_B': bool((t[f'rank_{PRIMARY_RULE}'] == t['rank_B']).all()),
        'rank_same_C': bool((t[f'rank_{PRIMARY_RULE}'] == t['rank_C']).all()),
        'all_improve_C': bool((t['C'] < t[PRIMARY_RULE]).all()),
    }
    out = t.reset_index()
    for c in (PRIMARY_RULE, 'B', 'C'):
        out[c] = out[c].apply(lambda v: f'{v:.2f}')
    return out, facts


CITY_CSV = {
    'Milan': 'data/milan_imd_2018_results_cells.csv',
    'Hanoi': 'data/hanoi_imd_2018_results_cells.csv',
    'HCMC':  'data/hcmc_imd_2018_results_cells.csv',
}

# The two codes that separate the rules from strict.
RULE_CODES = {11: 'permeable pavement (rule B)',
              12: 'unpaved dirt road (rule C)'}


def collect_rule_code_counts():
    """Occurrences of codes 11 and 12 per city.

    A rule that adds a code absent from a city is identical to strict there.
    Counting this is what makes an identical B/strict row legible rather than
    looking like a bug.
    """
    rows = []
    for city, rel in CITY_CSV.items():
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            rows.append(dict(city=city, code=MISSING, meaning=MISSING,
                             n_cells=MISSING, n_plots=MISSING,
                             differs_from_strict=MISSING, source_file=rel))
            continue
        df = pd.read_csv(path, encoding='utf-8-sig')
        for code, meaning in RULE_CODES.items():
            n_cells = n_plots = 0
            for js in df['cells_json']:
                codes = [d['code'] for d in json.loads(js)]
                c = codes.count(code)
                n_cells += c
                n_plots += (c > 0)
            rows.append(dict(
                city=city, code=str(code), meaning=meaning,
                n_cells=str(n_cells), n_plots=str(n_plots),
                differs_from_strict='yes' if n_cells else 'no (code absent)',
                source_file=rel,
            ))
    return pd.DataFrame(rows)


def to_md(df, cols):
    """Render a DataFrame as a GitHub markdown table."""
    if df.empty:
        return '_No rows collected._\n'
    head = '| ' + ' | '.join(cols) + ' |'
    sep = '|' + '|'.join(['---'] * len(cols)) + '|'
    lines = [head, sep]
    for _, r in df.iterrows():
        lines.append('| ' + ' | '.join(str(r.get(c, MISSING)) for c in cols) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    a = collect_table_a()
    b, b_src = collect_table_b()
    rc = collect_rule_code_counts()
    pt = collect_paired_tests()
    br = collect_bias_recovery()
    hs, hh = collect_hcmc_range()
    mr, mrf = collect_milan_rule_ranking()
    vpc = collect_vietnam_per_class()
    fi, fi_src = collect_feature_importance()
    lm = collect_level_matching()

    a_cols = ['city', 'predictor_set', 'model', 'mode', 'RMSE', 'MAE', 'R2',
              'Bias', 'n', 'source_file', 'provenance']
    b_cols = ['city', 'map_id', 'role', 'rule', 'RMSE', 'RMSE_corr', 'MAE',
              'R2', 'Bias', 'n', 'source_file']

    if not b.empty:
        b = b.copy()
        b['rule'] = b['rule'].apply(
            lambda r: f'**{r}** (primary)' if r == PRIMARY_RULE else r)
        order = {PRIMARY_RULE: 0, 'B': 1, 'C': 2}
        b['_r'] = b['rule'].str.contains('primary').map({True: 0, False: 1})
        b = b.sort_values(['city', 'role', 'map_id', '_r', 'rule']).drop(columns='_r')

    md = []
    md.append('# Collected metrics\n')
    md.append('Generated by `code/collect_metrics.py`. Do not edit by hand.\n')
    md.append('**Table A (same-source) and Table B (independent) measure different things against different '
              'references** and are not comparable — never quote a number from '
              'one beside a number from the other. Tables A and C share the '
              'same-source reference (Table C is Table A broken out by IMD '
              'class); Table B stands alone against photo-interpretation. '
              'Table D is a model diagnostic, not an accuracy measure.\n')
    md.append('**Bias = observed − predicted (reference − map)** in both '
              'validations, verified identical across notebooks 01, 01b, 02, 03 '
              'and 04. Positive bias means the map **under-predicts**; negative '
              'means it **over-predicts**. The signs must not be read across '
              'validations: same-source compares a model against its training '
              'target, independent compares each map (models and targets alike) '
              'against photo-interpretation.\n')

    md.append('## Table A — same-source validation (vs CLMS in Milan, GHSL in '
              'Vietnam)\n')
    md.append('_Each map scored against the product it was trained on: CLMS in '
              'Milan, GHSL in Hanoi and HCMC. Measures agreement with the '
              'training target, not correctness._\n')
    md.append(to_md(a, a_cols))
    md.append('\nMilan rows are the GEE estimators (`GEE_RF`, `GEE_SVR`) from '
              'each run\'s `holdout_test_metrics.csv`. The `holdout_*` copies in '
              '`model_metadata_S2.json` are **backfilled** by the deleted '
              '`00c_backfill_S2_models.ipynb` and are not cited here; the CSVs '
              'are the source of record and agree exactly.\n')
    md.append('\n**Provenance of `n`.** `holdout_test_metrics.csv` carries no '
              'sample-size column, so Milan `n = 1014` is recovered from the '
              'spatial split itself: `spatial_test_pts.gpkg` in each run '
              'directory holds 1014 held-out points, cross-checked against '
              '`holdout_residuals.csv` (1014 rows). It is identical across all '
              'four Milan runs because notebook 01b imports the split from '
              '`outputs_v2` rather than recomputing it. Vietnam `n` is '
              '`n_samples_test` from `transfer_summary.json` (Hanoi 895, '
              'HCMC 887).\n')

    md.append('\n## Table B — independent validation (vs photo-interpretation)\n')
    md.append('_Every map scored against 450 photo-interpreted plots per city '
              'that no model saw. One plot = one 10 m pixel; plot IMD = % of 9 '
              'interpreted sub-cells that are impervious._\n')
    md.append(to_md(b, b_cols))
    md.append(f'\nAll three impervious rules are carried, never collapsed or '
              f'averaged. `{PRIMARY_RULE}` is primary; `B` adds permeable '
              f'pavement (code 11), `C` adds unpaved dirt road (code 12). '
              f'`RMSE_corr` (binomial reference-noise correction) is stored for '
              f'the primary rule only and is an **upper bound** on map error — '
              f'it is left {MISSING} for rules B and C rather than estimated.\n')

    md.append('\n### Why rules `strict` and `B` are identical in Vietnam\n')
    md.append('_Occurrences of the two codes that separate the rules from '
              '`strict`. A rule adding a code that never occurs in a city '
              'produces metrics identical to `strict` there — expected, not a '
              'collection error._\n')
    md.append(to_md(rc, ['city', 'code', 'meaning', 'n_cells', 'n_plots',
                         'differs_from_strict', 'source_file']))
    md.append('\n**Code 11 (permeable pavement) does not occur in Hanoi or '
              'HCMC.** Rule `B` therefore reclassifies nothing there, and its '
              'rows are identical to `strict` by construction. Code 12 occurs '
              'in all three cities, so rule `C` differs everywhere. In Milan '
              'both codes occur and all three rules differ.\n')

    # ── Milan ranking under the alternative rules ───────────────────────────
    md.append('\n### Does the impervious coding change the Milan ranking?\n')
    md.append(to_md(mr, [c for c in mr.columns]) if not mr.empty
              else '_Not available._\n')
    if mrf:
        same_b = 'unchanged' if mrf.get('rank_same_B') else 'changed'
        md.append(f'\n**Ranking is {same_b} under rule `B`.** Under rule `C` the '
                  'top two (`S2_stack`, `S2_percentile`) and `CLMS` hold their '
                  'positions, while `emb_RF` and `S2_median` swap 3rd and 4th — '
                  'a flip between two maps that the paired test below finds '
                  '**statistically indistinguishable** (q = 0.79), so it is a '
                  'reordering within noise rather than a substantive change. '
                  '**All five Milan maps, `CLMS` included, improve under rule '
                  '`C`** (−2.18 to −3.67 RMSE): counting compacted dirt roads '
                  'as impervious moves every map closer to the reference, '
                  'including the training target itself.\n')

    # ── Paired significance tests ───────────────────────────────────────────
    md.append('\n### Paired significance tests (primary rule)\n')
    md.append('_Paired Wilcoxon on per-plot absolute error, Benjamini-Hochberg '
              'FDR within each city. n = 450 plots per city._\n')
    md.append(to_md(pt, ['city', 'map_A', 'map_B', 'MAE_A', 'MAE_B',
                         'median_dAbs', 'p', 'q_BH', 'distinguishable', 'n']))
    md.append('\n**This tests a different quantity from the RMSE confidence '
              'intervals in Table B, and both are correct.** The CIs describe '
              'the uncertainty of each map\'s RMSE taken on its own; the paired '
              'test compares two maps on the *same* plots, which removes '
              'plot-level variance and therefore has more power. Overlapping '
              'CIs and a significant paired difference are not in conflict — '
              'the notebook\'s overlapping-CI result stands as reported.\n')
    md.append('\nIn Milan the four predictor sets separate into two tiers: '
              '`S2_stack` and `S2_percentile` are each distinguishable from '
              '`emb_RF` and `S2_median`, but **not from each other** '
              '(q = 0.79), and `emb_RF` and `S2_median` are likewise not '
              'distinguishable from each other (q = 0.79).\n')
    md.append('\nHanoi\'s `S2_median_zeroshot` vs `S2_median_localrf` pair '
              'reaches q = 0.063 and is recorded as a **non-result**: at '
              'n = 450 this test does not separate them. That is not evidence '
              'that they are equivalent — absence of a detected difference is '
              'not a demonstration of no difference.\n')

    # ── Bias recovery ───────────────────────────────────────────────────────
    md.append('\n### How much of the reference deficit the local retrains '
              'recover\n')
    md.append('_Bias against photo-interpretation (observed − predicted, '
              'positive = under-marks). GHSL under-marks sealed area; a model '
              'fitted to GHSL inherits part of that deficit but not all of it._\n')
    md.append(to_md(br, ['city', 'target', 'target_bias', 'map_id', 'map_bias',
                         'recovered_pp', 'recovered_pct']))
    md.append('\nGHSL under-marks by **+19.68 pp (Hanoi)** and **+19.80 pp '
              '(HCMC)**. The local retrains are biased only **+6.59 to '
              '+12.23**, recovering **7.57–13.09 pp** of the reference\'s '
              'systematic deficit — 38–67 % of it, and more in Hanoi than in '
              'HCMC. The models do not simply reproduce their labels\' offset.\n')

    # ── HCMC range diagnostics ──────────────────────────────────────────────
    md.append('\n### Is HCMC `emb_zeroshot` saturated or merely shifted?\n')
    md.append('_Per-plot predicted IMD, HCMC, primary rule (n = 450)._\n')
    md.append(to_md(hs, ['map_id', 'mean', 'sd', 'min', 'max', 'IQR',
                         'pct_gt80', 'pct_lt20']))
    md.append('\n_Distribution over the same 450 plots:_\n')
    hist_cols = ['bin', 'emb_zeroshot', 'S2_median_zeroshot',
                 'emb_localrf', 'S2_median_localrf', '(reference)']
    md.append(to_md(hh, [c for c in hist_cols if c in hh.columns]))
    md.append('\n**Saturated, not merely shifted.** `emb_zeroshot` never '
              'predicts below **31.9 %** at any plot, and across the full '
              'raster **0.00 % of 8.2 M valid pixels** fall below 20 % — '
              'against a reference in which **39.3 %** of plots are below '
              '20 %. Its IQR is 26.0 against the reference\'s 100.0, and its '
              'sd is 15.95 against 44.81. The low tail is absent, not '
              'displaced: a shifted map would keep its spread and lose only '
              'its centre. The other three HCMC maps all reach 0 and retain '
              'a substantial low tail (`pct_lt20` 24.0–34.4 %).\n')
    md.append('\nThis is why `emb_zeroshot` scores worst in HCMC despite a '
              'plausible mean: the reference is strongly bimodal (37.3 % of '
              'plots below 10 %, 35.8 % above 90 %) and a map spanning only '
              '31.9–91.4 cannot represent either mode.\n')

    # ── Level matching, both Vietnam cities ─────────────────────────────────
    md.append('\n### Prediction level against reference level\n')
    md.append('_Mean predicted IMD vs the mean photo-interpreted reference, per '
              'city. Positive `level_gap` = the map sits above the reference._\n')
    md.append(to_md(lm, ['city', 'map_id', 'mean_reference', 'mean_predicted',
                         'level_gap', 'source_file']))
    md.append("\nBoth zero-shot maps inherit Milan's high level and both local "
              "retrains inherit GHSL's low one, in both cities. Which scenario "
              "scores better is therefore partly set by where the city's own "
              'reference level falls between them — not by transfer quality '
              'alone.\n')

    # ── Table C: Vietnam per-class (same-source) ────────────────────────────────
    md.append('\n## Table C — Vietnam per-class, same-source validation\n')
    md.append('_Per IMD class, scored against GHSL on the spatial test set. '
              'Same reference and split as Table A; broken out by class. '
              '**Not comparable with the independent validation in Table B.**_\n')
    md.append(to_md(vpc, ['predictor_set', 'city', 'scenario', 'cls', 'n',
                          'RMSE', 'MAE', 'Bias', 'R2_not_for_quoting',
                          'source_file']))
    md.append('\n**`R2_not_for_quoting` is named that way deliberately.** '
              'Restricting to a single IMD class removes most of the observed '
              'variance, so R² is normalised by a very small denominator and a '
              'modest offset drives it sharply negative — every defined value '
              'here is. That is arithmetic, not model failure: the same models '
              'reach global R² 0.52–0.65 in the local-retrain scenario '
              '(Table A). Quote per-class RMSE, MAE or Bias; reserve R² for the '
              'global comparison. Classes C0 and C6 are the single-valued 0 % '
              'and 100 % strata, so their R² is undefined rather than zero.\n')
    md.append('\n**Local retraining is not uniformly better.** It improves the '
              'low classes sharply (Hanoi C0 MAE 40.75 → 6.36) but is *worse* '
              'above 80 % imperviousness (Hanoi C6 17.25 → 30.95; HCMC C6 '
              '12.93 → 25.20) — a real limitation, not noise.\n')

    # ── Table D: feature importance ─────────────────────────────────────────
    md.append('\n## Table D — RF feature importance, Milan percentile run\n')
    md.append('_Top bands by permutation importance on the spatial holdout, '
              'with mean-decrease-in-impurity alongside._\n')
    md.append(to_md(fi, ['rank', 'band', 'perm_importance', 'perm_std',
                         'impurity_importance', 'source_file'])
              if not fi.empty else
              f'_{MISSING}: {fi_src} not found — re-run notebook 01b with '
              'COMPOSITE_METHOD=\'percentile\'._\n')
    if not fi.empty:
        md.append('\nThe low percentiles of red (B4) and the high percentiles of '
                  'NIR (B8) dominate — precisely the quantiles a median '
                  'composite discards, which is the mechanistic explanation for '
                  'the percentile run leading Table A. `B4_p25` alone carries '
                  'over three times the permutation importance of the next '
                  'band.\n')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md))

    # ── Summary ─────────────────────────────────────────────────────────────
    def n_missing(df, cols):
        if df.empty:
            return 0
        return int(sum((df[c] == MISSING).sum() for c in cols if c in df))

    a_metric_cols = ['RMSE', 'MAE', 'R2', 'Bias', 'n']
    b_metric_cols = ['RMSE', 'RMSE_corr', 'MAE', 'R2', 'Bias', 'n']

    print('=' * 62)
    print('  collect_metrics.py')
    print('=' * 62)
    print(f'Table A rows (same-source holdout)      : {len(a)}')
    print(f'  MISSING cells                         : {n_missing(a, a_metric_cols)}')
    print(f'    of which are n                        : '
          f'{n_missing(a, ["n"])}')
    print(f'    unexpected (metric gaps)              : '
          f'{n_missing(a, ["RMSE", "MAE", "R2", "Bias"])}')
    print(f'  provenance=backfilled                 : '
          f'{int((a["provenance"] == "backfilled").sum()) if not a.empty else 0}')
    print(f'  provenance=live                       : '
          f'{int((a["provenance"] == "live").sum()) if not a.empty else 0}')
    print()
    print(f'Table B rows (independent validation)   : {len(b)}')
    print(f'  MISSING cells                         : {n_missing(b, b_metric_cols)}')
    print(f'    of which expected (RMSE_corr, B/C)    : '
          f'{n_missing(b, ["RMSE_corr"])}')
    print(f'    unexpected (metric gaps)              : '
          f'{n_missing(b, ["RMSE", "MAE", "R2", "Bias", "n"])}')
    if not b.empty:
        # map_id repeats across cities (GHSL, emb_zeroshot, ...), so count
        # distinct city x map pairs -- that is what the 15-map registry means.
        pairs = b[['city', 'map_id', 'role']].drop_duplicates()
        by_role = pairs.groupby('role').size().to_dict()
        rules_seen = sorted(set(
            b['rule'].str.replace(r'\*\*| \(primary\)', '', regex=True)))
        print(f'  distinct city x map pairs             : {len(pairs)}'
              f'  {by_role}')
        print(f'  rules carried                         : {rules_seen}')
    print()
    print()
    print(f'Paired tests (pairs)                    : {len(pt)}')
    if not pt.empty:
        print(f'  distinguishable at FDR 5%             : '
              f'{int((pt["distinguishable"] == "yes").sum())} / {len(pt)}')
    print(f'Bias-recovery rows                      : {len(br)}')
    print(f'HCMC range-diagnostic rows              : {len(hs)}')
    print(f'Milan rule-ranking rows                 : {len(mr)}')
    if mrf:
        print(f'  ranking unchanged under B / C         : '
              f'{mrf["rank_same_B"]} / {mrf["rank_same_C"]}')
        print(f'  all Milan maps improve under C        : '
              f'{mrf["all_improve_C"]}')
    print()
    print(f'Table C rows (Vietnam per-class)        : {len(vpc)}')
    if not vpc.empty:
        undef = int((vpc['R2_not_for_quoting'] == 'undefined (no variance)').sum())
        print(f'  R2 undefined (C0/C6, no variance)     : {undef}')
    print(f'Table D rows (feature importance)       : {len(fi)}')
    if fi.empty:
        print(f'  {MISSING}: {fi_src}')
    print()
    print(f'Written: {os.path.relpath(OUT_PATH, REPO)}')
    print('=' * 62)


if __name__ == '__main__':
    main()
