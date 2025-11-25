
## Construction des sous-ensembles d’entraînement et de test

Notre jeu de données (503 875 images) est issu de **227 vidéos libres de droits**.  
Les images consécutives d’une même vidéo peuvent être très similaires ; nous imposons donc plusieurs contraintes afin de :

1. **Réduire la redondance intra-vidéo**  
2. **Équilibrer précisément la contribution de chaque source**  
3. **Reproduire une distribution similaire entre `train` et `test` tout en évitant tout chevauchement**

### Principe général

- **Stratification par source**  
  Les ensembles `train` et `test` tirent des images dans **l’ensemble des 227 vidéos**, mais restent **disjoints au niveau des images** (aucune image partagée).

- **Quotas combinés de type Hamilton**  
  Pour chaque split (`train`, `test`), les quotas par source sont calculés via la méthode des **plus forts restes** (Hare–Niemeyer), puis co-répartis entre `train` et `test` de sorte que leurs distributions par source soient proches de celle du jeu complet **et proches l’une de l’autre**.  
  Cela évite qu’une source domine et garantit des splits **iso-distribués** par source.

- **Sélection aléatoire contrôlée**  
  À l’intérieur de chaque vidéo, la sélection est aléatoire mais soumise à une **distance minimale en indices de frame** afin de limiter les paires quasi dupliquées.

### Procédure

Notations :

- `V = {v1, ..., v227}` : ensemble des sources (vidéos)  
- `n(v)` : nombre d’images utilisables dans la source `v`  
- `N = Σ_v n(v)` : nombre total d’images  
- `N_train` et `N_test` : tailles cibles pour les ensembles d’entraînement et de test

Étapes :

1. **Part de chaque source**  
   `s(v) = n(v) / N`

2. **Quotas idéaux**  
   - `q_train*(v) = s(v) · N_train`  
   - `q_test*(v)  = s(v) · N_test`

3. **Hamilton (plus forts restes) pour chaque split**  
   Pour `train` et `test` séparément :
   - on commence par allouer `floor(q*)` images par source ;
   - puis on distribue les images restantes selon les plus grandes parties fractionnaires jusqu’à atteindre exactement `N_train` et `N_test`.

4. **Co-apportionnement combiné**  
   Les listes de restes pour `train` et `test` sont **entrelacées** afin de minimiser l’écart par source entre les deux splits (tie-break partagé), tout en respectant les tailles cibles.

   On obtient ainsi des quotas `{q_train(v)}` et `{q_test(v)}` tels que :

   - `Σ_v q_train(v) = N_train`  
   - `Σ_v q_test(v)  = N_test`  
   - et pour chaque source `v` :  
     `q_train(v) / N_train ≈ q_test(v) / N_test ≈ s(v)`

5. **Échantillonnage disjoint et espacé**  
   Pour chaque source `v`, on tire `q_train(v)` et `q_test(v)` images :
   - **sans chevauchement d’ID** entre `train` et `test` ;  
   - avec la contrainte `|f_i - f_j| ≥ Δf_min` (écart minimal d’indices de frame) *au sein d’un même split* ;  
   - en utilisant une `seed` aléatoire fixe pour la **reproductibilité**.

### Tailles et métriques

Nous utilisons :

- **Ensemble d’entraînement** : `250 000` images  
- **Ensemble de test** : `25 000` images  

Pour caractériser la redondance intra-vidéo, nous mesurons l’**écart moyen d’indices de frame** :

`Δf̄ = (1 / |P|) · Σ_(i,j ∈ P) |f_i - f_j|`

sur les paires adjacentes retenues dans une même source.

- **Jeu complet (503 875)**  
  - `Δf̄ = 38,63`  
  - Voir :  
    ![Proximité des frames (jeu complet) : redondance intra-vidéo et hétérogénéité inter-vidéo](images/Datasets/statiscs_graphs/repartition_all_datas.png)

- **Train (250k)**  
  - `Δf̄ = 62,75`  
  - Quotas harmonisés via Hamilton :  
    ![Train (250k) : écart moyen d’indices et quotas par source via Hamilton combiné](images/Datasets/train_test_statistiques/train_heterogeneity.png)

- **Test (25k)**  
  - `Δf̄ = 427,65` (échantillonnage très espacé)  
  - Voir :  
    ![Test (25k) : écart moyen très élevé et distribution par source alignée](images/Datasets/train_test_statistiques/test_heterogeneity.png)

### Effets attendus

La combinaison **apportionnement de Hamilton + contrainte d’espacement** permet :

1. De **faire correspondre les distributions `train`/`test`** au niveau des sources ;  
2. De **tirer parti de toute la diversité des sources** (toutes les vidéos contribuent aux deux splits) ;  
3. De **réduire les corrélations temporelles** (frames trop proches dans une même séquence).

Le modèle évite ainsi de sur-apprendre sur des images quasi identiques issues d’une même vidéo, tout en conservant une grande diversité de situations : jour/nuit, pluie/brouillard/neige, routes/urbain, etc.

### Reproductibilité

Nous mettons à disposition :

- l’ensemble des annotations,  
- les listes complètes des IDs d’images sélectionnées,  
- la `seed` aléatoire utilisée,  
- ainsi que le **journal d’apportionnement** (restes/assignations de Hamilton).

Tout est disponible dans le dépôt :  
<https://github.com/Hamedkiri/Weather_MultiTask_Datasets>

Cela garantit des **splits entièrement reproductibles** et **aucun chevauchement train/test**.
