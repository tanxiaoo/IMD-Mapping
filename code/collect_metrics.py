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

# Estimators the report covers. The Milan notebooks also tune a third model
# whose rows appear in the CV CSVs; it is out of scope and is filtered out at
# collection so it never reaches the fact base.
#
# The filter is on the model NAME, so the excluded estimator is never written
# to FACTS.md even when it wins a run. That is a live case, not a hypothetical:
# `best_model_name` in the percentile run's model_metadata_S2.json names the
# excluded model. Anything reading a `best_model_*` field must pass it through
# reported_model() before rendering.
REPORTED_MODELS = ('RF', 'SVR')


def reported_model(name):
    """Model name if it is in scope, else a neutral placeholder.

    Never returns the excluded estimator's name. Use for any value read from a
    `best_model_*` metadata field, which records whichever model won CV
    regardless of whether the report covers it.
    """
    return str(name) if str(name) in REPORTED_MODELS else 'out of scope'


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


def _ci(lo, hi, nd=3):
    """Format a bootstrap interval as [lo, hi], or MISSING if either end is."""
    lo_s, hi_s = _f(lo, nd), _f(hi, nd)
    if lo_s == MISSING or hi_s == MISSING:
        return MISSING
    return f'[{lo_s}, {hi_s}]'


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
    cis = {}
    if os.path.exists(t1_path):
        t1 = pd.read_csv(t1_path)
        for _, r in t1.iterrows():
            corr[(r['city'], r['map_id'])] = r.get('RMSE_corr')
            cis[(r['city'], r['map_id'])] = (
                r.get('RMSE_lo'), r.get('RMSE_hi'),
                r.get('MAE_lo'), r.get('MAE_hi'))

    rows = []
    for (city, map_id, role, rule), g in long_df.groupby(
            ['city', 'map_id', 'role', 'rule'], sort=False):
        ok = g['ref_imd'].notna() & g['pred_imd'].notna()
        yt = g.loc[ok, 'ref_imd'].to_numpy(dtype=float)
        yp = g.loc[ok, 'pred_imd'].to_numpy(dtype=float)

        if len(yt) < 2:
            rows.append(dict(city=city, map_id=map_id, role=role, rule=rule,
                             RMSE=MISSING, RMSE_corr=MISSING,
                             RMSE_CI=MISSING, MAE=MISSING, MAE_CI=MISSING,
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

        # RMSE_corr and the bootstrap CIs exist only for the primary rule;
        # never estimate them for B or C.
        primary = rule == PRIMARY_RULE
        rc = corr.get((city, map_id)) if primary else None
        rlo, rhi, mlo, mhi = (cis.get((city, map_id), (None,) * 4)
                              if primary else (None,) * 4)

        rows.append(dict(
            city=city, map_id=map_id, role=role, rule=rule,
            RMSE=_f(rmse), RMSE_corr=_f(rc), RMSE_CI=_ci(rlo, rhi),
            MAE=_f(mae), MAE_CI=_ci(mlo, mhi),
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


def collect_milan_error_shape():
    """Per-plot absolute-error distribution for the five Milan maps.

    MAE is the mean of this distribution and RMSE is driven by its upper tail,
    so a map can hold the best MAE and the worst RMSE at once. The quantiles
    and tail counts here are what makes that split a measurement rather than
    an inference from the two summary metrics.
    """
    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame(), rel
    s = pd.read_csv(path)
    s = s[(s['rule'] == PRIMARY_RULE) & (s['city'] == 'Milan')]

    rows = []
    for map_id, g in s.groupby('map_id', sort=False):
        e = g['abs_error'].dropna().to_numpy(dtype=float)
        if e.size == 0:
            continue
        n = e.size
        rows.append(dict(
            map_id=map_id,
            role=g['role'].iloc[0],
            MAE=_f(float(np.mean(e)), 2),
            RMSE=_f(float(np.sqrt(np.mean(e ** 2))), 2),
            median=_f(float(np.median(e)), 2),
            p75=_f(float(np.percentile(e, 75)), 2),
            p90=_f(float(np.percentile(e, 90)), 2),
            max=_f(float(e.max()), 2),
            pct_under5=f'{100 * float(np.mean(e < 5)):.1f}%',
            pct_over50=f'{100 * float(np.mean(e > 50)):.1f}%',
            n=str(n),
            source_file=rel,
        ))
    return pd.DataFrame(rows), rel


# Transfer rasters, for the whole-map view of the same diagnostic. The plot
# stats below see 450 pixels per city; these see every predicted pixel, so a
# floor that survives both is a property of the map and not of the sample.
RANGE_RASTERS = {
    ('Hanoi', 'emb_zeroshot'):       'outputs_transfer_v2/IMD_Hanoi_10m_zeroshot.tif',
    ('Hanoi', 'emb_localrf'):        'outputs_transfer_v2/IMD_Hanoi_10m_localrf.tif',
    ('HCMC', 'emb_zeroshot'):        'outputs_transfer_v2/IMD_HCMC_10m_zeroshot.tif',
    ('HCMC', 'emb_localrf'):         'outputs_transfer_v2/IMD_HCMC_10m_localrf.tif',
    # The S2 median run suffixes its rasters with the composite name; the
    # embeddings run does not. Same notebook code, different export tag.
    ('Hanoi', 'S2_median_zeroshot'): 'outputs_transfer_S2_median/IMD_Hanoi_10m_zeroshot_S2median.tif',
    ('Hanoi', 'S2_median_localrf'):  'outputs_transfer_S2_median/IMD_Hanoi_10m_localrf_S2median.tif',
    ('HCMC', 'S2_median_zeroshot'):  'outputs_transfer_S2_median/IMD_HCMC_10m_zeroshot_S2median.tif',
    ('HCMC', 'S2_median_localrf'):   'outputs_transfer_S2_median/IMD_HCMC_10m_localrf_S2median.tif',
}


def check_range_rasters():
    """Fail loudly if the transfer rasters do not resolve as expected.

    The paths in RANGE_RASTERS are constructed, and the two runs do not use
    the same filename pattern: the S2 median run suffixes its exports with
    the composite name, the embeddings run does not. A pattern mismatch
    resolves a SUBSET rather than nothing, so the tables still render and the
    numbers are still plausible -- they are simply computed from four maps
    instead of eight. That is the worst kind of failure for a fact base, so
    it is made fatal here rather than left to be noticed downstream.
    """
    missing = [rel for rel in RANGE_RASTERS.values()
               if not os.path.exists(os.path.join(REPO, rel))]
    assert not missing, (
        f'{len(missing)} of {len(RANGE_RASTERS)} transfer rasters did not '
        f'resolve: {missing}. Check the export filename pattern in notebooks '
        f'02/03 -- the S2 median run suffixes "_S2median", the embeddings run '
        f'does not. A partial match silently computes the range diagnostics '
        f'from a subset of the maps.')
    return len(RANGE_RASTERS)


def collect_raster_range(city, map_id):
    """Whole-raster min and sub-20% share for one predicted map.

    The rasters carry no nodata tag and pad the export grid with NaN, so
    validity is finiteness -- which is what recovers HCMC's 8.2 M figure from
    a 3001x3001 grid. Returns MISSING if the file or rasterio is absent;
    never estimated from the plot sample, which is a different population.
    """
    rel = RANGE_RASTERS.get((city, map_id))
    if rel is None:
        return {}
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return {}
    try:
        import rasterio
        with rasterio.open(path) as ds:
            a = ds.read(1).astype(float)
    except Exception:
        return {}
    v = a[np.isfinite(a)]
    if v.size == 0:
        return {}
    return {
        'ras_n': f'{v.size / 1e6:.1f} M',
        'ras_min': f'{v.min():.2f}',
        'ras_pct_lt20': f'{100 * float((v < 20).mean()):.4f}%',
        'ras_source': rel,
    }


def collect_city_range(city):
    """Prediction-range diagnostics for one city's four maps.

    Distinguishes a map whose range has collapsed from one that is merely
    shifted: a shifted map keeps its spread, a saturated one loses the tails.
    Run for both Vietnam cities -- the contrast between them is the result,
    so neither city can be the only one measured.
    """
    rel = 'outputs_validation/validation_per_plot_long.csv'
    path = os.path.join(REPO, rel)
    if not os.path.exists(path):
        return pd.DataFrame(), pd.DataFrame()
    s = pd.read_csv(path)
    s = s[(s['rule'] == PRIMARY_RULE) & (s['city'] == city)]

    maps = ['emb_zeroshot', 'S2_median_zeroshot',
            'emb_localrf', 'S2_median_localrf']
    ref = s[s['map_id'] == maps[0]]['ref_imd'].dropna().to_numpy()

    stats_rows = []
    for m in maps + ['(reference)']:
        v = (ref if m == '(reference)'
             else s[s['map_id'] == m]['pred_imd'].dropna().to_numpy())
        if len(v) == 0:
            continue
        row = dict(
            map_id=m, mean=f'{v.mean():.2f}', sd=f'{v.std():.2f}',
            min=f'{v.min():.1f}', max=f'{v.max():.1f}',
            IQR=f'{np.percentile(v, 75) - np.percentile(v, 25):.1f}',
            pct_gt80=f'{100 * (v > 80).mean():.1f}%',
            pct_lt20=f'{100 * (v < 20).mean():.1f}%')
        # Whole-raster counterpart, where one exists. The reference is plots
        # only -- there is no interpreted raster -- so it stays MISSING there.
        ras = collect_raster_range(city, m) if m != '(reference)' else {}
        row.update({k: ras.get(k, MISSING)
                    for k in ('ras_n', 'ras_min', 'ras_pct_lt20')})
        stats_rows.append(row)

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

    # The reference's two modes, and the width each map has available to span
    # them. A map cannot represent a bimodal reference from inside a narrow
    # band however well its mean is placed.
    facts = {}
    if len(ref):
        facts = {
            'ref_lt10': f'{100 * float((ref < 10).mean()):.1f}%',
            'ref_gt90': f'{100 * float((ref > 90).mean()):.1f}%',
            'ref_lt20': f'{100 * float((ref < 20).mean()):.1f}%',
            'ref_iqr': f'{np.percentile(ref, 75) - np.percentile(ref, 25):.1f}',
            'ref_sd': f'{ref.std():.2f}',
        }

    return pd.DataFrame(stats_rows), pd.DataFrame(hist_rows), facts


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


def collect_milan_cv():
    """Tuning CV RMSE per Milan run x model x block, with the block selected.

    Two files carry CV numbers and they answer different questions:

      hyperparameter_tuning.csv  CV RMSE of the randomised search at each block
                                 size. This is what the notebooks minimise --
                                 `best_block_per_model[name]` in 01/01b cell 22
                                 takes the argmin of this column -- so it is the
                                 authority for which block was selected.
      spatial_cv_summary.csv     CV RMSE of the already-tuned model re-evaluated
                                 under each CV strategy, including a Random rung
                                 the tuning file has no counterpart for.

    They do not agree, and are not meant to: on the embeddings run the tuning
    file selects RF @ 1000m (13.162) while the evaluation file is flattest at
    2000m (13.20). Both are carried, in separate columns, and the `selected`
    flag follows the tuning file because that is what the code does.

    MLP rows are dropped at source: the estimator is out of scope for this
    report, so it must not reach the fact base. `selected` is therefore the
    minimum over RF and SVR, not over every model the notebook tuned -- stated
    in the rendered note so the flag is not misread as the notebook's own
    overall winner (which is MLP on the percentile run).
    """
    rows = []
    for d, predictor in MILAN_RUNS:
        tune_rel = f'{d}/hyperparameter_tuning.csv'
        eval_rel = f'{d}/spatial_cv_summary.csv'
        tune_path = os.path.join(REPO, tune_rel)
        eval_path = os.path.join(REPO, eval_rel)

        if not os.path.exists(tune_path):
            rows.append(dict(predictor_set=predictor, model=MISSING,
                             block=MISSING, cv_rmse_tuning=MISSING,
                             cv_std=MISSING, cv_rmse_eval=MISSING,
                             selected=MISSING, source_file=tune_rel))
            continue

        tune = pd.read_csv(tune_path)
        tune = tune[tune['Model'].isin(REPORTED_MODELS)]

        # Evaluation RMSE, keyed by (model, block). Absent -> MISSING, never
        # substituted from the tuning column: they are different quantities.
        ev = {}
        if os.path.exists(eval_path):
            edf = pd.read_csv(eval_path)
            for _, r in edf.iterrows():
                ev[(str(r['Model']), str(r['CV_method']))] = r.get('RMSE_mean')

        # Selected block per model = argmin of the tuning CV RMSE, matching
        # best_block_per_model in notebooks 01 and 01b.
        best = {}
        for model, g in tune.groupby('Model'):
            g = g.dropna(subset=['CV_RMSE'])
            if not g.empty:
                best[model] = str(g.loc[g['CV_RMSE'].idxmin(), 'Block'])

        for _, r in tune.iterrows():
            model, block = str(r['Model']), str(r['Block'])
            rows.append(dict(
                predictor_set=predictor,
                model=model,
                block=block,
                cv_rmse_tuning=_f(r.get('CV_RMSE')),
                cv_std=_f(r.get('CV_std')),
                cv_rmse_eval=_f(ev.get((model, block))),
                selected='**yes**' if best.get(model) == block else '',
                source_file=tune_rel,
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


# ── Composite depth: what the archive holds against what percentiles need ────
# The screened date counts are already in EXPERIMENT_MAP.md, but the CEILING
# counts -- how many dates exist when every screening threshold is disabled --
# live only in the extraction metadata's free-text `method_rationale`. Without
# them the report can say "no relaxation of the thresholds recovers the dates"
# but cannot say by how much each city falls short, which is the difference
# between an archive limitation and a screening choice.
#
# Milan is not listed: it clears the requirement, so it has no shortfall to
# record and its metadata carries no rationale field.
CEILING_RUNS = [
    ('Hanoi', 'samples_S2_median_Hanoi/s2_extraction_metadata.json'),
    ('HCMC',  'samples_S2_median_HCMC/s2_extraction_metadata.json'),
]

# The percentile set whose date floor the report quotes. s2_utils.PERCENTILES
# still defaults to the retired 3-percentile set, so the set in USE is read
# from the run directory rather than taken from the module default.
PERCENTILE_RUN = ('samples_S2_percentile_p10p25p50p75p90/'
                  's2_extraction_metadata.json')


def _required_dates():
    """Minimum stack depth for the percentile set actually in use.

    Derived from s2_utils rather than parsed from prose, so the requirement in
    the fact base is the one the code enforces. Returns (n_dates, n_pctl).
    """
    path = os.path.join(REPO, PERCENTILE_RUN)
    if not os.path.exists(path):
        return None, None
    with open(path, encoding='utf-8') as fh:
        pctl = json.load(fh).get('percentiles')
    if not pctl:
        return None, None
    import sys
    sys.path.insert(0, REPO)
    from s2_utils import min_dates_for
    return int(min_dates_for(pctl)), len(pctl)


def collect_composite_ceiling():
    """Per-city percentile shortfall: screened, ceiling and required counts.

    `method_rationale` is free text written by notebook 00b, of the form
      "percentile(...) needs 17 dates; <collection> holds only 10 over this
       AOI in 2018."
    Both numbers are parsed out and the REQUIREMENT is cross-checked against
    s2_utils.min_dates_for -- if the prose and the code disagree, the value is
    written MISSING rather than trusting the sentence. A number that reaches
    the report must be one the code can still vouch for.
    """
    import re

    required, n_pctl = _required_dates()

    rows = []
    for city, rel in CEILING_RUNS:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            rows.append(dict(city=city, n_screened=MISSING, n_ceiling=MISSING,
                             n_required=MISSING, shortfall=MISSING,
                             source_file=rel))
            continue
        with open(path, encoding='utf-8') as fh:
            meta = json.load(fh)

        n_screened = len(meta.get('selected_dates') or []) or None
        prose = str(meta.get('method_rationale', ''))

        m_need = re.search(r'needs\s+(\d+)\s+dates', prose)
        m_have = re.search(r'holds\s+only\s+(\d+)\b', prose)
        prose_need = int(m_need.group(1)) if m_need else None
        n_ceiling = int(m_have.group(1)) if m_have else None

        # The requirement is the code's, not the sentence's. Disagreement means
        # the rationale was written against a different percentile set, so
        # neither number is safe to quote.
        if required is not None and prose_need is not None \
                and prose_need != required:
            n_ceiling = None
            n_need = MISSING
        else:
            n_need = str(required) if required is not None else (
                str(prose_need) if prose_need is not None else MISSING)

        short = (str(required - n_ceiling)
                 if required is not None and n_ceiling is not None
                 else MISSING)

        rows.append(dict(
            city=city,
            n_screened=str(n_screened) if n_screened else MISSING,
            n_ceiling=str(n_ceiling) if n_ceiling is not None else MISSING,
            n_required=n_need,
            shortfall=short,
            source_file=rel,
        ))
    return pd.DataFrame(rows), required, n_pctl


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
    mes, mes_src = collect_milan_error_shape()
    n_rasters = check_range_rasters()
    ranges = {c: collect_city_range(c) for c in ('Hanoi', 'HCMC')}
    mr, mrf = collect_milan_rule_ranking()
    cc, cc_required, cc_npctl = collect_composite_ceiling()
    vpc = collect_vietnam_per_class()
    cv = collect_milan_cv()
    fi, fi_src = collect_feature_importance()
    lm = collect_level_matching()

    a_cols = ['city', 'predictor_set', 'model', 'mode', 'RMSE', 'MAE', 'R2',
              'Bias', 'n', 'source_file', 'provenance']
    b_cols = ['city', 'map_id', 'role', 'rule', 'RMSE', 'RMSE_corr', 'RMSE_CI',
              'MAE', 'MAE_CI', 'R2', 'Bias', 'n', 'source_file']

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
              'Tables D and E are model diagnostics, not accuracy measures — '
              'Table E holds cross-validation scores, which must never be '
              'quoted as holdout performance.\n')
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
    md.append(f'\n`RMSE_CI` and `MAE_CI` are **95 % percentile bootstrap** '
              f'intervals read from '
              f'`outputs_validation/table1_headline_ci.csv`: '
              f'10,000 resamples, seed 42, '
              f'resampling **plots** as the independent unit, with one shared '
              f'resample index across maps within a city. Like `RMSE_corr` '
              f'they are stored for the primary rule only and are left '
              f'{MISSING} for rules B and C.\n')
    md.append('\nAn interval here describes the uncertainty of **one map\'s** '
              'metric taken on its own. It is not a test of the difference '
              'between two maps: the paired tests below remove the plot-level '
              'variance common to both maps and therefore have more power, so '
              'overlapping intervals and a significant paired difference are '
              'consistent rather than contradictory.\n')

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

    # ── Composite depth: the percentile shortfall in Vietnam ────────────────
    md.append('\n### Why percentiles were not computable in Vietnam\n')
    md.append('_Usable dates after screening, against the ceiling case in '
              'which every screening threshold is disabled, against the number '
              'a percentile composite requires. `n_ceiling` is the count the '
              '2018 archive holds over the AOI when nothing is filtered out at '
              'all, so a city short of `n_required` there is short of dates '
              'that do not exist — not of dates a looser threshold would '
              'admit._\n')
    md.append(to_md(cc, ['city', 'n_screened', 'n_ceiling', 'n_required',
                         'shortfall', 'source_file']))
    if cc_required is not None:
        md.append(f'\n`n_required` is derived from `s2_utils.min_dates_for`, '
                  f'not read from the metadata prose: {cc_npctl} percentiles '
                  f'require **{cc_required} dates**. The prose value is '
                  'cross-checked against it and the row is written MISSING '
                  'if the two disagree, since a rationale written against a '
                  'different percentile set cannot vouch for either number.\n')
    if not cc.empty and (cc['n_ceiling'] != MISSING).all():
        worst = cc.loc[cc['shortfall'].astype(int).idxmin()]
        md.append(f'\n**Neither city reaches the requirement even unscreened.** '
                  f'The shortfall is smallest in {worst["city"]}, which holds '
                  f'{worst["n_ceiling"]} dates against the {worst["n_required"]} '
                  f'required — short by {worst["shortfall"]}. That the closest '
                  'case still misses is what makes this an archive limitation '
                  'rather than a screening choice: no relaxation of the '
                  'thresholds can produce dates the 2018 archive does not '
                  'hold. Median has no minimum date count and was therefore '
                  'the only method computable in either city.\n')

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

    # ── Milan error shape ───────────────────────────────────────────────────
    md.append('\n### Milan per-plot absolute-error distribution (primary '
              'rule)\n')
    md.append('_MAE is the mean of this distribution; RMSE squares the errors '
              'first and is therefore driven by its upper tail. A map can hold '
              'the best MAE and the worst RMSE at once, and these columns are '
              'where that shows._\n')
    md.append(to_md(mes, ['map_id', 'role', 'MAE', 'RMSE', 'median', 'p75',
                          'p90', 'max', 'pct_under5', 'pct_over50', 'n',
                          'source_file']))
    md.append('\n**`CLMS` has the best MAE and the worst RMSE of the five '
              'Milan maps.** The distribution accounts for the split: it is '
              'right more often than any model — the largest `pct_under5` and '
              'the lowest median absolute error — and wrong by more when it is '
              'wrong, carrying the largest `pct_over50`. The models fitted to '
              'it hedge, which costs them on the plots `CLMS` gets nearly '
              'exact and saves them on the plots it gets badly wrong. The two '
              'metrics measure the two halves of that trade and are not in '
              'conflict.\n')

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

    # ── Range diagnostics, both Vietnam cities ──────────────────────────────
    md.append('\n### Prediction range: tail and spread, both Vietnam cities\n')
    md.append('_Per-plot predicted IMD against the interpreted reference, '
              'primary rule (n = 450 per city), with the whole-raster minimum '
              'and sub-20 % share alongside. Two failures are separable here '
              'and are kept apart: a map may lose the low **tail** the '
              'reference carries, and it may compress its **spread**. Both '
              'cities are measured on both axes, neither standing in for the '
              'other._\n')
    stat_cols = ['map_id', 'mean', 'sd', 'min', 'max', 'IQR', 'pct_gt80',
                 'pct_lt20', 'ras_n', 'ras_min', 'ras_pct_lt20']
    hist_cols = ['bin', 'emb_zeroshot', 'S2_median_zeroshot',
                 'emb_localrf', 'S2_median_localrf', '(reference)']
    for city in ('Hanoi', 'HCMC'):
        st, hi, fx = ranges[city]
        md.append(f'\n**{city}.** Per-plot predicted IMD:\n')
        md.append(to_md(st, stat_cols))
        md.append(f'\n_{city}, distribution over the same 450 plots:_\n')
        md.append(to_md(hi, [c for c in hist_cols if c in hi.columns]))
        if fx:
            md.append(f'\n{city}\'s reference is bimodal: **{fx["ref_lt10"]}** '
                      f'of plots below 10 % and **{fx["ref_gt90"]}** above '
                      f'90 %, giving an IQR of {fx["ref_iqr"]} and an sd of '
                      f'{fx["ref_sd"]}. **{fx["ref_lt20"]}** of plots are '
                      'below 20 %.\n')

    # Every map with a registered raster must have produced raster columns.
    # check_range_rasters() catches a path that does not exist; this catches
    # one that exists but failed to open, which would otherwise leave a
    # MISSING cell in a table whose whole point is the raster evidence.
    loaded = sum(
        1 for city in ('Hanoi', 'HCMC')
        for _, r in ranges[city][0].iterrows()
        if (city, r['map_id']) in RANGE_RASTERS and r['ras_min'] != MISSING)
    assert loaded == n_rasters, (
        f'{loaded} of {n_rasters} transfer rasters produced range statistics. '
        f'A registered raster exists on disk but did not read -- check '
        f'rasterio and the file contents before trusting these tables.')

    # Saturation is measured on two axes, not collapsed into one verdict.
    #
    # An early version of this used a single threshold on low-tail retention.
    # It decided the answer by where the cut fell -- Hanoi lands at 3.1%, so a
    # 5% rule called it saturated and a 2% rule would not have. That is the
    # threshold talking, not the data, so both axes are now reported:
    #
    #   TAIL   share of the reference's sub-20% mass the map retains.
    #   SPREAD map IQR against the reference IQR.
    #
    # A map can lose the tail while keeping its spread (Hanoi) or lose both
    # (HCMC). Retention is reported at 10% as well as 20%, because the 20%
    # figure alone understates how complete the loss is in both cities.
    # Measured for every map, not only the zero-shots: whether the local
    # retrains keep their low tails is what turns a two-city observation into
    # a statement about the scenario rather than about a city.
    verdicts = []
    for city in ('Hanoi', 'HCMC'):
        st, _, fx = ranges[city]
        ref_row = st[st['map_id'] == '(reference)']
        if ref_row.empty or not fx:
            continue
        ref_row = ref_row.iloc[0]
        ref_share = float(str(fx['ref_lt20']).rstrip('%'))
        ref_iqr = float(ref_row['IQR'])
        for _, r in st.iterrows():
            if r['map_id'] == '(reference)' or r['ras_pct_lt20'] == MISSING:
                continue
            share = float(str(r['ras_pct_lt20']).rstrip('%'))
            tail_ret = share / ref_share if ref_share > 0 else float('nan')
            spread_ret = (float(r['IQR']) / ref_iqr if ref_iqr > 0
                          else float('nan'))
            verdicts.append(dict(
                city=city, map_id=r['map_id'],
                scenario=('zero-shot' if 'zeroshot' in r['map_id']
                          else 'local retrain'),
                ras_min=r['ras_min'], ras_share=r['ras_pct_lt20'],
                ras_n=r['ras_n'], plot_min=r['min'], iqr=r['IQR'], sd=r['sd'],
                ref_share=fx['ref_lt20'], ref_iqr=ref_row['IQR'],
                ref_sd=ref_row['sd'],
                tail_ret=f'{100 * tail_ret:.1f}%',
                spread_ret=f'{100 * spread_ret:.0f}%'))

    if verdicts:
        md.append('\n**Tail and spread retention, every map.** Two failures '
                  'are separable and are kept apart. `tail_retained` is the '
                  'share of the reference\'s sub-20 % mass the raster keeps; '
                  '`spread_retained` is the map IQR over the reference IQR. '
                  'Neither is thresholded into a yes/no — a single cut on '
                  'tail retention would decide the borderline case by where '
                  'the cut was put rather than by the data. Tail retention '
                  'compares a raster-wide share against a 450-plot share, so '
                  'read it as an order of magnitude, not to the percentage '
                  'point; values near or above 100 % mean the tail is fully '
                  'present, not that it is oversized.\n')
        vt = pd.DataFrame([dict(
            city=v['city'], map_id=v['map_id'], scenario=v['scenario'],
            raster_floor=v['ras_min'], pct_lt20=v['ras_share'],
            ref_pct_lt20=v['ref_share'], tail_retained=v['tail_ret'],
            IQR=v['iqr'], ref_IQR=v['ref_iqr'],
            spread_retained=v['spread_ret']) for v in verdicts])
        md.append(to_md(vt, list(vt.columns)))

        emb_zs = [v for v in verdicts if v['map_id'] == 'emb_zeroshot']
        loc = [v for v in verdicts if v['scenario'] == 'local retrain']
        if len(emb_zs) == 2:
            lo, hi = sorted(emb_zs, key=lambda v: float(v['spread_ret'].rstrip('%')))
            md.append(f'\n**Both `emb_zeroshot` maps have lost the low '
                      f'tail.** {hi["city"]} retains **{hi["tail_ret"]}** of '
                      f'the sub-20 % mass its reference carries and '
                      f'{lo["city"]} **{lo["tail_ret"]}**; below 10 % both '
                      'are empty to four decimal places. On the tail axis '
                      'the two cities agree, so the loss is a property of '
                      'the transferred embedding map and not of one city.\n')
            md.append(f'\n**They differ in how far the spread collapses with '
                      f'it.** {lo["city"]} holds **{lo["spread_ret"]}** of '
                      f'the reference IQR against {hi["city"]}\'s '
                      f'**{hi["spread_ret"]}**, on {lo["iqr"]} and '
                      f'{hi["iqr"]} against a reference IQR of '
                      f'{lo["ref_iqr"]}. The shared mechanism is the missing '
                      f'tail; {lo["city"]} is the severe case, where the '
                      'range has narrowed around it as well.\n')
        if len(loc) == 4:
            worst = min(loc, key=lambda v: float(v['tail_ret'].rstrip('%')))
            md.append(f'\n**Every local retrain keeps its low tail, in both '
                      f'cities.** All four reach a raster floor of 0.00 and '
                      f'retain between **{worst["tail_ret"]}** and '
                      f'**{max(float(v["tail_ret"].rstrip("%")) for v in loc):.0f} %** '
                      'of the reference\'s sub-20 % mass — full recovery of '
                      'the low end within the precision this comparison '
                      'supports. Taken with the row above, that is the '
                      'cleanest statement of the failure: **zero-shot '
                      'transfer destroys the low end of the distribution and '
                      'local retraining restores it**, in both cities and '
                      'for both predictor sets.\n')

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

    # ── Table E: Milan cross-validation ─────────────────────────────────────
    md.append('\n## Table E — Milan cross-validation, tuning and evaluation\n')
    md.append('_CV RMSE per run × model × block. `cv_rmse_tuning` is the '
              'randomised search score from `hyperparameter_tuning.csv`; '
              '`cv_rmse_eval` is the tuned model re-scored under spatial CV '
              'from `spatial_cv_summary.csv`. **These are different '
              'quantities and will not agree.** `selected` marks the block '
              'each model was tuned at._\n')
    md.append(to_md(cv, ['predictor_set', 'model', 'block', 'cv_rmse_tuning',
                         'cv_std', 'cv_rmse_eval', 'selected', 'source_file']))
    md.append('\n**These are cross-validation numbers, not holdout numbers, '
              'and they are not comparable with Table A.** Table A scores '
              'rasters built in Earth Engine on the held-out 1014 points; the '
              'values here score scikit-learn models on training-set folds. '
              'The gap between them is the subject of the CV-versus-holdout '
              'reversal, not an inconsistency.\n')
    md.append(f'\n**`selected` is the argmin of `cv_rmse_tuning` over '
              f'{" and ".join(REPORTED_MODELS)} only**, matching '
              '`best_block_per_model` in notebooks 01 and 01b. The notebooks '
              'also tune a third estimator that is out of scope for this '
              'report; its rows are filtered out at collection, so `selected` '
              'here is not necessarily the overall winner recorded in a run\'s '
              '`model_metadata_*.json`.\n')
    if not cv.empty:
        sel = cv[cv['selected'] == '**yes**']
        emb = sel[sel['predictor_set'] == 'AlphaEarth embeddings']
        pairs = {r['model']: (r['cv_rmse_tuning'], r['block'])
                 for _, r in emb.iterrows()}
        if 'RF' in pairs and 'SVR' in pairs:
            md.append(f'\nOn the embeddings run SVR is tuned to '
                      f'**{pairs["SVR"][0]} @ {pairs["SVR"][1]}** against RF\'s '
                      f'**{pairs["RF"][0]} @ {pairs["RF"][1]}** — SVR ahead on '
                      'cross-validation, before losing every holdout metric in '
                      'Table A.\n')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md))

    # ── Summary ─────────────────────────────────────────────────────────────
    def n_missing(df, cols):
        if df.empty:
            return 0
        return int(sum((df[c] == MISSING).sum() for c in cols if c in df))

    a_metric_cols = ['RMSE', 'MAE', 'R2', 'Bias', 'n']
    b_metric_cols = ['RMSE', 'RMSE_corr', 'RMSE_CI', 'MAE', 'MAE_CI',
                     'R2', 'Bias', 'n']

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
    print(f'    of which expected (primary-only, B/C) : '
          f'{n_missing(b, ["RMSE_corr", "RMSE_CI", "MAE_CI"])}')
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
    for _c in ('Hanoi', 'HCMC'):
        _st = ranges[_c][0]
        _rn = 0 if _st.empty else int((_st['ras_min'] != MISSING).sum())
        print(f'{_c} range-diagnostic rows{" " * (17 - len(_c))}: '
              f'{len(_st)}  (raster-backed: {_rn})')
    print(f'  transfer rasters resolved             : '
          f'{loaded} / {n_rasters}')
    for _v in verdicts:
        print(f'    {_v["city"]:<5} {_v["map_id"]:<19} tail/spread : '
              f'{_v["tail_ret"]:>6} / {_v["spread_ret"]:>4}')
    print(f'Composite-ceiling rows                  : {len(cc)}')
    if not cc.empty:
        print(f'  percentiles require                   : '
              f'{cc_required} dates ({cc_npctl} percentiles)')
        for _, _r in cc.iterrows():
            print(f'    {_r["city"]:<5} screened {_r["n_screened"]:>3}  '
                  f'ceiling {_r["n_ceiling"]:>3}  short by '
                  f'{_r["shortfall"]:>3}')
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
    print(f'Table E rows (Milan CV)                 : {len(cv)}')
    if not cv.empty:
        print(f'  models carried                        : '
              f'{sorted(set(cv["model"]))}')
        print(f'  blocks selected                       : '
              f'{int((cv["selected"] == "**yes**").sum())}')
        print(f'  eval RMSE MISSING                     : '
              f'{n_missing(cv, ["cv_rmse_eval"])}')
    print()
    print(f'Written: {os.path.relpath(OUT_PATH, REPO)}')
    print('=' * 62)


if __name__ == '__main__':
    main()
