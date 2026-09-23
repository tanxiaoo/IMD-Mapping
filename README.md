# Mapping Imperviousness Density Using Geospatial Foundation-Model AlphaEarth Embeddings

**Can AlphaEarth replace locally composed Sentinel-2 for 10 m imperviousness
mapping, and does it transfer across cities?**

Maria Antonia Brovelli, Matej Žgela, Keerthana Kirubakaran, Xiao Tan
· Politecnico di Milano

Impervious surface density (IMD) is the proportion of a pixel covered by
impervious material such as buildings, roads, pavement. Mapping it at 10 m for Milan,
Hanoi and Ho Chi Minh City in 2018.

Hanoi and HCMC have no IMD product at all. The maps are needed to support local
climate zone mapping and urban heat island analysis in the **LCZ-UHI-GEO** and **Space it up!** project.

## Contributions

1. **Compare Sentinel-2 and AlphaEarth** for local 10 m imperviousness mapping.
2. **Evaluate both local retraining and zero-shot transfer** across Milan,
   Hanoi and Ho Chi Minh City.
3. **Assess how the choice of training target** affects mapping accuracy.

### Predictors

AlphaEarth is one annual product: a single image per year, ready to use.
Sentinel-2 is not. It passes over each city many times a year, so 2018 gives
dozens of images, each with its own clouds and gaps. To get one annual layer
out of them, we screen for cloud and valid pixels and then combine the
remaining dates into a composite, and we do that three ways. Those three,
plus AlphaEarth, are the four predictor sets below. They are compared on Milan
with everything else kept the same, so the input is the only thing that
changes:

| Predictor | What it is |
|---|---|
| AlphaEarth embeddings | 64 learned bands from [Google Satellite Embedding V1](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_SATELLITE_EMBEDDING_V1_ANNUAL), encoding a year of Sentinel-1/2, Landsat and more per 10 m pixel |
| Sentinel-2 median | 10 reflectance bands, per-pixel median of cloud-free 2018 dates |
| Sentinel-2 percentile | five percentiles per band, capturing within-year variation |
| Sentinel-2 stack | four near-cloud-free dates evenly spaced from March to October, kept as separate bands rather than combined |

### Transfer

Milan models are applied to Hanoi and HCMC two ways: *zero-shot*, with no local
data at all, and *locally retrained*, using a sample of local labels. The gap
between them is what a city gains by collecting its own training data.

### Training target

Milan is modelled twice, against CLMS and against GHS-BUILT-S (GHSL). The two measure
different things: CLMS maps sealed surface including roads, GHSL maps roofed
built-up area without them. Comparing the two separates what the method
achieves from what the training reference already decides.

Everything is evaluated against 450 independently photo-interpreted **EarthLabel** plots per city, which no model ever saw during training.

## What is here

`deliverables/report.pdf` is the full write-up of the project and
`deliverables/IMD_Mapping.pptx` is the accompanying deck. The notebooks below
are the pipeline that produced the maps and the numbers those two report on.

```
00_S2_Extraction_Milan_2018.ipynb               Sentinel-2 scene search + extraction
00b_S2_Extraction_Vietnam_2018.ipynb            the same for Hanoi and HCMC
ghsl_data_preparation.ipynb                     GHSL clipped, reclassified, resampled

01_IMD_Prediction_Milan_blockCV_embedding_CLMS.ipynb   Milan, embeddings, CLMS
01b_IMD_Prediction_Milan_blockCV_S2_CLMS.ipynb         Milan, Sentinel-2, CLMS
01c_IMD_Prediction_Milan_blockCV_embedding_GHSL.ipynb  Milan, embeddings, GHSL
01d_IMD_Prediction_Milan_blockCV_S2_GHSL.ipynb         Milan, Sentinel-2, GHSL

02_Transferability_Vietnam_embedding.ipynb      Hanoi / HCMC transfer, embeddings
03_Transferability_Vietnam_S2_median.ipynb      the same, Sentinel-2

04_SameSource_Validation.ipynb                  same-source validation, against the training product
05_Independent_Validation.ipynb                 independent validation, 450 EarthLabel plots/city

s2_utils.py                                     shared cloud masks + composite builder
gee_init.py                                     reads the GEE project id from .env
```

Run them in order: extract, model, transfer, validate.

### Where things live

Two directories, each with one job. Neither is in the repository: create them
yourself, then fill `data/` from the [Zenodo
archive](https://doi.org/10.5281/zenodo.22874238) (1.8 GB, CC BY 4.0) before
running anything.

**`data/` — inputs only,** never written to by a notebook. Make the folder at
the repository root and put the files in this layout:

```
data/
  CLMS_2018_Milan_LAEA.tif            CLMS imperviousness, Milan
  CLMS_2018_Milan_UTM32N.tif          the same, reprojected
  GHSL_2018_Milan_UTM32N.tif          GHS-BUILT-S, one per city
  GHSL_2018_Hanoi_UTM48N.tif
  GHSL_2018_HCMC_UTM48N.tif
  sample_points/                      the 3500 training points per run
    sample_points_all_CLMS_Milan.gpkg
    sample_points_all_GHSL_Milan.gpkg
    sample_points_all_GHSL_Hanoi.gpkg
    sample_points_all_GHSL_HCMC.gpkg
  earthlabel/                         450 photo-interpreted plots per city
    milan_imd_2018_results_cells.csv
    hanoi_imd_2018_results_cells.csv
    hcmc_imd_2018_results_cells.csv
  aoi_milan/                          Milan study area polygon
    milano_aoi.gpkg  (and .shp/.dbf/.shx/.prj)
```

Everything here is in the Zenodo archive. The two reference products can also
be downloaded from their own sources, listed under **Data sources** below, and
the EarthLabel plots can be re-made with the annotation tool linked there.

**`output/` — one directory per run,** named `city / label source / predictor`.
The notebooks create it as they go, so you do not have to; the finished rasters
are also in the Zenodo archive if you would rather not rerun them.

```
output/
  milan/                              the eight Milan runs
    clms/                             trained against CLMS
      embedding/                      each run directory holds the
      median/                           predicted raster, the fitted
      percentile/                       model, its metadata JSON and
      stack/                            the run's figures and CSVs
    ghsl/                             the same four, against GHSL
      embedding/  median/  percentile/  stack/

  transfer_vietnam/
    hanoi/                            one city: rasters and samples
      embedding/                        IMD_Hanoi_10m_zeroshot.tif
      median/                           IMD_Hanoi_10m_localrf.tif
    hcmc/
      embedding/  median/
    hanoi_and_hcmc/                   both cities: the comparison
      embedding/                        transferability_comparison.csv
      median/                           per_class_metrics.csv, figures

  validation_samesource/              notebook 04, against the
                                        training product
  validation_independent/             notebook 05, against EarthLabel
    Milan_2018/                         per_raster/<map>/ and
    Hanoi_2018/                         comparison/ per city
    HCMC_2018/
    cross_city/                       the three cities together
```

A file describing one city goes under that city; a file comparing two goes
under `hanoi_and_hcmc/`. Keeping them apart matters: a two-city file filed
under one city hides the other city's results inside it.

**`deliverables/` — what gets handed over:** `report.pdf` and
`IMD_Mapping.pptx`, the finished versions.

## Method in brief

**Sampling.** 500 points in each of the seven density classes, giving a
balanced 3500, so sparse classes are not swamped by the dominant one. Drawn
separately for CLMS and GHSL, since the two products differ pixel by pixel.

**Train/test split.** The 3500 points are split using 1 km spatial blocks,
whole blocks to one side or the other. A 250m buffer around the test blocks
then removes training points lying too close to a test point, 37 of them for
CLMS, leaving **2449 train and 1014 test**. Splitting on blocks rather than
on points keeps a pixel's neighbours out of the other half, which ordinary
random splitting does not.

**Cross-validation.** The 2449 training points are regrouped into spatial
blocks and the blocks assigned at random to five folds. Tuning repeats at
three block sizes (500m, 1000m and 2000m) and the setting with the lowest
mean RMSE is selected. For AlphaEarth on Milan that was 1000m.

**Model.** Random forest, tuned in scikit-learn under spatial folds,
then retrained server-side in Earth Engine and exported as a 10m raster. The
selected trees and depth differ per run and are recorded in each run's
`model_metadata_*.json`.

**Validation.** Maps are ranked against the EarthLabel plots on three measures:
R² on the raw predicted percentage, Cohen's κ at a 50 % cut-off, and quadratic
weighted κ over ten fraction levels; RMSE, MAE, overall accuracy and F1 are
reported alongside. Each plot is one 10m pixel subdivided into nine
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
bilateral and **Space it up!** projects, funded and supported by the Italian
Space Agency (ASI) and the Vietnam National Space Center (VNSC).
