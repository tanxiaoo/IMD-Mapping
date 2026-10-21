"""The random forest, defined once for scikit-learn and Earth Engine.

Every notebook tunes a ``RandomForestRegressor`` in scikit-learn and then
builds the map with Earth Engine's ``smileRandomForest``, because only Earth
Engine can classify the full-resolution image. The map is therefore only the
tuned model if every tuned setting reaches Earth Engine. Until this module,
notebooks 01/01b/01c/01d passed ``numberOfTrees`` and ``minLeafPopulation``
alone, so ``variablesPerSplit`` fell to its default (sqrt of the band count)
and ``bagFraction`` to 0.5 whatever tuning chose; 02/03 passed more, but
hardcoded the bag fraction.

So the tuning space is restricted to settings with an exact Earth Engine
counterpart, and the translation lives here, next to it:

    =====================  ======================  ==========================
    scikit-learn           Earth Engine            translation
    =====================  ======================  ==========================
    ``n_estimators``       ``numberOfTrees``       same value
    ``max_features``       ``variablesPerSplit``   resolved to a band count
                                                   with sklearn's own rule
    ``min_samples_leaf``   ``minLeafPopulation``   same value
    ``max_leaf_nodes``     ``maxNodes``            same value (None = no cap)
    bootstrap, full size   ``bagFraction=1.0``     both draw n samples with
                                                   replacement
    =====================  ======================  ==========================

Settings that do not translate are kept out of the tuning space and fixed at
the sklearn defaults Earth Engine also uses: ``max_depth`` (a depth limit has
no Earth Engine form; ``max_leaf_nodes`` limits tree size instead),
``min_samples_split`` (no counterpart), ``max_samples`` (Smile subsamples
*without* replacement below 1.0, sklearn with replacement, so only 1.0 means
the same thing) and ``bootstrap=False`` (Earth Engine always bags).

:func:`rf_classifier` refuses parameters that would not translate, so a model
tuned outside this space cannot silently be rebuilt as a different one. The
two forests still differ in their random draws, so their predictions agree
closely but not exactly; :func:`compare_predictions` measures by how much.
"""

import numpy as np

import ee

# The shared tuning space. Every key has an exact Earth Engine counterpart.
RF_PARAM_SPACE = {
    "n_estimators":     [100, 200, 300, 500],
    "max_features":     ["sqrt", "log2", 0.3, 0.5],
    "min_samples_leaf": [1, 2, 4],
    "max_leaf_nodes":   [None, 250, 500, 1000],
}

# Settings that must stay at these values for the translation to hold.
_FIXED = {
    "max_depth": None,
    "min_samples_split": 2,
    "max_samples": None,
    "bootstrap": True,
    "criterion": "squared_error",
    "min_weight_fraction_leaf": 0.0,
    "min_impurity_decrease": 0.0,
    "ccp_alpha": 0.0,
}


def _parse(value):
    """Undo the ``str()`` that model_metadata*.json applies to every param."""
    if not isinstance(value, str):
        return value
    s = value.strip().strip("'\"")
    if s == "None":
        return None
    if s in ("True", "False"):
        return s == "True"
    for cast in (int, float):
        try:
            return cast(s)
        except ValueError:
            pass
    return s


def variables_per_split(max_features, n_features):
    """Bands tried per split, by scikit-learn's rule for ``max_features``."""
    if max_features is None or max_features == 1.0:
        return n_features
    if max_features == "sqrt":
        return max(1, int(np.sqrt(n_features)))
    if max_features == "log2":
        return max(1, int(np.log2(n_features)))
    if isinstance(max_features, float):
        return max(1, int(max_features * n_features))
    if isinstance(max_features, int):
        return max_features
    raise ValueError(f"max_features={max_features!r} has no Earth Engine translation")


def rf_gee_params(params, n_features):
    """Translate RF parameters to ``smileRandomForest`` keyword arguments.

    ``params`` is ``RandomForestRegressor.get_params()`` or the ``best_params``
    dict of a saved model_metadata JSON (where every value is a string).
    Raises if a parameter is set to a value Earth Engine cannot reproduce.
    """
    p = {k: _parse(v) for k, v in params.items()}
    bad = {k: p[k] for k, default in _FIXED.items() if k in p and p[k] != default}
    if bad:
        raise ValueError(
            f"These RF settings have no exact Earth Engine counterpart: {bad}. "
            "Tune with gee_models.RF_PARAM_SPACE; a model saved before that "
            "space existed must be re-tuned, not translated.")
    gee = {
        "numberOfTrees":     int(p.get("n_estimators", 100)),
        "variablesPerSplit": variables_per_split(p.get("max_features", 1.0), n_features),
        "minLeafPopulation": int(p.get("min_samples_leaf", 1)),
        "bagFraction":       1.0,
    }
    if p.get("max_leaf_nodes") is not None:
        gee["maxNodes"] = int(p["max_leaf_nodes"])
    return gee


def rf_classifier(params, n_features, seed):
    """An untrained Earth Engine regression forest matching ``params``."""
    gee = rf_gee_params(params, n_features)
    return ee.Classifier.smileRandomForest(**gee, seed=seed).setOutputMode("REGRESSION")


def training_fc(df, band_names, label):
    """A geometry-free FeatureCollection of ``band_names`` plus ``label``."""
    return ee.FeatureCollection([
        ee.Feature(None, {**{b: float(row[b]) for b in band_names}, label: float(row[label])})
        for _, row in df.iterrows()])


def compare_predictions(trained_clf, sk_model, X, band_names, y_true=None, chunk=500):
    """Predict ``X`` with both forests and report how far apart they are.

    Returns the two prediction arrays and the summary it prints. ``X`` is sent
    in chunks: every request also carries the trained forest's training points
    inline, and the two together must stay under Earth Engine's 10 MB payload
    limit (3,500 training points x 64 bands is already about half of it).
    """
    gee_pred = np.empty(len(X))
    for start in range(0, len(X), chunk):
        fc = ee.FeatureCollection([
            ee.Feature(None, {"idx": start + i, **{b: float(v) for b, v in zip(band_names, row)}})
            for i, row in enumerate(X[start:start + chunk])])
        cols = (fc.classify(trained_clf, "pred")
                .reduceColumns(ee.Reducer.toList(2), ["idx", "pred"]).get("list").getInfo())
        for i, v in cols:
            gee_pred[int(i)] = v
    gee_pred = np.clip(gee_pred, 0, 100)
    sk_pred = np.clip(sk_model.predict(X), 0, 100)

    diff = gee_pred - sk_pred
    summary = {
        "n": len(X),
        "mean_abs_diff": float(np.mean(np.abs(diff))),
        "rms_diff": float(np.sqrt(np.mean(diff ** 2))),
        "corr": float(np.corrcoef(gee_pred, sk_pred)[0, 1]),
    }
    if y_true is not None:
        for name, pred in (("sklearn", sk_pred), ("gee", gee_pred)):
            summary[f"rmse_{name}"] = float(np.sqrt(np.mean((y_true - pred) ** 2)))
    print("  Earth Engine vs scikit-learn RF on the given points: "
          + ", ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                      for k, v in summary.items()))
    return gee_pred, sk_pred, summary
