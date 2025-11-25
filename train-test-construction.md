## Construction of Training and Test Subsets

Our dataset (503,875 images) is derived from **227 royalty-free videos**.  
Consecutive frames from the same video can be very similar, so we enforce several constraints in order to:

1. **Reduce intra-video redundancy**  
2. **Precisely balance the contribution of each source**  
3. **Reproduce a similar distribution between `train` and `test` while avoiding any overlap**

### General Principle

- **Source stratification**  
  The `train` and `test` sets draw images from **all 227 videos**, but remain **disjoint at the image level** (no image is shared between them).

- **Combined Hamilton quotas**  
  For each split (`train`, `test`), per-source quotas are computed using the **largest remainders method** (Hare–Niemeyer), then co-apportioned between `train` and `test` so that their per-source distributions are close to that of the full dataset **and close to each other**.  
  This prevents any single source from dominating and guarantees **source-wise iso-distributed** splits.

- **Controlled random selection**  
  Within each video, sampling is random but subject to a **minimum frame-index distance** in order to limit near-duplicate pairs.

### Procedure

Notation:

- `V = {v1, ..., v227}`: set of all sources (videos)  
- `n(v)`: number of usable images in source `v`  
- `N = Σ_v n(v)`: total number of images  
- `N_train` and `N_test`: target sizes for the training and test sets

Steps:

1. **Share of each source**  
   `s(v) = n(v) / N`

2. **Ideal quotas**  
   - `q_train*(v) = s(v) · N_train`  
   - `q_test*(v)  = s(v) · N_test`

3. **Hamilton (largest remainders) for each split**  
   For `train` and `test` separately:
   - first assign `floor(q*)` images per source;  
   - then distribute the remaining images according to the largest fractional parts until reaching exactly `N_train` and `N_test`.

4. **Combined co-apportionment**  
   The remainder lists for `train` and `test` are **interleaved** so as to minimize per-source divergence between the two splits (shared tie-break), while still meeting the target sizes.

   This yields quotas `{q_train(v)}` and `{q_test(v)}` such that:

   - `Σ_v q_train(v) = N_train`  
   - `Σ_v q_test(v)  = N_test`  
   - and for each source `v`:  
     `q_train(v) / N_train ≈ q_test(v) / N_test ≈ s(v)`

5. **Disjoint and spaced sampling**  
   For each source `v`, we sample `q_train(v)` and `q_test(v)` images:
   - **with no ID overlap** between `train` and `test`;  
   - under the constraint `|f_i - f_j| ≥ Δf_min` (minimum frame-index gap) *within the same split*;  
   - using a fixed random `seed` for **reproducibility**.

### Sizes and Metrics

We use:

- **Training set**: `250,000` images  
- **Test set**: `25,000` images  

To quantify intra-video redundancy, we measure the **mean frame-index gap**:

`Δf̄ = (1 / |P|) · Σ_(i,j ∈ P) |f_i - f_j|`

over adjacent pairs retained within the same source.

- **Full dataset (503,875)**  
  - `Δf̄ = 38.63`  
  - See:  
    ![Frame proximity (full dataset): intra-video redundancy and inter-video heterogeneity](images/Datasets/statiscs_graphs/repartition_all_datas.png)

- **Train (250k)**  
  - `Δf̄ = 62.75`  
  - Quotas harmonized via Hamilton:  
    ![Train (250k): mean frame-index gap and per-source quotas via combined Hamilton](images/Datasets/train_test_statistiques/train_heterogeneity.png)

- **Test (25k)**  
  - `Δf̄ = 427.65` (very sparse sampling)  
  - See:  
    ![Test (25k): very high mean frame-index gap and aligned per-source distribution](images/Datasets/train_test_statistiques/test_heterogeneity.png)

### Expected Effects

The combination of **Hamilton apportionment + spacing constraint**:

1. **Aligns the `train`/`test` distributions** at the source level;  
2. **Leverages the full diversity of sources** (all videos contribute to both splits);  
3. **Reduces temporal correlations** (frames that are too close within the same sequence).

This prevents the model from overfitting on quasi-identical images from the same video, while preserving a wide variety of situations: day/night, rain/fog/snow, highway/urban, etc.

### Reproducibility

We release:

- the full set of annotations,  
- the complete lists of selected image IDs,  
- the random `seed` used,  
- as well as the **apportionment log** (Hamilton remainders/assignments).

All of this is available in the repository:  
<https://github.com/Hamedkiri/Weather_MultiTask_Datasets>

This ensures **fully reproducible splits** and **no train/test overlap**.
