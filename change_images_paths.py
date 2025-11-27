import os, json
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, Optional, Iterable, Tuple, List

def _build_file_indexes(root: str | Path,
                        allowed_exts: Iterable[str] = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
                        ) -> tuple[Dict[Tuple[str, str], str], Dict[str, List[str]]]:
    """
    Indexe le dossier racine:
      - idx_sub_name[(subfolder, filename)] -> chemin complet
      - idx_by_name[filename] -> [chemins complets...]
    subfolder = dernier dossier parent immédiat du fichier indexé.
    """
    root = Path(root)
    allowed_exts = {e.lower() for e in allowed_exts}
    idx_sub_name: Dict[Tuple[str, str], str] = {}
    idx_by_name: Dict[str, List[str]] = defaultdict(list)

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in allowed_exts:
            continue
        filename = p.name
        subfolder = p.parent.name  # parent immédiat
        idx_sub_name[(subfolder, filename)] = str(p)
        idx_by_name[filename].append(str(p))

    return idx_sub_name, idx_by_name


def _resolve_new_path(record: Dict[str, Any],
                      outer_key: Optional[str],
                      *,
                      search_folder: Optional[str],
                      find_images_by_sub_folder: Optional[str],
                      idx_sub_name: Optional[Dict[Tuple[str, str], str]],
                      idx_by_name: Optional[Dict[str, List[str]]]
                      ) -> Optional[str]:
    """
    Renvoie le nouveau chemin si trouvé, sinon None.
    Stratégie:
      1) search_folder: <search_folder>/<filename>
      2) find_images_by_sub_folder:
            - (record['folder'], filename) si dispo
            - (parent(orig_path), filename)
            - si unique par filename, on prend
    """
    # filename fiable
    filename = None
    if isinstance(record.get("image_name"), str) and record["image_name"]:
        filename = Path(record["image_name"]).name
    elif isinstance(record.get("image_path"), str) and record["image_path"]:
        filename = Path(record["image_path"]).name
    else:
        return None  # pas d'info fiable

    # 1) search_folder
    if search_folder:
        cand = Path(search_folder) / filename
        return str(cand) if cand.exists() else None

    # 2) find_images_by_sub_folder via index
    if find_images_by_sub_folder and idx_sub_name is not None and idx_by_name is not None:
        # Tentatives par sous-dossier le plus probable
        preferred_subs: List[str] = []

        # a) champ 'folder' s’il existe
        if isinstance(record.get("folder"), str) and record["folder"]:
            preferred_subs.append(record["folder"])

        # b) parent de l'ancien image_path
        if isinstance(record.get("image_path"), str) and record["image_path"]:
            try:
                old_parent = Path(record["image_path"]).parent.name
                if old_parent:
                    preferred_subs.append(old_parent)
            except Exception:
                pass

        # c) outer_key (dernier recours, peu fiable, mais on tente)
        if isinstance(outer_key, str) and outer_key:
            # pas de normalisation agressive: on prend le nom brut
            preferred_subs.append(outer_key)

        # Essais (subfolder, filename)
        for sub in preferred_subs:
            key = (sub, filename)
            if key in idx_sub_name:
                path = idx_sub_name[key]
                if Path(path).exists():
                    return path

        # Sinon, si un seul fichier porte ce nom dans tout l'index
        paths = idx_by_name.get(filename, [])
        if len(paths) == 1 and Path(paths[0]).exists():
            return paths[0]

    return None


def _process_record_in_place(record: Dict[str, Any],
                             outer_key: Optional[str],
                             *,
                             search_folder: Optional[str],
                             find_images_by_sub_folder: Optional[str],
                             idx_sub_name: Optional[Dict[Tuple[str, str], str]],
                             idx_by_name: Optional[Dict[str, List[str]]]
                             ) -> tuple[bool, bool]:
    """
    Met à jour record['image_path'] si un nouveau chemin valide est trouvé.
    Retourne (updated, had_image_field)
    """
    has_img_field = "image_path" in record or "image_name" in record
    new_path = _resolve_new_path(
        record, outer_key,
        search_folder=search_folder,
        find_images_by_sub_folder=find_images_by_sub_folder,
        idx_sub_name=idx_sub_name,
        idx_by_name=idx_by_name
    )
    if new_path is not None:
        record["image_path"] = new_path  # update
        return True, has_img_field
    return False, has_img_field


def rewrite_annotation_paths(annot_in: str | Path,
                             annot_out: str | Path,
                             *,
                             search_folder: Optional[str] = None,
                             find_images_by_sub_folder: Optional[str] = None,
                             strict: bool = False,
                             allowed_exts: Iterable[str] = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
                             ) -> dict:
    """
    Lit annot_in (JSON), crée annot_out (JSON) avec 'image_path' corrigés
    via `search_folder` OU `find_images_by_sub_folder`.
    - Si les deux sont fournis -> ValueError.
    - On n'écrit un nouveau chemin que si le fichier existe vraiment.
    - Si aucun chemin trouvé, l'entrée est laissée telle quelle.
    - strict=True -> lève une erreur si au moins un fichier n’a pas pu être résolu.

    Retourne un petit rapport: dict(counters=..., out=annot_out)
    """
    if search_folder and find_images_by_sub_folder:
        raise ValueError("Fournis soit 'search_folder', soit 'find_images_by_sub_folder', pas les deux.")

    annot_in = Path(annot_in)
    annot_out = Path(annot_out)

    with annot_in.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Index si on utilise find_images_by_sub_folder
    idx_sub_name = idx_by_name = None
    if find_images_by_sub_folder:
        idx_sub_name, idx_by_name = _build_file_indexes(find_images_by_sub_folder, allowed_exts)

    counters = {
        "groups": 0,
        "records_scanned": 0,
        "records_updated": 0,
        "records_missing_or_unchanged": 0,
        "records_without_image_field": 0,
    }

    # On traite 2 cas fréquents:
    #  1) data = { group_name: { "filename.jpg": { ...record... }, ... }, ... }
    #  2) data = { "filename.jpg": { ...record... }, ... }  (sans groupes)
    def is_record(d: Any) -> bool:
        return isinstance(d, dict) and (("image_path" in d) or ("image_name" in d))

    # Cas 1: top-level dict de groupes ?
    treated_as_grouped = False
    if isinstance(data, dict):
        # Si toutes/souvent les valeurs sont des dicts d'items qui ressemblent à {filename: record}
        # on essaie de les parcourir comme groupes.
        grouped_candidates = 0
        for v in data.values():
            if isinstance(v, dict) and any(is_record(vv) for vv in v.values() if isinstance(vv, dict)):
                grouped_candidates += 1
        if grouped_candidates > 0:
            treated_as_grouped = True

    if treated_as_grouped and isinstance(data, dict):
        for group_key, images_map in data.items():
            counters["groups"] += 1
            if not isinstance(images_map, dict):
                continue
            for img_key, rec in list(images_map.items()):
                if not isinstance(rec, dict):
                    continue
                counters["records_scanned"] += 1
                updated, had_img_field = _process_record_in_place(
                    rec, group_key,
                    search_folder=search_folder,
                    find_images_by_sub_folder=find_images_by_sub_folder,
                    idx_sub_name=idx_sub_name,
                    idx_by_name=idx_by_name
                )
                if updated:
                    counters["records_updated"] += 1
                else:
                    counters["records_missing_or_unchanged"] += 1
                if not had_img_field:
                    counters["records_without_image_field"] += 1
    else:
        # Cas 2: dictionnaire plat de {filename: record}
        if isinstance(data, dict):
            for img_key, rec in list(data.items()):
                if not isinstance(rec, dict):
                    continue
                counters["records_scanned"] += 1
                updated, had_img_field = _process_record_in_place(
                    rec, None,
                    search_folder=search_folder,
                    find_images_by_sub_folder=find_images_by_sub_folder,
                    idx_sub_name=idx_sub_name,
                    idx_by_name=idx_by_name
                )
                if updated:
                    counters["records_updated"] += 1
                else:
                    counters["records_missing_or_unchanged"] += 1
                if not had_img_field:
                    counters["records_without_image_field"] += 1
        else:
            raise ValueError("Format d'annotation inattendu: data n'est pas un dict JSON au top-level.")

    # Écriture de la copie mise à jour
    annot_out.parent.mkdir(parents=True, exist_ok=True)
    with annot_out.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    if strict and counters["records_missing_or_unchanged"] > 0:
        raise RuntimeError(
            f"{counters['records_missing_or_unchanged']} enregistrements non résolus (ou inchangés). "
            f"Sortie écrite dans: {annot_out}"
        )

    return {"counters": counters, "out": str(annot_out)}



# 1) Utiliser un répertoire plat (toutes les images dans un même dossier)
report = rewrite_annotation_paths(
    annot_in="/media/hamed/8TO_2/sauvegardes_28_06_2024/Annotations_files/fusion/4FOUR/Split_test_train_same_distribution/train.json",
    annot_out="/media/hamed/8TO_2/sauvegardes_28_06_2024/Annotations_files/fusion/4FOUR/Split_test_train_same_distribution/train_good_path.json",
    find_images_by_sub_folder="/media/hamed/8TO_2/sauvegardes_28_06_2024/Movies_to_images/",  # <-- on fait <search_folder>/<filename>
    strict=True
)
print(report)