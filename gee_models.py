"""The random forest, tuned and built entirely in Earth Engine.

Every map is classified by Earth Engine's ``smileRandomForest``. Tuning used to
run in scikit-learn and be translated, but one tuned setting (a leaf cap) has
no exact Earth Engine counterpart, so for most models the map's forest was not
the tuned one. Here the search, the cross-validation and the final fit all run
in Earth Engine: the map is the tuned model by construction.

    folds  = gm.make_folds(coords)                       # 500 / 1000 / 2000 m
    fc     = gm.points_fc(gdf, bands, label, folds)
    table, best = gm.tune(fc, bands, label)              # 40 settings x 3 blocks
    oof, cv = gm.oof_predictions(fc, bands, label, best) # spatial CV metrics
    clf    = gm.train_final(fc, bands, label, best)      # all points
    gm.save_model(clf, record, json_path)                # keep the model

Requests: one per (setting, block size), each training and scoring all 5 folds
on the server and returning the summed squared error per fold. A trial on the
Milan embedding (3,500 points, 64 bands): 120 requests in 11 minutes at 8 in
parallel, the same choice as scikit-learn (CV RMSE 13.21 vs 13.22).

Each model is kept as a JSON record beside its map: the feature table, bands,
label, Earth Engine settings and seed, the tuning table, the CV metrics and the
forest's own importances (``explain()``). Training is deterministic, so
:func:`load_model` rebuilds the identical forest from it (zero-shot, or later
analysis). A classifier asset is not used: Earth Engine reloads a regression
forest asset without its trees.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

import ee

SEED = 42
N_FOLDS = 5
BLOCK_SIZES = (500, 1000, 2000)
N_ITER = 40
WORKERS = 8

# Earth Engine settings searched. max_features is resolved to a band count
# (variablesPerSplit) for each predictor; maxNodes is Earth Engine's own limit.
PARAM_SPACE = {
    "numberOfTrees":     [100, 200, 300, 500],
    "max_features":      ["sqrt", "log2", 0.3, 0.5],
    "minLeafPopulation": [1, 2, 4],
    "maxNodes":          [None, 250, 500, 1000],
}
_NOT_KWARGS = ("max_features", "block", "setting", "cv_rmse", "cv_std")


def variables_per_split(max_features, n_bands):
    """Bands tried per split for a ``max_features`` choice."""
    if max_features == "sqrt":
        return max(1, int(np.sqrt(n_bands)))
    if max_features == "log2":
        return max(1, int(np.log2(n_bands)))
    return max(1, int(float(max_features) * n_bands))


def settings(n_bands, n_iter=N_ITER, seed=SEED):
    """The ``n_iter`` settings searched, drawn reproducibly from PARAM_SPACE."""
    from sklearn.model_selection import ParameterSampler

    out = []
    for p in ParameterSampler(PARAM_SPACE, n_iter=n_iter, random_state=seed):
        kw = {"numberOfTrees": int(p["numberOfTrees"]),
              "variablesPerSplit": variables_per_split(p["max_features"], n_bands),
              "minLeafPopulation": int(p["minLeafPopulation"]),
              "bagFraction": 1.0, "seed": seed}
        if p["maxNodes"] is not None:
            kw["maxNodes"] = int(p["maxNodes"])
        out.append({"max_features": p["max_features"], **kw})
    return out


def ee_kwargs(setting):
    """The ``smileRandomForest`` keyword arguments of a setting or table row."""
    return {k: v for k, v in setting.items() if k not in _NOT_KWARGS}


def classifier(setting):
    """An untrained Earth Engine regression forest for one setting."""
    return ee.Classifier.smileRandomForest(**ee_kwargs(setting)).setOutputMode("REGRESSION")


def make_folds(coords, block_sizes=BLOCK_SIZES, n_folds=N_FOLDS, seed=SEED):
    """Spatial-block folds per block size: blocks shuffled with ``seed`` and
    dealt round-robin to ``n_folds`` folds (the notebooks' rule)."""
    folds = {}
    for b in block_sizes:
        bx = (coords[:, 0] // b).astype(int)
        by = (coords[:, 1] // b).astype(int)
        ids = np.array([f"{x}_{y}" for x, y in zip(bx, by)])
        order = np.random.RandomState(seed).permutation(np.unique(ids))
        fmap = {blk: i % n_folds for i, blk in enumerate(order)}
        folds[b] = np.array([fmap[blk] for blk in ids])
    return folds


def points_fc(gdf, bands, label, folds):
    """The points as one FeatureCollection: bands, label, row index and one
    fold column per block size (``fold_500`` ...)."""
    cols = {f"fold_{b}": f for b, f in folds.items()}
    return ee.FeatureCollection([
        ee.Feature(None, {**{b: float(v) for b, v in zip(bands, row)}, label: float(y), "row": i,
                          **{k: int(f[i]) for k, f in cols.items()}})
        for i, (row, y) in enumerate(zip(gdf[bands].values, gdf[label].values))])


def _retry(fn, tries=4):
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:                       # throttling, timeouts
            if attempt == tries - 1:
                raise
            print(f"    retry {attempt + 1} after: {str(e)[:120]}", flush=True)
            time.sleep(15 * (attempt + 1))


def _fold_sse(fc, bands, label, setting, block):
    """One request: per fold, train on the other folds and return (SSE, n)."""
    prop, clf = f"fold_{block}", classifier(setting)

    def one(k):
        k = ee.Number(k)
        trained = clf.train(fc.filter(ee.Filter.neq(prop, k)), label, bands)
        pred = fc.filter(ee.Filter.eq(prop, k)).classify(trained)
        se = pred.map(lambda f: f.set("se", ee.Number(f.get("classification")).max(0).min(100)
                                      .subtract(f.get(label)).pow(2)))
        return ee.List([se.aggregate_sum("se"), se.size()])
    return ee.List.sequence(0, N_FOLDS - 1).map(one).getInfo()


def tune(fc, bands, label, block_sizes=BLOCK_SIZES, workers=WORKERS):
    """Search every setting at every block size; return (table, best).

    ``table`` has one row per (block, setting) with the mean and std of the
    fold RMSE; ``best`` is the row with the lowest mean (the notebooks' rule).
    """
    grid = settings(len(bands))
    jobs = [(b, i) for b in block_sizes for i in range(len(grid))]
    rows, t0 = [], time.time()

    def run(job):
        b, i = job
        folds = _retry(lambda: _fold_sse(fc, bands, label, grid[i], b))
        rmse = [float(np.sqrt(s / n)) for s, n in folds]
        return {"block": b, "setting": i, **grid[i],
                "cv_rmse": float(np.mean(rmse)), "cv_std": float(np.std(rmse))}

    with ThreadPoolExecutor(workers) as pool:
        for n, fut in enumerate(as_completed([pool.submit(run, j) for j in jobs]), 1):
            rows.append(fut.result())
            if n % 20 == 0 or n == len(jobs):
                print(f"  tuning: {n}/{len(jobs)} done, {(time.time() - t0) / 60:.1f} min", flush=True)
    rows.sort(key=lambda r: (r["block"], r["setting"]))
    best = min(rows, key=lambda r: r["cv_rmse"])
    for b in block_sizes:
        rb = min((r for r in rows if r["block"] == b), key=lambda r: r["cv_rmse"])
        print(f"  {b} m: best CV RMSE {rb['cv_rmse']:.3f} +/- {rb['cv_std']:.3f}  (setting {rb['setting']})")
    print(f"  => chosen: {best['block']} m, {ee_kwargs(best)}")
    return rows, best


def oof_predictions(fc, bands, label, best):
    """Out-of-fold prediction for every point at the chosen block size, and
    the CV metrics from them. Bias is observed minus predicted."""
    prop, clf = f"fold_{best['block']}", classifier(best)

    def one(k):
        k = ee.Number(k)
        trained = clf.train(fc.filter(ee.Filter.neq(prop, k)), label, bands)
        return (fc.filter(ee.Filter.eq(prop, k)).classify(trained)
                .reduceColumns(ee.Reducer.toList(2), ["row", "classification"]).get("list"))
    per_fold = _retry(lambda: ee.List.sequence(0, N_FOLDS - 1).map(one).getInfo())
    obs = np.array(_retry(lambda: fc.aggregate_array(label).getInfo()), dtype=float)
    pred = np.full(len(obs), np.nan)
    for fold in per_fold:
        for r, p in fold:
            pred[int(r)] = p
    assert np.isfinite(pred).all(), "some points got no out-of-fold prediction"
    pred = np.clip(pred, 0, 100)
    resid = obs - pred
    metrics = {"block": best["block"], "rmse": float(np.sqrt(np.mean(resid ** 2))),
               "mae": float(np.mean(np.abs(resid))),
               "r2": float(1 - np.sum(resid ** 2) / np.sum((obs - obs.mean()) ** 2)),
               "bias": float(resid.mean()), "n": int(len(obs))}
    print("  out-of-fold: " + ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                                        for k, v in metrics.items()))
    return pred, metrics


def train_final(fc, bands, label, best):
    """The map's forest: the chosen setting trained on all points."""
    return classifier(best).train(fc, label, bands)


def predict_points(clf, X, bands, chunk=500):
    """Predict an array of band values with a trained classifier (chunked to
    stay under the 10 MB request limit), clipped to 0-100.

    Reads the default ``classification`` output: a classifier loaded from an
    asset ignores a requested output name, and must not be passed through
    ``setOutputMode`` (that rebuilds it untrained)."""
    pred = np.full(len(X), np.nan)
    for start in range(0, len(X), chunk):
        fc = ee.FeatureCollection([
            ee.Feature(None, {"row": start + i, **{b: float(v) for b, v in zip(bands, row)}})
            for i, row in enumerate(X[start:start + chunk])])
        for r, p in _retry(lambda: fc.classify(clf).reduceColumns(
                ee.Reducer.toList(2), ["row", "classification"]).get("list").getInfo()):
            pred[int(r)] = p
    assert np.isfinite(pred).all(), "some points got no prediction"
    return np.clip(pred, 0, 100)


def model_record(best, table, cv, source, city, predictor, bands, label, n_points):
    """Everything that defines the forest: with the feature table it names,
    :func:`load_model` rebuilds the identical forest (training is deterministic
    for fixed points, settings and seed)."""
    return {"engine": "Earth Engine smileRandomForest (REGRESSION)",
            "feature_table": {"source": source, "city": city, "predictor": predictor},
            "label": label, "bands": list(bands), "n_points": int(n_points),
            "max_features": best["max_features"], "block": best["block"],
            "earth_engine_kwargs": ee_kwargs(best), "cv": cv, "tuning": table}


def save_model(clf, record, json_path):
    """Keep the model: its record (see :func:`model_record`) plus the forest's
    own importances from ``explain()`` (trees omitted), written to ``json_path``.

    Not an Earth Engine classifier asset: a regression forest exported with
    ``Export.classifier.toAsset`` loads back without its trees (``explain()``
    empty, predictions wrong), so the model is kept as its exact recipe."""
    explain = _retry(lambda: ee.Dictionary(clf.explain()).remove(["trees"], True).getInfo())
    record = {**record, "explain": explain, "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(json_path, "w") as f:
        json.dump(record, f, indent=2, default=str)
    print(f"  model record -> {json_path}")
    return record


def load_model(json_path):
    """Rebuild the identical trained forest from a saved record: the same
    points, label, bands, settings and seed. Returns (classifier, record)."""
    import sample_features as sf

    with open(json_path) as f:
        record = json.load(f)
    t = record["feature_table"]
    gdf, _ = sf.load_features(t["source"], t["city"], t["predictor"])
    assert len(gdf) == record["n_points"], f"{json_path}: point count changed"
    bands, label = record["bands"], record["label"]
    fc = ee.FeatureCollection([
        ee.Feature(None, {**{b: float(v) for b, v in zip(bands, row)}, label: float(y)})
        for row, y in zip(gdf[bands].values, gdf[label].values)])
    clf = (ee.Classifier.smileRandomForest(**record["earth_engine_kwargs"])
           .setOutputMode("REGRESSION").train(fc, label, bands))
    return clf, record
