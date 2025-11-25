## Dataset

We introduce a new dataset of **503,875 RGB images**, annotated according to **13 tasks** (criteria).  
Each task has its own set of classes, for a total of **56 classes**.

The data are released under a **CC-BY license**.  
Any use of this dataset should **cite the associated paper** (coming soon) or **the authors**  
(see the [license](https://github.com/Hamedkiri/Weather_MultiTask_Datasets?tab=License-1-ov-file) for more details).

- 📦 **Images**: *(to be completed)*  
- 📝 **Full annotations**: *(to be completed)*  
- 📝 **Train annotations**: *(to be completed)*  
- 📝 **Test annotations**: *(to be completed)*  

For a detailed description of how the `train` and `test` sets are constructed, see:  
➡️ [train-test-construction.md](train-test-construction.md)

---

<a id="fig-1"></a>
<p align="center">
  <img src="images/Datasets/example_of_annotations.png" alt="Annotation example" title="Fig. 1 – Example of data annotations" width="70%">
</p>

<p align="center"><em>Fig. 1 – Example of annotation. Each image is annotated on 13 criteria.</em></p>

As illustrated in [Fig. 1](#fig-1), each image is manually annotated by  
**three independent annotators** according to **13 criteria**, of which **12 are related to weather** and **1 to the *viewpoint*** (an informative criterion not used for training, intended to diversify the dataset in terms of camera perspectives).

Image resolutions range from **640×450** to **1280×720**.  
Images are extracted from public videos released under **CC0** or **Open Licence**.

---

### Annotation criteria (13 tasks)

- **Weather Type**  
  `Clear, Sunny+Clear, Rain, Snow, Fog, Fog+Rain, Fog+Snow, None`

- **Weather Intensity**  
  `Low, Medium, High, None`

- **Visibility**  
  `Very Low, Low, Medium, Good`

- **Sky Condition**  
  `Unknown, Clear Sky, Partly Cloudy, Cloudy, Overcast, Partly Overcast`

- **Precipitation Presence**  
  `None, Rain, Snow, Hail`

- **Precipitation Intensity**  
  `None, Low, Medium, High`

- **Ground Condition**  
  `Dry, Wet, Partly Wet, Snowy, Partly Snowy, Wet+Snowy, Unknown`

- **Glare / Reflections**  
  `Absent, Present`

- **Light Conditions**  
  `Day, Night, Sunset, Sunrise, Artificial Light`

- **Water Spray (road spray)**  
  `Absent, Present`

- **Water on Windshield**  
  `Absent, Present, None`

- **Snow on Windshield**  
  `Absent, Present, None`

- **Viewpoint** (not used for training)  
  `Onboard Vehicle, Pedestrian, Fixed Road Camera`

---

<a id="fig-2"></a>
<p align="center">
  <img src="images/Datasets/trainning_datasets.png" alt="Example images: rain, snow, fog, clear weather" title="Fig. 2 – Example images from the dataset" width="80%">
</p>

<p align="center"><em>Fig. 2 – Example images showing rain, snow, fog, and clear weather, by day and by night.</em></p>

[Fig. 2](#fig-2) shows a few examples of images from the dataset,  
including rainy, snowy, foggy, and clear scenes, both during day and night.

---

### Global dataset statistics

<a id="fig-3"></a>
<p align="center">
  <img src="images/Datasets/statiscs_graphs/stats_all_datas.png" alt="Overview of distributions for all annotated criteria" title="Fig. 3 – Global data distribution for all tasks" width="80%">
</p>

<p align="center"><em>Fig. 3 – Overview of class distributions across all tasks.</em></p>

[Fig. 3](#fig-3) provides an overview of **class distributions** for all tasks.  
For some tasks (e.g., presence of road spray or water/snow on the windshield), the data distribution is **highly imbalanced**.  
We recommend taking this imbalance into account during training (e.g., class weighting, focal loss, etc.).

The following figures focus more specifically on **Weather Type** and **Ground Condition**.

---

<a id="fig-4"></a>
<p align="center">
  <img src="images/Datasets/statiscs_graphs/weather_all_datas_diagramm.png" alt="Distribution by weather type" title="Fig. 4 – Distribution by Weather Type" width="70%">
</p>

<p align="center"><em>Fig. 4 – Data distribution for the “Weather Type” task.</em></p>

[Fig. 4](#fig-4) shows the class distribution for the **Weather Type** task.  
The distribution is globally well balanced, which is favourable for training robust classifiers on this task.

---

<a id="fig-5"></a>
<p align="center">
  <img src="images/Datasets/statiscs_graphs/ground_condition_repartition.png" alt="Distribution by ground condition" title="Fig. 5 – Distribution by Ground Condition" width="70%">
</p>

<p align="center"><em>Fig. 5 – Data distribution for the “Ground Condition” task.</em></p>

[Fig. 5](#fig-5) shows the class distribution for the **Ground Condition** task.  
Here as well, the distribution is reasonably balanced, which enables effective training of models for this specific task.

---

### Annotation tools and figure generation

The [`Annotations.py`](https://github.com/Hamedkiri/Weather_MultiTask_Datasets/blob/main/Annotations.py) script allows you to:

- perform **your own annotations**,  
- and **automatically generate** the statistical figures shown above (global distributions, per-task distributions, etc.).

Examples of usage and how to generate these statistics will be added soon in the repository documentation.
