"""Shared Sentinel-2 helpers for the IMD baseline.

Imported by BOTH 00_S2_Extraction_Milan_2018.ipynb (which extracts the
training table) and 01b_IMD_Prediction_Milan_blockCV_S2.ipynb (which exports
the prediction raster). The mask and composite definitions MUST NOT diverge
between the two: the holdout evaluation compares points sampled from the
exported raster against a model trained on the extracted table, so a
divergence here would silently invalidate the metrics.
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


def build_composite(collection_id, selected_dates, aoi_geom, non_water=None):
    """Per-pixel median over ``selected_dates`` of cloud-masked S2 imagery.

    Returns ``(image, projection)``. The image carries exactly ``S2_BANDS``,
    reprojected onto B2's 10 m grid so the 20 m bands come back at 10 m.
    Reflectance is kept as raw DN (0-10000): RF is scale-invariant and the
    SVR/MLP pipelines wrap a StandardScaler, so rescaling would change nothing
    while adding a needless divergence from notebook 01.
    """
    if non_water is None:
        non_water = water_mask(aoi_geom)

    date_filter = ee.Filter.Or(*[
        ee.Filter.date(d, ee.Date(d).advance(1, 'day')) for d in selected_dates
    ])
    col = (ee.ImageCollection(collection_id)
           .filter(ee.Filter.bounds(aoi_geom))
           .filter(date_filter)
           .map(harmonize))          # uniform bands -> median() won't raise

    proj = col.first().select('B2').projection()

    masked = col.map(lambda i: i.updateMask(valid_mask(i)))
    img = (masked.median()
           .select(S2_BANDS)
           .setDefaultProjection(proj)
           .clip(aoi_geom)
           .updateMask(non_water))
    return img, proj
