"""Shared Sentinel-2 helpers for the IMD baseline.

Imported by BOTH 00_S2_Extraction_Milan_2018.ipynb (which extracts the
training table) and 01b_IMD_Prediction_Milan_blockCV_S2.ipynb (which exports
the prediction raster). The mask and composite definitions MUST NOT diverge
between the two: the holdout evaluation compares points sampled from the
exported raster against a model trained on the extracted table, so a
divergence here would silently invalidate the metrics.

Notebook 00 writes ``method`` and ``band_names`` into
``s2_extraction_metadata.json``; notebook 01b reads both back and asserts the
band names match. That handshake is what keeps the two notebooks building the
same image now that the composite method is switchable.
"""

import ee

# ── Band set ──────────────────────────────────────────────────────────────────
# B2,B3,B4,B8 are native 10 m; the rest are 20 m resampled to the 10 m grid.
# SWIR (B11/B12) is the key impervious-surface signal.
S2_BANDS = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']

# ── SCL (Sen2Cor scene classification) classes ────────────────────────────────
#  0 no-data       1 saturated/defective   2 dark area
#  3 cloud shadow  4 vegetation            5 bare soil
#  6 water         7 unclassified          8 cloud medium prob
#  9 cloud high p 10 thin cirrus          11 snow/ice
CLOUD_CLASSES   = [3, 8, 9, 10]                 # cloud + shadow + cirrus
INVALID_CLASSES = [0, 1, 3, 8, 9, 10, 11]       # + no-data, defective, snow

# Optional stricter cloud edge via the cloud-probability band.
USE_CLDPRB    = True
CLDPRB_THRESH = 40

# Composite methods available to ``build_composite`` (see its docstring).
COMPOSITE_METHODS = ('median', 'percentile', 'stack')

# Percentiles emitted by method='percentile', and the minimum stack depth that
# makes them meaningful. Below this, p25/p75 are each pinned by 2-3
# observations and a single surviving cloud edge moves them.
PERCENTILES          = (25, 50, 75)
MIN_DATES_PERCENTILE = 10


# Bands every image is reduced to before any mosaic/median.
# The 2018 S2_SR archive is NOT band-homogeneous: some scenes carry
# MSK_CLDPRB/MSK_SNWPRB where others carry QA10/QA20/QA60, so mosaic() over the
# raw collection raises "Expected a homogeneous image collection". Selecting a
# fixed subset first makes the collection uniform.
_CORE_BANDS = S2_BANDS + ['SCL']


def harmonize(img):
    """Reduce an S2 image to a fixed band set so collections are homogeneous.

    ``MSK_CLDPRB`` is appended only when present; scenes lacking it get a
    constant 0 stand-in (0 = "not cloudy per the probability band"), so the
    optional probability gate never changes a pixel's fate on those scenes and
    never raises for a missing band.
    """
    img = ee.Image(img)
    base = img.select(_CORE_BANDS)
    if not USE_CLDPRB:
        return base.copyProperties(img, img.propertyNames())

    has = img.bandNames().contains('MSK_CLDPRB')
    cldprb = ee.Image(ee.Algorithms.If(
        has,
        img.select('MSK_CLDPRB'),
        ee.Image.constant(0).rename('MSK_CLDPRB').updateMask(img.select('SCL').mask()),
    )).rename('MSK_CLDPRB').toUint16()
    return base.addBands(cldprb).copyProperties(img, img.propertyNames())


def cloud_mask(img):
    """1 where cloud/shadow/cirrus, else 0. Used for the AOI_cloud% statistic.

    Unmasked (see ``valid_mask``) so ``reduceRegion(mean)`` counts no-data
    pixels as "not cloud" instead of skipping them.
    """
    scl = ee.Image(img).select('SCL')
    return (scl.remap(CLOUD_CLASSES, [1] * len(CLOUD_CLASSES), 0)
            .unmask(0).rename('cloud'))


def valid_mask(img):
    """1 where the pixel is usable, else 0.

    Stricter than ``cloud_mask.Not()``: also drops no-data, saturated/defective
    and snow. This is the mask actually applied to the composite, and the one
    whose statistics the scene table reports.

    Expects a ``harmonize``-d image when ``USE_CLDPRB`` is on.

    The result is deliberately **unmasked** (0 where unusable) rather than
    masked. ``reduceRegion(mean)`` skips masked pixels, so a masked version
    returns ``None`` for a fully-clouded scene instead of the 0% it should
    report -- the mean of an empty set. Callers that want it as an actual mask
    pass it to ``updateMask``, where 0 masks the pixel anyway.
    """
    img = ee.Image(img)
    scl = img.select('SCL')
    bad = scl.remap(INVALID_CLASSES, [1] * len(INVALID_CLASSES), 0)
    valid = bad.Not()
    if USE_CLDPRB:
        # Tolerate a non-harmonized image rather than raising on a missing band.
        valid = ee.Image(ee.Algorithms.If(
            img.bandNames().contains('MSK_CLDPRB'),
            valid.And(img.select('MSK_CLDPRB').lt(CLDPRB_THRESH)),
            valid,
        ))
    return valid.unmask(0).rename('valid')


def water_mask(aoi_geom):
    """ESA WorldCover non-water mask -- copied verbatim from notebook 01 cell 6."""
    return (ee.ImageCollection('ESA/WorldCover/v200')
            .filter(ee.Filter.bounds(aoi_geom))
            .mosaic().clip(aoi_geom)).neq(80)


def _masked_collection(collection_id, selected_dates, aoi_geom):
    """Cloud-masked S2 collection over ``selected_dates``, plus B2's projection.

    Everything up to (but not including) the reduction, shared by every
    ``build_composite`` method. Masking happens HERE, before any reduction, so
    cloudy observations are excluded from the sample entirely rather than
    averaged in.
    """
    date_filter = ee.Filter.Or(*[
        ee.Filter.date(d, ee.Date(d).advance(1, 'day')) for d in selected_dates
    ])
    col = (ee.ImageCollection(collection_id)
           .filter(ee.Filter.bounds(aoi_geom))
           .filter(date_filter)
           .map(harmonize))          # uniform bands -> median() won't raise

    proj = col.first().select('B2').projection()
    return col.map(lambda i: i.updateMask(valid_mask(i))), proj


def _reduce_median(masked, selected_dates):
    """Per-pixel median across all dates. 10 bands, named ``S2_BANDS``."""
    return masked.median(), list(S2_BANDS)


def _reduce_percentile(masked, selected_dates):
    """Per-pixel p25/p50/p75 per band. 30 bands, named ``B2_p25 ... B12_p75``.

    The p75-p25 spread is a direct proxy for temporal stability -- asphalt and
    roofs barely move across the year while crops and bare soil swing widely --
    which is the defining property of an impervious surface.
    """
    if len(selected_dates) < MIN_DATES_PERCENTILE:
        raise ValueError(
            f"method='percentile' needs >= {MIN_DATES_PERCENTILE} dates, got "
            f'{len(selected_dates)}. Over a shorter stack p25 and p75 are each '
            'pinned by 2-3 observations, so one surviving cloud edge moves '
            'them. Widen SELECTED_DATES (the scene table has ~30 usable dates '
            "for 2018) or use method='median'.")

    names = [f'{b}_p{p}' for b in S2_BANDS for p in PERCENTILES]
    # GEE names these '<band>_p<n>' already; the explicit select() in
    # build_composite pins the ORDER to `names` regardless.
    return masked.reduce(ee.Reducer.percentile(list(PERCENTILES))), names


def _reduce_stack(masked, selected_dates):
    """No reduction -- every date contributes its own 10 bands as features.

    ``10 * len(selected_dates)`` bands named ``B2_d00 ... B12_dNN``, in sorted
    date order so the band list is a function of the dates themselves, not of
    the order they happened to be typed in.

    Masked pixels are gap-filled from the per-pixel median across all selected
    dates, because a pixel clouded on any single date would otherwise drop the
    whole point -- and with N dates the odds of a point being clean on all N
    approach zero. Filled values are NOT observations and the model cannot tell
    them apart from real ones; cloud is also not randomly distributed, so the
    fill lands unevenly across the AOI. Keep N small (3-6) and check the
    per-date fill rate before attributing any gain to temporal information.
    """
    dates = sorted(selected_dates)
    fill  = masked.median()          # 10 bands, S2_BANDS names

    per_date = []
    for i, d in enumerate(dates):
        day   = ee.Date(d)
        names = [f'{b}_d{i:02d}' for b in S2_BANDS]
        # mosaic(), not median(): Milan spans several MGRS tiles, so one date
        # is usually 2+ scenes. Mosaicking keeps a date a single observation.
        img = (masked.filter(ee.Filter.date(day, day.advance(1, 'day')))
               .mosaic().select(S2_BANDS).rename(names))
        per_date.append(img.unmask(fill.rename(names)))

    names = [f'{b}_d{i:02d}' for i in range(len(dates)) for b in S2_BANDS]
    return ee.Image.cat(per_date), names


_REDUCERS = {
    'median':     _reduce_median,
    'percentile': _reduce_percentile,
    'stack':      _reduce_stack,
}


def build_composite(collection_id, selected_dates, aoi_geom, non_water=None,
                    method='median'):
    """Composite ``selected_dates`` of cloud-masked S2 imagery.

    ``method`` selects how the dates are combined:

    ==============  ======================  ==========================________
    method          bands                   what it does
    ==============  ======================  ==========================________
    ``median``      10                      per-pixel median (the default)
    ``percentile``  30                      p25/p50/p75 per band, >= 10 dates
    ``stack``       ``10 * n_dates``        no reduction; each date's own bands
    ==============  ======================  ==========================________

    Returns ``(image, projection, band_names)``. ``band_names`` is
    method-dependent and is the single source of truth for the feature columns
    downstream -- notebook 00 writes it to the metadata JSON and notebook 01b
    asserts against it. Do NOT re-derive it from ``image.bandNames().getInfo()``
    at the call site: that costs a round-trip and carries no ordering
    guarantee, so the training table's columns could silently permute relative
    to the classifier's ``inputProperties``. ``S2_BANDS`` keeps its own,
    method-independent meaning: the 10 raw bands each scene is harmonized to.

    The image is reprojected onto B2's 10 m grid so the 20 m bands come back at
    10 m. Reflectance stays raw DN (0-10000): RF is scale-invariant and the
    SVR/MLP pipelines wrap a StandardScaler -- fitted per-fold inside the CV,
    which is the correct place -- so rescaling here would change nothing while
    adding a needless divergence from notebook 01.
    """
    if method not in _REDUCERS:
        raise ValueError(f'Unknown method {method!r}. '
                         f'Expected one of {COMPOSITE_METHODS}.')
    if not selected_dates:
        raise ValueError('selected_dates is empty.')
    if len(set(selected_dates)) != len(selected_dates):
        raise ValueError('selected_dates contains duplicates -- under '
                         "method='stack' that would double-weight a date.")

    if non_water is None:
        non_water = water_mask(aoi_geom)

    masked, proj    = _masked_collection(collection_id, selected_dates, aoi_geom)
    img, band_names = _REDUCERS[method](masked, selected_dates)

    img = (img.select(band_names)     # pins band order to the Python list
           .setDefaultProjection(proj)
           .clip(aoi_geom)
           .updateMask(non_water))
    return img, proj, band_names


def stack_fill_rates(collection_id, selected_dates, aoi_geom, scale=60):
    """Fraction of the AOI gap-filled per date under ``method='stack'``.

    Client-side dict ``{date: pct}`` -- one ``reduceRegion`` per date, so it is
    cheap at ``scale=60`` but not free. A date filling more than a few percent
    is contributing mostly synthetic features and should be swapped out.
    """
    masked, _ = _masked_collection(collection_id, selected_dates, aoi_geom)

    rates = {}
    for d in sorted(selected_dates):
        day = ee.Date(d)
        # B2's mask after valid_mask: 1 where the date has a real observation.
        present = (masked.filter(ee.Filter.date(day, day.advance(1, 'day')))
                   .mosaic().select('B2').mask().unmask(0))
        got = present.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi_geom,
                                   scale=scale, bestEffort=True,
                                   maxPixels=1e9).values().get(0)
        rates[d] = round((1 - ee.Number(got).getInfo()) * 100, 3)
    return rates
