# Mapping Imperviousness Density Using Geospatial Foundation-Model AlphaEarth Embeddings

**Can AlphaEarth replace locally composed Sentinel-2 for 10 m imperviousness
mapping, and does it transfer across cities?**

Maria Antonia Brovelli, Matej Žgela, Keerthana Kirubakaran, Xiao Tan
· Politecnico di Milano

Impervious surface density (IMD) is the proportion of a pixel covered by
impervious material — buildings, roads, pavement. Mapping it at 10 m for Milan,
Hanoi and Ho Chi Minh City in 2018.

Hanoi and HCMC have no IMD product at all. The maps are needed to support local
climate zone mapping and urban heat island analysis in the **LCZ-UHI-GEO**
Italy–Vietnam bilateral project.

## Contributions

1. **Compare Sentinel-2 and AlphaEarth** for local 10 m imperviousness mapping.
2. **Evaluate both local retraining and zero-shot transfer** across Milan,
   Hanoi and Ho Chi Minh City.
3. **Assess how the choice of training target** affects mapping accuracy.

### Predictors

AlphaEarth is ready to use: one global annual product, no compositing to get
right. Sentinel-2 costs more work — searching scenes, screening cloud, building
a composite per city. Four predictor sets are compared on Milan under identical
conditions, so the only thing that varies is the input:

| Predictor | What it is |
|---|---|
| AlphaEarth embeddings | 64 learned bands from [Google Satellite Embedding V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL), encoding a year of Sentinel-1/2, Landsat and more per 10 m pixel |
| Sentinel-2 median | 10 reflectance bands, per-pixel median of cloud-free 2018 dates |
| Sentinel-2 stack | the same dates kept as separate bands |
| Sentinel-2 percentile | five percentiles per band, capturing within-year variation |

### Transfer

Milan models are applied to Hanoi and HCMC two ways: *zero-shot*, with no local
data at all, and *locally retrained*, using a sample of local labels. The gap
between them is what a city gains by collecting its own training data.

### Training target

Milan is modelled twice, against CLMS and against GHS-BUILT-S. The two measure
different things — CLMS sealed surface including roads, GHSL roofed built-up
area excluding them — so the comparison separates what the method achieves from
what the reference it learned from dictates.

Everything is checked twice: against the same reference the models trained on,
and against 450 independently photo-interpreted **EarthLabel** plots per city,
which no model ever saw. The two are never merged — a model can beat its own
training reference and still be wrong about the ground.

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

**Sampling.** 3 500 points per city — 500 in each of seven density classes, so
sparse classes are not swamped by the dominant one. Sampled separately for CLMS
and GHSL, since the two products differ pixel by pixel. Roughly 70/30 train and
test: 2 449 train, 1 014 test.

**Spatial cross-validation.** Ordinary random CV leaks between neighbouring
pixels and reports accuracy that does not survive contact with new ground.
Training points are grouped into blocks of 500 m, 1 km and 2 km, whole blocks
go to five folds, and a 250 m buffer drops validation points sitting too close
to a training point. The locked train/test split is scored exactly once.

**Model.** Random forest — 500 trees, depth 30, seed 42 — tuned in scikit-learn
under those spatial folds, then retrained server-side in Earth Engine and
exported as a 10 m raster.

**Validation.** Three measures against the EarthLabel plots: R², Cohen's κ, and
quadratic weighted κ. Each plot is one 10 m pixel subdivided into nine
photo-interpreted sub-cells.

Run in Google Earth Engine via its Python API, with tuning in scikit-learn.

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

| Dataset | Use | Reference |
|---|---|---|
| CLMS Imperviousness Density 2018, 10 m | training target (Milan) | Copernicus / EEA, [doi:10.2909/3bf542bd](https://doi.org/10.2909/3bf542bd) |
| GHS-BUILT-S R2023A | training target (Milan, Vietnam) | Pesaresi & Politis (2023), EC JRC, [doi:10.2905/9F06F36F](https://doi.org/10.2905/9F06F36F) |
| Google Satellite Embedding V1 (Annual) | predictor, 64 bands | Brown et al. (2025) |
| Sentinel-2 MSI L2A (`S2_SR_HARMONIZED`) | predictor, 10 bands | ESA (2018); Drusch et al. (2012), [doi:10.1016/j.rse.2011.11.026](https://doi.org/10.1016/j.rse.2011.11.026) |
| ESA WorldCover v200 | water masking | |

EarthLabel validation plots were photo-interpreted independently for all three
cities and are not derived from any of the above. The annotation tool is at
[github.com/tanxiaoo/earth-label](https://github.com/tanxiaoo/earth-label).

Predicted rasters and the project code are published at
[github.com/gisgeolab/IMD](https://github.com/gisgeolab/IMD).

## Acknowledgements

We acknowledge Copernicus/EEA (CLMS), EC JRC (GHS-BUILT-S), ESA (Sentinel-2)
and Google (AlphaEarth) for the satellite data and reference products, and
Ammar Mughees for the EarthLabel annotation tool.

This research was conducted as part of the **LCZ-UHI-GEO** Italy–Vietnam
bilateral project and **Space it up!**, funded and supported by the Italian
Space Agency (ASI) and the Vietnam National Space Center (VNSC).
