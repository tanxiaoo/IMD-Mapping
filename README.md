# Mapping Imperviousness Density Using Geospatial Foundation-Model AlphaEarth Embeddings

**Can AlphaEarth replace locally composed Sentinel-2 for 10 m imperviousness
mapping, and does it transfer across cities?**

Maria Antonia Brovelli, Matej Žgela, Keerthana Kirubakaran, Xiao Tan
· Politecnico di Milano

Impervious surface density (IMD) is the proportion of a pixel covered by
impervious material such as buildings, roads, pavement. Mapping it at 10 m for Milan,
Hanoi and Ho Chi Minh City in 2018.

Hanoi and HCMC have no IMD product at all. The maps are needed to support local
climate zone mapping and urban heat island analysis in the **LCZ-UHI-GEO** project.

## Contributions

1. **Compare Sentinel-2 and AlphaEarth** for local 10 m imperviousness mapping.
2. **Evaluate both local retraining and zero-shot transfer** across Milan,
   Hanoi and Ho Chi Minh City.
3. **Assess how the choice of training target** affects mapping accuracy.

### Predictors

AlphaEarth is ready to use: one global annual product, no compositing to get
right. Sentinel-2 costs more work for searching scenes, screening cloud, building
a composite per city. Four predictor sets are compared on Milan under identical
conditions, so the only thing that varies is the input:

| Predictor | What it is |
|---|---|
| AlphaEarth embeddings | 64 learned bands from [Google Satellite Embedding V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL), encoding a year of Sentinel-1/2, Landsat and more per 10 m pixel |
| Sentinel-2 median | 10 reflectance bands, per-pixel median of cloud-free 2018 dates |
| Sentinel-2 percentile | five percentiles per band, capturing within-year variation |
| Sentinel-2 stack | Four near-cloud-free dates , evenly spaced from March to October. kept as separate bands |

### Transfer

Milan models are applied to Hanoi and HCMC two ways: *zero-shot*, with no local
data at all, and *locally retrained*, using a sample of local labels. The gap
between them is what a city gains by collecting its own training data.

### Training target

Milan is modelled twice, against CLMS and against GHS-BUILT-S. The two measure
different things, CLMS sealed surface including roads while GHSL roofed built-up
area excluding them. so the comparison separates what the method achieves from
what the reference it learned from dictates.

Everything is evaluated against 450 independently photo-interpreted **EarthLabel** plots per city, which no model ever saw during training.

## What is here

The full write-up is `report/report.pdf`, with `report/IMD_Mapping.pptx` as
the accompanying deck. The notebooks are the pipeline that produced them.

```
00_S2_Extraction_Milan_2018.ipynb               Sentinel-2 scene search + extraction
00b_S2_Extraction_Vietnam_2018.ipynb            the same for Hanoi and HCMC
ghsl_data_preparation.ipynb                     GHSL clipped, reclassified, resampled

01_IMD_Prediction_Milan_blockCV_embedding.ipynb Milan, embeddings
01b_IMD_Prediction_Milan_blockCV_S2.ipynb       Milan, Sentinel-2
01c_IMD_Prediction_Milan_blockCV_GHSL.ipynb     Milan, embeddings, GHSL-labelled
01d_IMD_Prediction_Milan_blockCV_S2_GHSL.ipynb  Milan, Sentinel-2, GHSL-labelled

02_Transferability_Vietnam_v2.ipynb             Hanoi / HCMC transfer, embeddings
03_Transferability_Vietnam_S2_median.ipynb      the same, Sentinel-2

04_SameSource_Validation.ipynb                  same-source validation, against the training product
05_Independent_Validation.ipynb                 independent validation, 450 EarthLabel plots/city

s2_utils.py                                     shared cloud masks + composite builder
gee_init.py                                     reads the GEE project id from .env
```

Run them in order: extract, model, transfer, validate.

### Where things live

```
data/     inputs only — reference rasters, sample points, the AOI and the
          EarthLabel plots. Nothing a notebook writes ever lands here.

output/   every run, as city / label source / predictor:
            milan/{clms,ghsl}/{embedding,median,stack,percentile}/
            transfer_vietnam/{hanoi,hcmc}/{embedding,median}/
            transfer_vietnam/hanoi_and_hcmc/  two-city comparison files
            validation_samesource/            against the training product
            validation_independent/           against the EarthLabel plots

report/   report.tex, report.pdf, IMD_Mapping.pptx
```

> **Code only.** `data/` and `output/` are around 5 GB of rasters, models and
> sample points — regenerable by re-running the notebooks, and the GeoTIFFs
> exceed GitHub's file size limit.
>
> **Download them instead:** the predicted maps and the input data are archived
> on Zenodo, 1.8 GB, CC BY 4.0 —
> [doi:10.5281/zenodo.22874238](https://doi.org/10.5281/zenodo.22874238).
> Unpack into `data/` and `output/` and the notebooks run without re-exporting
> anything from Earth Engine.

## Method in brief

**Sampling.** 500 points in each of seven density classes, so sparse classes
are not swamped by the dominant one. Milan against CLMS hits the full 3 500;
the GHSL sets come in slightly under once water-masked points are dropped
(3 448 Milan, 3 282 Hanoi, 3 249 HCMC). Sampled separately for CLMS and GHSL,
since the two products differ pixel by pixel. Roughly 70/30 train and test:
2 449 train, 1 014 test on the Milan CLMS split.

**Spatial cross-validation.** Ordinary random CV leaks between neighbouring
pixels and reports accuracy that does not survive contact with new ground.
Training points are grouped into blocks of 500 m, 1 km or 2 km — the size is
tuned per run — whole blocks go to five folds, and a 250 m buffer drops
validation points sitting too close to a training point. The locked train/test
split is scored exactly once.

**Model.** Random forest, seed 42, tuned in scikit-learn under those spatial
folds over a grid of tree count and depth, then retrained server-side in Earth
Engine and exported as a 10 m raster. The selected settings differ per run and
are recorded in each run's `model_metadata_*.json`.

**Validation.** Maps are ranked against the EarthLabel plots on three measures:
R² on the raw predicted percentage, Cohen's κ at a 50 % cut-off, and quadratic
weighted κ over ten fraction levels; RMSE, MAE, overall accuracy and F1 are
reported alongside. Each plot is one 10 m pixel subdivided into nine
photo-interpreted sub-cells.

Run in Google Earth Engine via its Python API, with tuning in scikit-learn.

## Reproducing

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on Unix
pip install -r requirements.txt
earthengine authenticate
copy .env.example .env          # Windows;  cp .env.example .env on Unix
```

Put your own Earth Engine project id in `.env`:

```
GEE_PROJECT=your-cloud-project-id
```

`.env` is gitignored, so it survives a pull and no notebook needs editing —
they all read it through `gee_init.init_gee()`. Upload your AOI polygon as an
Earth Engine asset too.

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

## Archive

The predicted maps for all three cities, together with the inputs under
`data/`, are deposited on Zenodo under CC BY 4.0:

> Brovelli, M. A., Žgela, M., Kirubakaran, K. and Tan, X. (2026). *Mapping
> Imperviousness Density Using Geospatial Foundation-Model AlphaEarth
> Embeddings* (v1) [Data set]. Zenodo.
> [doi:10.5281/zenodo.22874238](https://doi.org/10.5281/zenodo.22874238)

1.8 GB in total: the Milan embedding and Sentinel-2 models, the IMD maps for
Milan, Hanoi and HCMC, and the zero-shot and locally retrained Vietnam
outputs.

The project code is published at
[github.com/gisgeolab/IMD](https://github.com/gisgeolab/IMD); the predicted
rasters are in the Zenodo deposit above, not in either repository.

## Acknowledgements

We acknowledge Copernicus/EEA (CLMS), EC JRC (GHS-BUILT-S), ESA (Sentinel-2)
and Google (AlphaEarth) for the satellite data and reference products, and
Mohammad Ammar Mughees for the EarthLabel annotation tool.

This research was conducted as part of the **LCZ-UHI-GEO** Italy–Vietnam
bilateral project and **Space it up!**, funded and supported by the Italian
Space Agency (ASI) and the Vietnam National Space Center (VNSC).
