"""Independent validation against the EarthLabel plots: the reference value,
the metrics (equal or area weights), stratum areas and the stratified, paired
bootstrap.

Used by notebook 05 and by ``interpreter_agreement.py``, so every number comes
from one implementation.

Conventions
-----------
- Bias is observed minus predicted: positive means the map under-predicts.
- Two weighting schemes:
  ``balanced``       every plot counts once, so each of the six strata (75 plots
                     each) carries 1/6: performance across the whole
                     imperviousness gradient;
  ``area_weighted``  each plot carries W_h / n_h, W_h the share of the city's
                     valid area in its stratum and n_h the stratum's plot count:
                     performance representative of the city.
  Without weights every function reproduces the unweighted metric exactly.
- Confusion matrices are weighted counts. With area weights normalised to sum
  to the number of plots they are "equivalent plots"; divided by that number
  they are estimated area proportions.
"""

import json

import numpy as np
import pandas as pd

BIN_THRESHOLD = 50.0
K_LEVELS = 9                      # ninths: 10 levels, 0/9 .. 9/9
N_STRATA = 6
STRATA = [f"IMD_Class_{k}" for k in range(N_STRATA)]
SCHEMES = ("balanced", "area_weighted")

# ── The reference value of a plot ────────────────────────────────────────────
_KW_IMP = ("building", "roof", "road", "asphalt", "pavement", "concrete", "sidewalk", "parking",
           "industrial", "airport", "runway", "railroad", "rail track", "ballast", "swimming pool",
           "rock", "material")
_KW_PER = ("grass", "lawn", "park", "vegetation", "tree", "canopy", "forest", "bare soil", "silt",
           "plowed", "agricultur", "unpaved", "dirt road", "water", "wetland", "crop", "shrub",
           "soil", "sand", "permeable pavement")


def classify_surface(label):
    """1 impervious, 0 pervious, NaN unresolved, for one sub-cell label."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return np.nan
    s = str(label).strip().lower()
    if not s or s == "nan":
        return np.nan
    while s.startswith("perviouspervious"):
        s = s[len("pervious"):]
    if s.startswith("impervious"):
        return 1
    if s.startswith("pervious"):
        return 0
    if "permeable pavement" in s:
        return 0
    if any(k in s for k in _KW_PER):
        return 0
    if any(k in s for k in _KW_IMP):
        return 1
    return np.nan


def reference_from_cells(cells_json):
    """(impervious % of the resolvable sub-cells, number of unresolved sub-cells)."""
    flags = np.array([classify_surface(it.get("label")) for it in json.loads(cells_json)], float)
    good = flags[~np.isnan(flags)]
    return (100.0 * good.mean() if good.size else np.nan), int(np.isnan(flags).sum())


# ── Weighted primitives ──────────────────────────────────────────────────────
def _w(w, n):
    return np.ones(n) if w is None else np.asarray(w, float)


def weighted_confusion(a, b, n_classes, w=None):
    """Weighted confusion matrix, rows ``a`` (reference), columns ``b`` (predicted)."""
    C = np.zeros((n_classes, n_classes))
    np.add.at(C, (a, b), _w(w, len(a)))
    return C


def kappa_from_cm(C):
    N = C.sum()
    po = np.trace(C) / N
    pe = (C.sum(1) * C.sum(0)).sum() / N ** 2
    return (po - pe) / (1 - pe) if pe != 1 else np.nan


def continuous_metrics(g, p, w=None):
    """Raw predicted % (clipped to 0-100) against the reference %."""
    g = np.asarray(g, float); p = np.clip(np.asarray(p, float), 0, 100)
    w = _w(w, len(g))
    m = np.isfinite(g) & np.isfinite(p)
    g, p, w = g[m], p[m], w[m]
    sw = w.sum()
    err = p - g
    gbar = (w * g).sum() / sw
    ss_res = (w * err ** 2).sum()
    ss_tot = (w * (g - gbar) ** 2).sum()
    pbar = (w * p).sum() / sw
    cov = (w * (g - gbar) * (p - pbar)).sum()
    vp = (w * (p - pbar) ** 2).sum()
    return dict(n=int(m.sum()),
                RMSE_pp=float(np.sqrt(ss_res / sw)),
                MAE_pp=float((w * np.abs(err)).sum() / sw),
                bias_pp=float((w * (g - p)).sum() / sw),
                R2=float(1 - ss_res / ss_tot) if ss_tot else np.nan,
                pearson_r=float(cov / np.sqrt(ss_tot * vp)) if ss_tot and vp else np.nan)


def binary_metrics(g, p, w=None, threshold=BIN_THRESHOLD):
    """Impervious if >= threshold, for the reference and the map; drops plots
    with no prediction or no resolvable reference (a NaN would score pervious)."""
    g = np.asarray(g, float); p = np.asarray(p, float)
    w = _w(w, len(g))
    m = np.isfinite(g) & np.isfinite(p)
    gb = (g[m] >= threshold).astype(int); pb = (p[m] >= threshold).astype(int)
    cm = weighted_confusion(gb, pb, 2, w[m])
    (tn, fp), (fn, tp) = cm
    tot = cm.sum()
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    return cm, dict(
        n=int(m.sum()), OA=float(np.trace(cm) / tot), kappa=float(kappa_from_cm(cm)),
        PA_pervious=tn / (tn + fp) if (tn + fp) else np.nan,
        PA_impervious=tp / (tp + fn) if (tp + fn) else np.nan,
        UA_pervious=tn / (tn + fn) if (tn + fn) else np.nan,
        UA_impervious=tp / (tp + fp) if (tp + fp) else np.nan,
        F1_impervious=float(f1))


def to_levels(pct, k=K_LEVELS):
    """0-100 % to the nearest of k+1 levels (ninths)."""
    return np.clip(np.round(np.clip(np.asarray(pct, float) / 100.0, 0, 1) * k), 0, k).astype(int)


def level_stats(C, k=K_LEVELS):
    """Exact, within-one-level, MAE/RMSE in levels and pp, and QWK, of a
    (k+1)x(k+1) confusion matrix of levels (weighted counts allowed)."""
    N = C.sum(); idx = np.arange(k + 1)
    d = np.abs(idx[:, None] - idx[None, :])
    W = (d / k) ** 2
    E = np.outer(C.sum(1), C.sum(0)) / N
    mae_lv = (C * d).sum() / N
    return dict(exact_match_OA=float(np.trace(C) / N), within_1_level_OA=float(C[d <= 1].sum() / N),
                MAE_levels=float(mae_lv), MAE_pp=float(mae_lv * 100 / k),
                RMSE_pp=float(np.sqrt((C * d ** 2).sum() / N) * 100 / k),
                quad_weighted_kappa=float(1 - (W * C).sum() / (W * E).sum()) if (W * E).sum() else np.nan)


def level_confusion(g, p, w=None, k=K_LEVELS):
    """The 10-level confusion matrix (DataFrame), per-level accuracies, stats."""
    g = np.asarray(g, float); p = np.asarray(p, float)
    w = _w(w, len(g))
    m = np.isfinite(g) & np.isfinite(p)
    C = weighted_confusion(to_levels(g[m], k), to_levels(p[m], k), k + 1, w[m])
    lab = [f"{i}/9" for i in range(k + 1)]
    row, col = C.sum(1), C.sum(0)
    per = pd.DataFrame({
        "n_ref": row, "n_pred": col,
        "producers_acc": np.divide(np.diag(C), row, out=np.full(k + 1, np.nan), where=row > 0),
        "users_acc": np.divide(np.diag(C), col, out=np.full(k + 1, np.nan), where=col > 0),
    }, index=lab)
    Cdf = pd.DataFrame(C, index=pd.Index(lab, name="reference"), columns=pd.Index(lab, name="predicted"))
    return Cdf, per, dict(n=int(m.sum()), **level_stats(C, k))


# ── Stratum areas and weights ────────────────────────────────────────────────
def stratum_areas(stratum_tif, mask_tif):
    """Pixels and km2 of each stratum C0-C5 inside the combined valid mask, and
    W_h, the share of the masked area. The mask is resampled (nearest) onto the
    stratum grid when the grids differ."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(stratum_tif) as s:
        st = s.read(1); nod = s.nodata
        grid = dict(transform=s.transform, crs=s.crs, shape=s.shape)
        px_km2 = abs(s.transform.a * s.transform.e) / 1e6
    with rasterio.open(mask_tif) as m:
        if (m.transform, m.crs, m.shape) == (grid["transform"], grid["crs"], grid["shape"]):
            mask = m.read(1)
        else:
            mask = np.zeros(grid["shape"], "uint8")
            reproject(m.read(1), mask, src_transform=m.transform, src_crs=m.crs,
                      dst_transform=grid["transform"], dst_crs=grid["crs"],
                      src_nodata=None, dst_nodata=0, resampling=Resampling.nearest)
    valid = (mask == 1) & (st != nod) if nod is not None else (mask == 1)
    counts = np.bincount(st[valid].astype(int), minlength=N_STRATA)[:N_STRATA]
    assert counts.sum() == valid.sum(), "masked pixels outside the six strata"
    return pd.DataFrame({"stratum": STRATA, "pixels": counts.astype(np.int64),
                         "area_km2": counts * px_km2, "W_h": counts / counts.sum()})


def plot_weights(strata, W):
    """Area weight of each plot, W_h / n_h, normalised to sum to the plot count.
    ``strata`` is each plot's stratum label, ``W`` maps a label to W_h."""
    strata = pd.Series(np.asarray(strata))
    n_h = strata.map(strata.value_counts())
    w = strata.map(W).to_numpy(float) / n_h.to_numpy(float)
    return w * len(w) / w.sum()


# ── The nine bootstrap metrics ───────────────────────────────────────────────
METRICS = ("RMSE_pp", "MAE_pp", "bias_pp", "R2", "OA", "kappa",
           "exact_match_OA", "within_1_level_OA", "quad_weighted_kappa")
HIGHER_BETTER = {"R2", "OA", "kappa", "exact_match_OA", "within_1_level_OA", "quad_weighted_kappa"}
LOWER_BETTER = {"RMSE_pp", "MAE_pp", "abs_bias_pp"}
PRIMARY = {"R2", "kappa", "quad_weighted_kappa"}


def nine_metrics(g, p, w=None):
    c = continuous_metrics(g, p, w)
    _, b = binary_metrics(g, p, w)
    _, _, lv = level_confusion(g, p, w)
    return {"RMSE_pp": c["RMSE_pp"], "MAE_pp": c["MAE_pp"], "bias_pp": c["bias_pp"], "R2": c["R2"],
            "OA": b["OA"], "kappa": b["kappa"], "exact_match_OA": lv["exact_match_OA"],
            "within_1_level_OA": lv["within_1_level_OA"],
            "quad_weighted_kappa": lv["quad_weighted_kappa"]}


def stratified_indices(strata, B, seed):
    """B arrays of row positions: inside each stratum, n_h draws with
    replacement from that stratum's rows. The same arrays serve every map."""
    strata = np.asarray(strata)
    groups = [np.where(strata == s)[0] for s in pd.unique(strata)]
    rng = np.random.default_rng(seed)
    for _ in range(B):
        yield np.concatenate([rng.choice(gi, size=len(gi), replace=True) for gi in groups])


def bootstrap(df, maps, W, B=1000, seed=42):
    """Per iteration and map, the nine metrics under both schemes.

    ``df`` has ``gt_imperv_pct``, ``gt_density_class`` and ``pred_<map>``
    columns. Returns {scheme: DataFrame(iter, map, *METRICS)}. The resampled
    plot IDs are the same for every map within an iteration (paired).
    """
    g_all = df["gt_imperv_pct"].to_numpy(float)
    st_all = df["gt_density_class"].to_numpy()
    sizes = pd.Series(st_all).value_counts()
    rows = {s: [] for s in SCHEMES}
    for it, idx in enumerate(stratified_indices(st_all, B, seed)):
        st = st_all[idx]
        assert (pd.Series(st).value_counts().reindex(sizes.index) == sizes).all()
        g = g_all[idx]
        w_area = plot_weights(st, W)
        for m in maps:
            p = df[f"pred_{m}"].to_numpy(float)[idx]
            rows["balanced"].append({"iter": it, "map": m, **nine_metrics(g, p)})
            rows["area_weighted"].append({"iter": it, "map": m, **nine_metrics(g, p, w_area)})
    return {s: pd.DataFrame(r) for s, r in rows.items()}


def point_estimates(df, maps, W):
    """The nine metrics on the original plots, both schemes: {scheme: DataFrame}."""
    g = df["gt_imperv_pct"].to_numpy(float)
    w_area = plot_weights(df["gt_density_class"], W)
    out = {}
    for s, w in (("balanced", None), ("area_weighted", w_area)):
        out[s] = pd.DataFrame([{"map": m, **nine_metrics(g, df[f"pred_{m}"].to_numpy(float), w)}
                               for m in maps]).set_index("map")
    return out


def confidence_intervals(est, boot, level=0.95):
    """Percentile interval per map and metric; the estimate is the value on the
    original plots, not the bootstrap mean. Flags an estimate outside its interval."""
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    rows = []
    for m, g in boot.groupby("map", sort=False):
        for k in METRICS:
            v = g[k].to_numpy(float)
            e = float(est.loc[m, k])
            a, b = np.nanpercentile(v, [lo, hi])
            rows.append({"map": m, "metric": k, "estimate": e, "ci_lo": a, "ci_hi": b,
                         "boot_mean": float(np.nanmean(v)), "boot_sd": float(np.nanstd(v, ddof=1)),
                         "estimate_outside_ci": bool(e < a or e > b)})
    return pd.DataFrame(rows)


def paired_differences(est, boot, pairs, level=0.95):
    """Delta = metric(A) - metric(B) per pair, with its percentile interval
    over the paired bootstrap. Bias is compared as |bias|. ``better_map`` is A
    or B when the interval excludes 0 (read with the metric's direction), else
    'similar'. ``pairs`` is a list of (group, A, B)."""
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    wide = {k: boot.pivot(index="iter", columns="map", values=k) for k in METRICS}
    rows = []
    for group, a, b in pairs:
        for k in METRICS:
            name = "abs_bias_pp" if k == "bias_pp" else k
            f = np.abs if k == "bias_pp" else (lambda x: x)
            da = f(wide[k][a].to_numpy(float)) - f(wide[k][b].to_numpy(float))
            ea, eb = float(f(est.loc[a, k])), float(f(est.loc[b, k]))
            c_lo, c_hi = np.nanpercentile(da, [lo, hi])
            excl = bool(c_lo > 0 or c_hi < 0)
            if not excl:
                better = "similar"
            elif name in HIGHER_BETTER:
                better = a if c_lo > 0 else b
            else:
                better = a if c_hi < 0 else b
            rows.append({"group": group, "map_a": a, "map_b": b, "metric": name,
                         "a": ea, "b": eb, "delta": ea - eb, "ci_lo": c_lo, "ci_hi": c_hi,
                         "ci_excludes_0": excl, "better_map": better,
                         "direction": "higher is better" if name in HIGHER_BETTER else "lower is better",
                         "primary": name in PRIMARY})
    return pd.DataFrame(rows)


def qwk_levels(a, b, k=K_LEVELS):
    """QWK between two sets of levels 0..k (the interpreter agreement)."""
    return level_stats(weighted_confusion(np.asarray(a, int), np.asarray(b, int), k + 1), k)
