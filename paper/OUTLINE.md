# Paper outline — from Prof. Brovelli

Separate from the internal report (`report/`). This is the outline for a
standalone academic paper, not a restructuring of `report/IMD_Mapping_report.tex`.
Saved as received; no drafting started yet.

**Working title:** Urban Imperviousness Mapping with AlphaEarth Embeddings and
Sentinel-2: Local Performance, Cross-City Transfer and Training-Label Effects

## 1. Introduction
- Imperviousness density and applications
- Existing EO-based IMD mapping (state of the art)
- Geospatial foundation models and embeddings
- Research questions and contributions

## 2. Study Areas and Data
- Milan, Hanoi, Ho Chi Minh City
- CLMS Imperviousness Density
- GHS-BUILT-S
- Sentinel-2
- AlphaEarth embeddings
- EarthLabel independent reference dataset

## 3. Methodology
- Training-sample generation
- Spatial train/test split
- Spatial-block cross-validation and block-size sensitivity
- Sentinel-2 compositing strategies
- Random Forest modelling
  - Local retraining
  - Zero-shot cross-city transfer
- Independent EarthLabel validation
  - Continuous, binary and ordinal metrics

## 4. Results
- 4.1 Spatial CV and model robustness
- 4.2 Milan: AlphaEarth vs Sentinel-2
- 4.3 Effect of the training target: CLMS vs GHS-BUILT-S
- 4.4 Hanoi: local retraining vs zero-shot transfer
- 4.5 Ho Chi Minh City: local retraining vs zero-shot transfer
- 4.6 Cross-city comparison

## 5. Discussion
- 5.1 Do AlphaEarth embeddings replace Sentinel-2?
- 5.2 Why local retraining matters
- 5.3 Training-label quality versus predictor quality
- 5.4 Why zero-shot transfer succeeds or fails
- 5.5 The HCMC anomaly / apparent Sentinel-2 zero-shot advantage
- 5.6 Implications for operational IMD mapping where local reference data are scarce
- 5.7 Limitations

## 6. Conclusions
