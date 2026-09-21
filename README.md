# IMD-Mapping

**Can AlphaEarth replace locally composed Sentinel-2 for 10 m imperviousness
mapping, and does it transfer across cities?**

Impervious surface — the share of a pixel covered by artificial,
water-impermeable material — drives urban runoff, flood risk and surface heat.
Mapping it at 10 m for Milan, Hanoi and Ho Chi Minh City in 2018.

## The question

AlphaEarth embeddings are attractive because they are ready to use: 64 learned
bands, one global annual product, no compositing to get right. The alternative
is more work — searching Sentinel-2 scenes, screening cloud, building a
composite for each city. Whether that work pays for itself is the first
question, and whether either choice survives being carried to a new city is the
second.

**Can AlphaEarth replace locally composed Sentinel-2?** Four predictor sets are
compared on Milan under identical conditions — same sample points, same
train/test split, same models — so the only thing that varies is the input:

| Predictor | What it is |
|---|---|
| AlphaEarth embeddings | 64 learned bands from [Google Satellite Embedding V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL), used as supplied |
| Sentinel-2 median | 10 reflectance bands, per-pixel median of cloud-free 2018 dates |
| Sentinel-2 stack | the same dates kept as separate bands |
| Sentinel-2 percentile | five percentiles per band, capturing within-year variation |

**Does it transfer across cities?** The Milan models are applied to Hanoi and
HCMC two ways: *zero-shot*, with no local data at all, and *locally retrained*,
using a sample of local labels. The gap between them is what a city gains by
collecting its own training data.

Both answers are then checked twice: against the same reference the models were
trained on, and against an independent set of 450 photo-interpreted plots per
city, which no model ever saw. The two are never merged — a model can beat its
own training reference and still be wrong about the ground.

## What is here

The full write-up is `report/report.pdf`, with `report/IMD_Mapping.pptx` as
the accompanying deck. The notebooks are the pipeline that produced them.

```
00_S2_Extraction_Milan_2018.ipynb               Sentinel-2 scene search + extraction
00b_S2_Extraction_Vietnam_2018.ipynb            the same for Hanoi and HCMC
ghsl_data_preparation.ipynb                     GHSL clipped, reclassified, resampled

01_IMD_Prediction_Milan_blockCV_embedding.ipynb Milan, embeddings
01b_IMD_Prediction_Milan_blockCV_S2.ipynb       Milan, Sentinel-2
01c_IMD_Prediction_Milan_blockCV_GHSL.ipynb     the same, GHSL-labelled
01d_IMD_Prediction_Milan_blockCV_S2_GHSL.ipynb  the same, GHSL-labelled

02_Transferability_Vietnam_v2.ipynb             Hanoi / HCMC transfer, embeddings
03_Transferability_Vietnam_S2_median.ipynb      the same, Sentinel-2

04_Validation_PhotoInterpreted.ipynb            independent validation, 450 plots/city
05_imd_Groundtruth_validation.ipynb             confusion matrices per map

s2_utils.py                                     shared cloud masks + composite builder
```

Run them in order: extract, model, transfer, validate.

### Where things live

```
data/     inputs only — reference rasters, sample points, the AOI.
          Nothing a notebook writes ever lands here.

output/   every run, as city / label source / predictor:
            milan/{clms,ghsl}/{embedding,median,stack,percentile}/
            hanoi/{embedding,median}/  hcmc/{embedding,median}/
            transfer/{embedding,median}/   two-city comparison files
            milan/validation/              photo-interpreted validation

report/   report.tex, report.pdf, IMD_Mapping.pptx
```

> **Code only.** `data/` and `output/` are around 5 GB of rasters, models and
> sample points — regenerable by re-running the notebooks, and the GeoTIFFs
> exceed GitHub's file size limit. Neither is in this repository, and neither
> are the report's own sources beyond `report.tex`.

## Method in brief

**Sampling.** 3500 points per city, 500 in each of seven density classes, so
sparse classes are not swamped by the dominant one.

**Spatial cross-validation.** Ordinary random CV leaks between neighbouring
pixels and reports accuracy that does not survive contact with new ground.
Points are grouped into square blocks, whole blocks go to folds, and a 250 m
buffer drops validation points sitting too close to a training point. The
locked train/test split is scored exactly once.

**Models.** Random Forest and SVR, tuned under those same spatial folds, with
the winner retrained server-side in Earth Engine and exported as a 10 m raster.

**Two references.** Milan models are trained against CLMS and, separately,
against GHS-BUILT-S, to see how much of the result is the method and how much
is the reference it learned from.

## Reproducing

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Unix
pip install -r requirements.txt
earthengine authenticate
```

Set `GEE_PROJECT` in the config cell of each notebook, and upload your AOI
polygon as an Earth Engine asset.

The Sentinel-2 notebooks are interactive by design: run the first cells, read
the ranked table of candidate acquisition dates, choose the dates, then run on.
Cloud screening scores each date on cloud cover, pixel validity and swath
coverage *over the study area* rather than trusting scene-level metadata, which
describes a whole tile and misleads for a smaller AOI.

After the modelling cells, the prediction rasters are exported to Google Drive;
download them into the run directory before continuing.

**If Earth Engine returns `Too many concurrent aggregations`,** lower
`SCORE_BATCH` or raise `QA_SCALE` — scene scoring is aggregation-heavy and the
quota is rate-based.

## Data sources

| Dataset | Use |
|---|---|
| Copernicus CLMS Imperviousness Density 2018, 10 m | reference (Milan) |
| GHS-BUILT-S R2023A | second reference (Milan), reference (Vietnam) |
| Google Satellite Embedding V1 (Annual) | predictor |
| Copernicus Sentinel-2 L2A (`S2_SR_HARMONIZED`) | predictor |
| ESA WorldCover v200 | water masking |

Photo-interpreted validation plots were produced independently for all three
cities and are not derived from any of the above.

## License

No license is specified. Please get in touch before reusing this work.
