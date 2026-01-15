## Jeu de données (Dataset)

Nous proposons un nouveau jeu de données de **503 875 images RGB**, annoté selon **13 tâches** (critères).  
Chaque tâche comporte un certain nombre de classes, pour un total de **56 classes**.

Les données sont disponibles sous licence **CC-BY**.  
Toute utilisation du jeu de données doit **citer l’article associé** (à venir) ou **les auteurs**  
(voir la [licence](https://github.com/Hamedkiri/Weather_MultiTask_Datasets?tab=License-1-ov-file) pour plus d’informations).

- 📦 **Images** : *https://cerema.box.com/v/MultitaskWeatherDatasetImages*  
- 📝 **Annotations complètes** : *https://cerema.box.com/v/MultiWDAnnotations* 
- 📝 **Annotations `train`** : *(à compléter)*  
- 📝 **Annotations `test`** : *(à compléter)*  

Pour une description détaillée de la construction des ensembles `train` et `test`, voir :  
➡️ [train-test-construction.md](train-test-construction.md)

---

<a id="fig-1"></a>
<p align="center">
  <img src="images/Datasets/example_of_annotations.png" alt="Exemple d’annotation" title="Fig. 1 – Exemple d’annotations de données" width="70%">
</p>

<p align="center"><em>Fig. 1 – Exemple d’annotation. Chaque image est annotée sur 13 critères.</em></p>

Comme illustré dans la [Fig. 1](#fig-1), chaque image est annotée manuellement par  
**trois annotateurs indépendants** selon **13 critères**, dont **12 liés à la météo** et **1 lié au *point de vue*** (critère informatif non utilisé pour l’entraînement, destiné à diversifier le jeu de données en termes de perspectives).

Les résolutions vont de **640×450** à **1280×720**.  
Les images sont extraites de vidéos publiques sous licence **CC0** ou **Open Licence**.

---

### Critères d’annotation (13 tâches)

- **Type de météo (Weather Type)**  
  `Clear, Sunny+Clear, Rain, Snow, Fog, Fog+Rain, Fog+Snow, None`

- **Intensité de la météo (Weather Intensity)**  
  `Low, Medium, High, None`

- **Visibilité (Visibility)**  
  `Very Low, Low, Medium, Good`

- **État du ciel (Sky Condition)**  
  `Unknown, Clear Sky, Partly Cloudy, Cloudy, Overcast, Partly Overcast`

- **Présence de précipitations (Precipitation Presence)**  
  `None, Rain, Snow, Hail`

- **Intensité des précipitations (Precipitation Intensity)**  
  `None, Low, Medium, High`

- **État de la chaussée (Ground Condition)**  
  `Dry, Wet, Partly Wet, Snowy, Partly Snowy, Wet+Snowy, Unknown`

- **Éblouissement / Reflets (Glare / Reflections)**  
  `Absent, Present`

- **Conditions de lumière (Light Conditions)**  
  `Day, Night, Sunset, Sunrise, Artificial Light`

- **Spray d’eau (Water Spray, projections sur la route)**  
  `Absent, Present`

- **Eau sur le pare-brise (Water on Windshield)**  
  `Absent, Present, None`

- **Neige sur le pare-brise (Snow on Windshield)**  
  `Absent, Present, None`

- **Point de vue (Viewpoint, non utilisé pour l’entraînement)**  
  `Onboard Vehicle, Pedestrian, Fixed Road Camera`

---

<a id="fig-2"></a>
<p align="center">
  <img src="images/Datasets/trainning_datasets.png" alt="Exemples d’images : pluie, neige, brouillard et temps clair" title="Fig. 2 – Exemples d’images de la dataset" width="80%">
</p>

<p align="center"><em>Fig. 2 – Exemples d’images montrant pluie, neige, brouillard et temps clair, de jour comme de nuit.</em></p>

La [Fig. 2](#fig-2) illustre quelques exemples d’images issues du jeu de données  
(situations de pluie, neige, brouillard, temps clair, de jour et de nuit).

---

### Statistiques globales du dataset

<a id="fig-3"></a>
<p align="center">
  <img src="images/Datasets/statiscs_graphs/stats_all_datas.png" alt="Vue d’ensemble des distributions pour tous les critères annotés" title="Fig. 3 – Répartition globale des données pour toutes les tâches" width="80%">
</p>

<p align="center"><em>Fig. 3 – Vue d’ensemble des distributions de classes pour l’ensemble des tâches.</em></p>

La [Fig. 3](#fig-3) donne une vue d’ensemble des **distributions de classes** pour toutes les tâches.  
On observe que, pour certaines tâches (par exemple la présence de spray d’eau sur la route ou d’eau/neige sur le pare-brise), la répartition des données est **fortement déséquilibrée**.  
Il est recommandé de prendre en compte ce déséquilibre lors de l’entraînement (par ex. pondération des classes, focal loss, etc.).

Les figures suivantes détaillent plus spécifiquement le **Type de météo** et l’**État de la chaussée**.

---

<a id="fig-4"></a>
<p align="center">
  <img src="images/Datasets/statiscs_graphs/weather_all_datas_diagramm.png" alt="Distribution par type de météo" title="Fig. 4 – Distribution par type de météo" width="70%">
</p>

<p align="center"><em>Fig. 4 – Répartition des données pour la tâche « Type de météo ».</em></p>

La [Fig. 4](#fig-4) montre la distribution des classes pour la tâche **Type de météo**.  
La répartition est globalement équilibrée, ce qui est favorable pour l’entraînement de classifieurs robustes sur cette tâche.

---

<a id="fig-5"></a>
<p align="center">
  <img src="images/Datasets/statiscs_graphs/ground_condition_repartition.png" alt="Distribution par état de la chaussée" title="Fig. 5 – Distribution par état de la chaussée" width="70%">
</p>

<p align="center"><em>Fig. 5 – Répartition des données pour la tâche « État de la chaussée » (Ground Condition).</em></p>

La [Fig. 5](#fig-5) présente la distribution des classes pour la tâche **Ground Condition**.  
Là encore, la répartition est raisonnablement équilibrée, ce qui permet de bien entraîner des modèles pour cette tâche spécifique.

---

### Outils d’annotation et génération des figures

Le script [`Annotations.py`](https://github.com/Hamedkiri/Weather_MultiTask_Datasets/blob/main/Annotations.py) permet :

- de réaliser **vos propres annotations**,  
- et de **générer automatiquement** les figures de statistiques présentées ci-dessus (distributions globales, par tâche, etc.).

1. **Installer les dépendances**

   Dans un terminal, à la racine du projet :

   ```bash
   pip install -r requirements.txt
   
2. **Regardez la vidéo**

   

https://github.com/user-attachments/assets/3bc88461-353d-4728-bedb-459955faf954

