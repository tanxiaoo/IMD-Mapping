"""Where every run writes, and the registry of every predicted map.

The single place that builds output paths. Notebooks 01-05 and the report
scripts import it instead of writing path strings by hand, so the layout can be
read (and changed) in one file.

Layout (city / training points / label / predictor)::

    output/milan/<points>_points/<label>/<predictor>/
        IMD_Milan_10m_<predictor>_<POINTS>pts_<LABEL>.tif, model_rf.json, ...
    output/transfer_vietnam/<city>/<predictor>/local/
        IMD_<City>_10m_<predictor>_local.tif, model_rf.json, ...
    output/transfer_vietnam/<city>/<predictor>/transfer_<points>_points_<label>/
        IMD_<City>_10m_<predictor>_transfer_Milan<POINTS>pts_<LABEL>.tif
    output/transfer_vietnam/hanoi_and_hcmc/<predictor>/   two-city files only

``points`` is the point set the model was trained on (the product that point
set was stratified on), ``label`` the product whose values were the target.
Direct cross-city transfer applies a Milan model, unchanged, to Hanoi or HCMC;
the transfer folder and file name say which Milan model.

Every raster name carries city, predictor, scenario and source, so a copied
file keeps its identity.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parent
OUT = REPO / "output"
DATA = REPO / "data"

PREDICTORS = ("embedding", "median", "stack", "percentile")
SHORT = {"embedding": "emb", "median": "median", "stack": "stack", "percentile": "percentile"}
# Milan models moved to Vietnam: stack and percentile cannot be transferred
# (Milan's stack has 40 bands, Hanoi's 30 and HCMC's 10; neither city has the
# dates a percentile composite needs).
TRANSFER_PREDICTORS = ("embedding", "median")
# (points, label) of every Milan model; also the Milan sources of a transfer.
MILAN_RUNS = (("clms", "clms"), ("clms", "ghsl"), ("ghsl", "ghsl"))
VIETNAM = ("Hanoi", "HCMC")

PRODUCTS = {
    ("Milan", "clms"): DATA / "CLMS_2018_Milan_UTM32N.tif",
    ("Milan", "ghsl"): DATA / "GHSL_2018_Milan_UTM32N.tif",
    ("Hanoi", "ghsl"): DATA / "GHSL_2018_Hanoi_UTM48N.tif",
    ("HCMC", "ghsl"): DATA / "GHSL_2018_HCMC_UTM48N.tif",
}


def _tag(points, label):
    """'CLMSpts_GHSL': trained on the CLMS points with GHSL values."""
    return f"{points.upper()}pts_{label.upper()}"


# ── Milan ────────────────────────────────────────────────────────────────────
def milan_dir(points, label, predictor):
    return OUT / "milan" / f"{points}_points" / label / predictor


def milan_raster(points, label, predictor):
    return milan_dir(points, label, predictor) / f"IMD_Milan_10m_{predictor}_{_tag(points, label)}.tif"


def milan_model(points, label, predictor):
    return milan_dir(points, label, predictor) / "model_rf.json"


# ── Hanoi and HCMC ───────────────────────────────────────────────────────────
def scenario_name(source=None):
    """'local', or 'transfer_<points>_points_<label>' for a Milan source."""
    return "local" if source is None else f"transfer_{source[0]}_points_{source[1]}"


def vietnam_dir(city, predictor, source=None):
    """``source`` None is the local retrain; a (points, label) pair is the
    direct cross-city transfer of that Milan model."""
    return OUT / "transfer_vietnam" / city.lower() / predictor / scenario_name(source)


def vietnam_raster(city, predictor, source=None):
    tail = "local" if source is None else f"transfer_Milan{_tag(*source)}"
    return vietnam_dir(city, predictor, source) / f"IMD_{city}_10m_{predictor}_{tail}.tif"


def vietnam_model(city, predictor):
    """The local model (a transfer has no model of its own: it is Milan's)."""
    return vietnam_dir(city, predictor) / "model_rf.json"


def city_predictor_dir(city, predictor):
    """One city's files that compare its scenarios (scatter, per-class)."""
    return OUT / "transfer_vietnam" / city.lower() / predictor


def two_city_dir(predictor):
    return OUT / "transfer_vietnam" / "hanoi_and_hcmc" / predictor


# ── Evaluation outputs ───────────────────────────────────────────────────────
BENCHMARK_DIFF = OUT / "benchmark_difference"
VALIDATION = OUT / "validation_independent"
INTERPRETER = OUT / "interpreter_agreement"
SAMPLING = OUT / "sampling"


def validation_dir(city):
    return VALIDATION / f"{city}_2018"


# ── Registry of every predicted map ──────────────────────────────────────────
def map_key(city, predictor, source=None, points=None, label=None):
    """The name a map carries in every table (notebooks 04 and 05)."""
    p = SHORT[predictor]
    if city == "Milan":
        return f"{p}_{_tag(points, label)}"
    return f"{p}_local" if source is None else f"{p}_transfer_{_tag(*source)}"


def maps(city=None):
    """Every predicted map, in table order: dicts with city, key, predictor,
    points, label (the training product), transfer (bool), raster."""
    out = []
    for points, label in MILAN_RUNS:
        for pred in PREDICTORS:
            out.append(dict(city="Milan", key=map_key("Milan", pred, points=points, label=label),
                            predictor=pred, points=points, label=label, transfer=False,
                            raster=milan_raster(points, label, pred)))
    for c in VIETNAM:
        for pred in ("embedding", "median", "stack"):
            out.append(dict(city=c, key=map_key(c, pred), predictor=pred, points="ghsl",
                            label="ghsl", transfer=False, raster=vietnam_raster(c, pred)))
        for pred in TRANSFER_PREDICTORS:
            for src in MILAN_RUNS:
                out.append(dict(city=c, key=map_key(c, pred, src), predictor=pred,
                                points=src[0], label=src[1], transfer=True,
                                raster=vietnam_raster(c, pred, src)))
    return [m for m in out if city is None or m["city"] == city]


def products(city):
    """The reference products evaluated beside the maps: {key: path}."""
    return {lab.upper(): p for (c, lab), p in PRODUCTS.items() if c == city}
