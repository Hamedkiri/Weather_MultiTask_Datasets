#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps
import json
import shutil
from datetime import datetime
import random
import math, time
from collections import defaultdict, Counter
import itertools
import statistics
from typing import Optional, List, Dict, Tuple

# Graphiques
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# ------------------------
# Helpers globaux
# ------------------------
_TS_PATTERNS = [
    re.compile(r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})[T _\-]?(\d{2})[:\-]?(\d{2})[:\-]?(\d{2})'),
    re.compile(r'ts[_-]?(\d{10})'),
    re.compile(r'(\d{10})')
]

_IMG_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def gini_index(counts):
    total = sum(counts)
    if total <= 1:
        return 0.0
    sorted_counts = sorted(counts)
    cum = 0
    for i, x in enumerate(sorted_counts, 1):
        cum += i * x
    return (2*cum)/(total*(len(counts)+1)) - (len(counts)+1)/len(counts)

def entropy_from_counts(counts):
    total = sum(counts)
    if total == 0:
        return 0.0
    import math
    ent = 0.0
    for c in counts:
        if c > 0:
            p = c/total
            ent -= p*math.log(p+1e-12)
    return ent

def jain_index(counts):
    if not counts:
        return 1.0
    s = sum(counts)
    if s == 0: return 1.0
    sq = sum(c*c for c in counts)
    n = len(counts)
    return (s*s) / (n * max(sq, 1e-12))

def theil_T(counts):
    n = len(counts)
    if n == 0:
        return 0.0
    mean = (sum(counts) / n) if sum(counts) > 0 else 0
    if mean <= 0:
        return 0.0
    import math
    t = 0.0
    for x in counts:
        if x > 0:
            r = x / mean
            t += r * math.log(r)
    return t / n

def hhi(counts):
    s = sum(counts)
    if s == 0:
        return 0.0
    return sum((c/s)**2 for c in counts)

def simpson_diversity(counts):
    return 1.0 - hhi(counts)

def _path_with_alt_ext(path: str) -> Optional[str]:
    """Si path n'existe pas, essaie les mêmes nom/chemin avec extensions d'images usuelles."""
    if not path:
        return None
    root, ext = os.path.splitext(path)
    # Essai tel quel
    if os.path.exists(path):
        return path
    # Essai en normalisant l'extension s'il y en a une
    if ext:
        cand = root + ext.lower()
        if os.path.exists(cand):
            return cand
    # Essai sur chaque extension image connue
    for e in _IMG_EXTS:
        cand = root + e
        if os.path.exists(cand):
            return cand
    return None

# ------------------------
# Conteneur scrollable anti-boucle
# ------------------------
class SafeScrollableFrame(tk.Frame):
    """
    Conteneur scrollable qui évite les boucles de <Configure> en dé-bounçant
    la mise à jour du scrollregion avec after_idle.
    """
    def __init__(self, master, orient="vertical", **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.inner = tk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.vbar = None
        if orient == "vertical":
            self.vbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=self.vbar.set)
            self.vbar.pack(side="right", fill="y")

        self.canvas.pack(side="left", fill="both", expand=True)

        self._pending = False
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # molette
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind("<Button-5>", self._on_mousewheel_linux)

    def _on_inner_configure(self, _event=None):
        if not self._pending:
            self._pending = True
            self.after_idle(self._update_scrollregion)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)
        if not self._pending:
            self._pending = True
            self.after_idle(self._update_scrollregion)

    def _update_scrollregion(self):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        finally:
            self._pending = False

    def _on_mousewheel(self, event):
        if self.vbar:
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _on_mousewheel_linux(self, event):
        if self.vbar:
            if event.num == 4:
                self.canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(3, "units")

# ------------------------
# Égalisation stricte + caps (Hamilton)
# ------------------------
def fair_quotas(sizes: dict, N: int, min_frac: float = 0.0, max_frac: float = 1.0) -> dict:
    srcs = list(sizes.keys())
    S = len(srcs)
    if N <= 0 or S == 0:
        return {s: 0 for s in srcs}

    base = math.floor(N / S)
    min_q = {s: min(sizes[s], math.floor(min_frac * N)) for s in srcs}
    max_q = {s: min(sizes[s], math.floor(max_frac * N)) for s in srcs}

    q = {s: min(max(base, min_q[s]), max_q[s]) for s in srcs}
    for s in srcs:
        q[s] = min(q[s], sizes[s])

    total = sum(q.values())

    def room(s):
        return max(0, min(sizes[s], max_q[s]) - q[s])

    while total < N:
        candidates = [s for s in srcs if room(s) > 0]
        if not candidates:
            break
        candidates.sort(key=lambda s: (room(s), sizes[s]), reverse=True)
        for s in candidates:
            if total >= N: break
            q[s] += 1
            total += 1

    while total > N:
        candidates = sorted(srcs, key=lambda s: (q[s], sizes[s]), reverse=True)
        for s in candidates:
            if total <= N: break
            if q[s] > min_q[s]:
                q[s] -= 1
                total -= 1

    return q

# ------------------------
# Égalité douce (Efraimidis–Spirakis)
# ------------------------
def efraimidis_spirakis_pick(by_src: dict, target: int, rng: random.Random) -> list:
    if target <= 0:
        return []
    keys = []
    for s, lst in by_src.items():
        n = max(1, len(lst))
        w = 1.0 / n
        for a in lst:
            u = rng.random()
            k = u ** (1.0 / max(w, 1e-12))
            keys.append((k, a))
    if not keys:
        return []
    keys.sort(key=lambda t: t[0], reverse=True)
    picked = [a for _, a in keys[:target]]
    return picked

class ImageAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("Annotateur d'Images Météo")
        self.root.geometry("1300x800")
        self.root.resizable(True, True)

        # 0) Langue de l'interface : À DÉFINIR ICI
        self.ui_lang_var = tk.StringVar(value="EN")  # interface EN par défaut

        # Données principales
        self.images: List[str] = []
        self.annotations: Dict[str, Dict[str, dict]] = {}
        self.filtered_annotations: Dict[str, Dict[str, dict]] = {}
        self.annotation_file_path = ""
        self.current_index = 0
        self.image_folders = {}
        self.annotated_image_paths: List[str] = []

        # Racines (pour résoudre des chemins des JSON)
        self.initial_images_root: Optional[str] = None   # dossier choisi au lancement
        self.annotations_images_root: Optional[str] = None  # racine choisie si chemins du JSON sont relatifs/invalides

        self.attributes = {
            "Weather Type": ["Clear", "Sun and Clear", "Rain", "Snow", "Fog", "Fog and Rain", "Fog and Snow", "None"],
            "Weather Intensity": ["Low", "Average", "High", "None"],
            "Visibility": ["Very Low", "Low", "Average", "Good"],
            "Sky Condition": ["Unknown", "Clear Sky", "Partly Cloudy", "Cloudy", "Overcast", "Partly Overcast"],
            "Precipitation Presence": ["None", "Rain", "Snow", "Hail"],
            "Precipitation Intensity": ["None", "Low", "Average", "High"],
            "Ground Condition": ["Dry", "Wet", "Partly Wet", "Snowy", "Partly Snowy", "Wet and Snowy", "Unknown"],
            "Glare or Reflections": ["Absent", "Present"],
            "Light Conditions": ["Day", "Night", "Sunset", "Sunrise", "artificial"],
            "Road Spray": ["Absent", "Present"],
            "Water On Window": ["Absent", "Present", "None"],
            "Snow On Window": ["Absent", "Present", "None"],
            "Point of view": ["Road Vehicules", "Pedestrian", "Road Camera", "Other"]
        }

        self.default_values = {}
        self.annotation_vars = {}

        # 1) Valeurs par défaut
        self.setup_defaults()

        # 2) Charger les images (peut être annulé : on pourra n’utiliser que le JSON)
        self.load_images(allow_cancel=True)

        # 3) Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.annotation_tab = ttk.Frame(self.notebook)
        self.manager_tab = ttk.Frame(self.notebook)
        self.stats_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.annotation_tab, text=self._ui("tab_annotation"))
        self.notebook.add(self.manager_tab, text=self._ui("tab_manager"))
        self.notebook.add(self.stats_tab, text=self._ui("tab_stats"))

        # 4) UI avec conteneur scrollable de chaque onglet
        self.create_annotation_tab_ui(self.annotation_tab)
        self.create_manager_tab_ui(self.manager_tab)
        self.create_stats_tab_ui(self.stats_tab)

        # Anti-boucle / mémo de rendu
        self._resize_job = None
        self._rendering_image = False
        self._last_render_size = (None, None)
        self._last_image_path = None

        # 7) Première image
        self.update_interface()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Configure>', self.on_window_resize)
        self.root.bind('<Left>', self.on_left_arrow)
        self.root.bind('<Right>', self.on_right_arrow)

        # 2) Sélecteur de langue UI en haut de fenêtre
        self.setup_ui_language_switch()

        # Langue de l'interface (EN par défaut)
        # "EN" -> interface en anglais, "FR" -> interface en français

    # ---------------------------------------------------------
    # Résolution robuste des chemins d'image venant des annotations
    # ---------------------------------------------------------
    def _resolve_image_path(self, folder: str, image_name: str, ann: dict) -> Optional[str]:
        """
        Ordre d'essais :
        1) ann['image_path'] s'il existe (ou avec extension alternative)
        2) chemin relatif à self.annotations_images_root (si définie) : root/folder/image_name
        3) chemin relatif à self.initial_images_root (si définie)
        4) si 'image_path' est relatif et que annotations_images_root est définie, join(root, image_path)
        5) si 'image_path' est relatif et initial_images_root est définie, join(initial_root, image_path)
        """
        # 1) Champs 'image_path' direct
        p = ann.get('image_path') or ''
        if p:
            cand = _path_with_alt_ext(p if os.path.isabs(p) else os.path.abspath(p))
            if cand:
                return cand

        # 2) Racine d'images choisie POUR le JSON (si cochée)
        if self.annotations_images_root:
            cand2 = _path_with_alt_ext(os.path.join(self.annotations_images_root, folder, image_name))
            if cand2:
                return cand2
            if p and not os.path.isabs(p):
                cand2 = _path_with_alt_ext(os.path.join(self.annotations_images_root, p))
                if cand2:
                    return cand2

        # 3) Racine d'images INITIALE (si l’utilisateur a sélectionné un dossier au démarrage)
        if self.initial_images_root:
            cand2 = _path_with_alt_ext(os.path.join(self.initial_images_root, folder, image_name))
            if cand2:
                return cand2

        # 5) Dernière chance : si p est un chemin relatif et initial_images_root est connue
        if p and not os.path.isabs(p) and self.initial_images_root:
            cand2 = _path_with_alt_ext(os.path.join(self.initial_images_root, p))
            if cand2:
                return cand2

        return None

    # ---------------------------------------------------------
    # 1) Configuration par défaut
    # ---------------------------------------------------------
    def setup_defaults(self):
        setup_window = tk.Toplevel(self.root)
        setup_window.title("Définir les Valeurs par Défaut")
        setup_window.grab_set()

        tk.Label(setup_window, text="Sélectionnez les valeurs par défaut :", font=("Arial", 10)).pack(pady=10)
        self.setup_vars = {}

        for attribute, options in self.attributes.items():
            frame = tk.LabelFrame(setup_window, text=attribute)
            frame.pack(fill="x", padx=10, pady=5)
            var = tk.StringVar(value=options[0])
            self.setup_vars[attribute] = var
            num_columns = 2
            options_frame = tk.Frame(frame)
            options_frame.pack()
            for idx, option in enumerate(options):
                tk.Radiobutton(options_frame, text=option, variable=var, value=option)\
                    .grid(row=idx // num_columns, column=idx % num_columns, sticky='w', padx=5, pady=2)

        btn_frame = tk.Frame(setup_window)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Confirmer", command=lambda: self.confirm_defaults(setup_window)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Annuler", command=setup_window.destroy).pack(side=tk.LEFT, padx=5)
        self.root.wait_window(setup_window)

    def confirm_defaults(self, setup_window):
        for attribute, var in self.setup_vars.items():
            self.default_values[attribute] = var.get()
        setup_window.destroy()

    # ---------------------------------------------------------
    # 2) Chargement des images (dossier)
    # ---------------------------------------------------------
    def load_images(self, allow_cancel=False):
        directory = filedialog.askdirectory(title="Sélectionnez le répertoire des images (Annuler si vous utiliserez un JSON)")
        if not directory:
            if allow_cancel:
                self.initial_images_root = None
                return
            messagebox.showerror("Erreur", "Aucun répertoire sélectionné.")
            self.root.destroy()
            return

        self.initial_images_root = directory
        image_paths = []
        for root_dir, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(_IMG_EXTS):
                    image_paths.append(os.path.join(root_dir, file))
        image_paths.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
        self.images.extend(image_paths)

        for img_path in image_paths:
            folder = os.path.basename(os.path.dirname(img_path))
            img_name = os.path.basename(img_path)
            self.image_folders.setdefault(folder, []).append(img_name)

        if not self.images and not allow_cancel:
            messagebox.showwarning("Avertissement", "Aucune image trouvée dans ce répertoire.")
            self.root.destroy()

    # ---------------------------------------------------------
    # Parcours / Annotées
    # ---------------------------------------------------------
    def toggle_browse_mode(self):
        is_browse = self.browse_mode_var.get()
        self._apply_browse_mode_state(is_browse)
        self.update_interface(load_saved_annotations=True)

    def toggle_only_annotated_mode(self):
        if self.only_annotated_var.get():
            if not self.annotations:
                messagebox.showwarning("Attention", "Aucun fichier d'annotations chargé. Charge-le d'abord.")
                self.only_annotated_var.set(False)
                return
            self._rebuild_annotated_image_list()
            if not self.annotated_image_paths:
                messagebox.showwarning("Attention", "Aucune image valide trouvée dans le fichier d'annotations (chemins introuvables).")
                self.only_annotated_var.set(False)
                return
        self.current_index = 0
        self.update_interface(load_saved_annotations=True)

    def _rebuild_annotated_image_list(self):
        """Reconstruit la liste d'images à partir du JSON en résolvant les chemins."""
        paths = []
        missing = 0
        for folder in sorted(self.annotations.keys()):
            imgs = self.annotations[folder]
            for image_name, ann in sorted(imgs.items(), key=lambda kv: natural_sort_key(kv[0])):
                p = self._resolve_image_path(folder, image_name, ann)
                if p and os.path.exists(p):
                    paths.append(p)
                else:
                    missing += 1
        self.annotated_image_paths = paths

        # Si beaucoup d'images manquantes, proposer une racine
        if missing > 0 and (not self.annotations_images_root):
            if messagebox.askyesno("Chemins manquants",
                                   f"{missing} image(s) d'annotations introuvable(s).\n"
                                   f"Voulez-vous choisir une racine d'images pour résoudre les chemins ?"):
                root = filedialog.askdirectory(title="Choisissez la racine d'images correspondant au JSON")
                if root:
                    self.annotations_images_root = root
                    # Re-essayer avec la nouvelle racine
                    return self._rebuild_annotated_image_list()

    def _get_active_images(self):
        if getattr(self, 'only_annotated_var', None) and self.only_annotated_var.get():
            return self.annotated_image_paths
        return self.images

    def _apply_browse_mode_state(self, is_browse: bool):
        if is_browse:
            self.set_state_recursive(self.annotation_frame, 'disabled')
            if 'state' in self.change_save_path_btn.configure():
                self.change_save_path_btn.configure(state='disabled')
            if 'state' in self.change_defaults_btn.configure():
                self.change_defaults_btn.configure(state='disabled')
            self.prev_button.configure(state='normal')
            self.next_button.configure(state='normal')
        else:
            self.set_state_recursive(self.annotation_frame, 'normal')
            if 'state' in self.change_save_path_btn.configure():
                self.change_save_path_btn.configure(state='normal')
            if 'state' in self.change_defaults_btn.configure():
                self.change_defaults_btn.configure(state='normal')

    # ---------------------------------------------------------
    # 3) Interface onglet Annotation (scroll global)
    # ---------------------------------------------------------
    def create_annotation_tab_ui(self, parent):
        # conteneur scrollable de l’onglet
        tab_scroll = SafeScrollableFrame(parent, orient="vertical")
        tab_scroll.pack(fill="both", expand=True)
        tab = tab_scroll.inner

        main_frame = tk.Frame(tab)
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        # Top actions
        top_frame = tk.Frame(main_frame)
        top_frame.grid(row=0, column=0, columnspan=2, pady=5)
        self.btn_load_annotations = tk.Button(
            top_frame,
            text=self._ui("btn_load_ann"),
            command=self.load_annotations
        )
        self.btn_load_annotations.pack(side=tk.LEFT, padx=5)

        self.btn_create_annotations = tk.Button(
            top_frame,
            text=self._ui("btn_create_ann"),
            command=self.create_new_annotations
        )
        self.btn_create_annotations.pack(side=tk.LEFT, padx=5)

        self.load_more_btn = tk.Button(
            top_frame,
            text=self._ui("btn_load_more"),
            command=self.load_additional_images
        )
        self.load_more_btn.pack(side=tk.LEFT, padx=5)

        self.btn_open_manager = tk.Button(
            top_frame,
            text=self._ui("btn_manage_ann"),
            command=self.open_annotation_manager
        )
        self.btn_open_manager.pack(side=tk.LEFT, padx=5)

        self.btn_use_json_images = tk.Button(
            top_frame,
            text=self._ui("btn_use_json_images"),
            command=self.use_images_from_annotations
        )
        self.btn_use_json_images.pack(side=tk.LEFT, padx=5)

        # Content split
        content_frame = tk.Frame(main_frame)
        content_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # Image area
        image_frame = tk.Frame(content_frame)
        image_frame.grid(row=0, column=0, sticky="nsew")
        self.image_label = tk.Label(image_frame, bg="#101014")
        self.image_label.pack(fill="both", expand=True)
        self.remaining_label = tk.Label(image_frame, text="")
        self.remaining_label.pack()

        # Annotation area (scrollable, SAFE)
        annotation_container = tk.Frame(content_frame)
        annotation_container.grid(row=0, column=1, sticky="ns")
        scrollable = SafeScrollableFrame(annotation_container, orient="vertical")
        scrollable.pack(fill="both", expand=True)
        self.annotation_frame = scrollable.inner

        # Radios
        self.annotation_vars.clear()
        for attribute, options in self.attributes.items():
            frame = tk.LabelFrame(self.annotation_frame, text=attribute)
            frame.pack(fill="x", padx=10, pady=5)
            var = tk.StringVar(value=self.default_values.get(attribute, options[0]))
            self.annotation_vars[attribute] = var
            for option in options:
                tk.Radiobutton(frame, text=option, variable=var, value=option).pack(anchor='w', padx=5, pady=2)

        # Bottom bar
        bottom_frame = tk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, columnspan=2, pady=5)

        self.buttons_frame = tk.Frame(bottom_frame)
        self.buttons_frame.pack()
        self.prev_button = tk.Button(self.buttons_frame, text=self._ui("btn_prev"), command=self.prev_image)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        self.next_button = tk.Button(self.buttons_frame, text=self._ui("btn_next"), command=self.next_image)
        self.next_button.pack(side=tk.LEFT, padx=5)

        # Cases à cocher
        mode_frame = tk.Frame(bottom_frame)
        mode_frame.pack(pady=2)

        self.browse_mode_var = tk.BooleanVar(value=False)
        self.browse_checkbutton = tk.Checkbutton(
            mode_frame,
            text=self._ui("chk_browse"),
            variable=self.browse_mode_var,
            command=self.toggle_browse_mode
        )
        self.browse_checkbutton.grid(row=0, column=0, padx=6, sticky="w")

        self.only_annotated_var = tk.BooleanVar(value=False)
        self.only_annotated_checkbutton = tk.Checkbutton(
            mode_frame,
            text=self._ui("chk_only_annotated"),
            variable=self.only_annotated_var,
            command=self.toggle_only_annotated_mode
        )
        self.only_annotated_checkbutton.grid(row=0, column=1, padx=6, sticky="w")

        self.change_defaults_btn = tk.Button(
            bottom_frame,
            text=self._ui("btn_change_defaults"),
            command=self.setup_defaults
        )
        self.change_defaults_btn.pack(pady=5)

        self.change_save_path_btn = tk.Button(
            bottom_frame,
            text=self._ui("btn_change_save"),
            command=self.change_save_path
        )
        self.change_save_path_btn.pack(pady=5)

        self.save_path_label = tk.Label(bottom_frame, text=self._ui("label_save_path_none"))
        self.save_path_label.pack()

        # Etat initial
        self.disable_annotation_widgets()
        self.enable_annotation_widgets()

    # Enable/Disable
    def set_state_recursive(self, widget, state):
        if isinstance(widget, (tk.Canvas,)):
            return
        try:
            widget.configure(state=state)
        except Exception:
            pass
        for child in widget.winfo_children():
            self.set_state_recursive(child, state)

    def disable_annotation_widgets(self):
        self.set_state_recursive(self.annotation_frame, 'disabled')
        self.set_state_recursive(self.buttons_frame, 'disabled')
        if 'state' in self.change_save_path_btn.configure():
            self.change_save_path_btn.configure(state='disabled')
        if 'state' in self.load_more_btn.configure():
            self.load_more_btn.configure(state='disabled')
        if 'state' in self.change_defaults_btn.configure():
            self.change_defaults_btn.configure(state='disabled')

    def enable_annotation_widgets(self):
        self.set_state_recursive(self.annotation_frame, 'normal')
        self.set_state_recursive(self.buttons_frame, 'normal')
        if 'state' in self.change_save_path_btn.configure():
            self.change_save_path_btn.configure(state='normal')
        if 'state' in self.load_more_btn.configure():
            self.load_more_btn.configure(state='normal')
        if 'state' in self.change_defaults_btn.configure():
            self.change_defaults_btn.configure(state='normal')

    # ---------------------------------------------------------
    # Bouton : utiliser les images résolues depuis le JSON
    # ---------------------------------------------------------
    def use_images_from_annotations(self):
        if not self.annotations:
            messagebox.showwarning("Info", "Charge d'abord un fichier d'annotations.")
            return
        self._rebuild_annotated_image_list()
        if not self.annotated_image_paths:
            messagebox.showwarning("Info", "Aucune image résolue depuis le JSON.")
            return
        # Remplace la liste d'images active par celles du JSON résolu
        self.images = list(self.annotated_image_paths)
        self.current_index = 0
        messagebox.showinfo("Succès", f"{len(self.images)} images chargées depuis le JSON (chemins résolus).")
        self.update_interface(load_saved_annotations=True)

    # ---------------------------------------------------------
    # Diagnostic faisabilité split
    # ---------------------------------------------------------
    def diagnose_split_feasibility(self):
        if not self.annotations:
            messagebox.showerror("Erreur", "Aucune annotation chargée.")
            return

        anns = [ann for imgs in (self.filtered_annotations or self.annotations).values() for ann in imgs.values()]
        if not anns:
            messagebox.showerror("Erreur", "Aucune annotation disponible.")
            return

        strat_task = self.stratify_task_var.get()
        if strat_task == "(aucune)":
            strat_task = None

        by_src = self._group_by_source(anns)

        prepared = {}
        for s, v in by_src.items():
            prepared[s] = self._ensure_diversity_per_source(
                v,
                gap_mode=self.gap_mode_var.get(),
                min_gap_s=float(self.min_time_gap_var.get()),
                min_gap_frames=int(self.min_frame_gap_var.get())
            )

        total_after = sum(len(v) for v in prepared.values())
        n_sources = len(prepared)

        max_pct = max(5.0, min(100.0, float(self.max_pct_per_source_var.get()))) / 100.0
        min_pct = max(0.0, min(100.0, float(self.min_pct_per_source_var.get()))) / 100.0
        per_source_counts = sorted((len(v) for v in prepared.values()), reverse=True)
        mean_per_source = (sum(per_source_counts) / n_sources) if n_sources else 0

        gap_desc = f"mode={self.gap_mode_var.get()} | min_gap={self.min_time_gap_var.get():.2f}s / {int(self.min_frame_gap_var.get())} frames"

        lines = [
            f"Images après préparation: {total_after}",
            f"Nombre de sources: {n_sources}",
            f"Moyenne images/source: {mean_per_source:.1f}",
            f"Bornes par source: min={int(min_pct*100)}%  max={int(max_pct*100)}%",
            f"Préparation: thinning + interleave quantiles ({gap_desc})",
            f"Soft sampling (Efraimidis–Spirakis): {'ON' if self.soft_equal_sampling_var.get() else 'OFF'}"
        ]

        if strat_task:
            class_per_source = defaultdict(Counter)
            for s, lst in prepared.items():
                for a in lst:
                    class_per_source[s][a.get(strat_task, "__none__")] += 1
            class_tot = Counter()
            for s, c in class_per_source.items():
                class_tot.update(c)
            lines.append(f"Tâche de stratification: {strat_task}")
            for cls, cnt in class_tot.items():
                src_with_cls = sum(1 for s in class_per_source if class_per_source[s][cls] > 0)
                lines.append(f" - {cls}: {cnt} images, présentes dans {src_with_cls} sources")

        messagebox.showinfo("Diagnostic de faisabilité", "\n".join(lines))

    # ---------------------------------------------------------
    # 4) Interface onglet Gestion (scroll global)
    # ---------------------------------------------------------
    def create_manager_tab_ui(self, parent):
        tab_scroll = SafeScrollableFrame(parent, orient="vertical")
        tab_scroll.pack(fill="both", expand=True)
        main_frame = tk.Frame(tab_scroll.inner)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Ligne d'actions
        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill="x", pady=5)
        tk.Button(top_frame, text="Charger annotations", command=self.load_annotations_manager).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Filtrer", command=self.filter_annotations).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Exporter JSON", command=self.export_filtered_annotations).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Générer JSON avec N images", command=self.generate_selected_json).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Split Train/Test", command=self.split_train_test).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Copier les images annotées", command=self.copy_annotated_images).pack(side=tk.LEFT, padx=5)

        # Filtres par attribut
        filter_frame = tk.LabelFrame(main_frame, text="Filtres")
        filter_frame.pack(fill="x", padx=5, pady=5)
        self.filter_vars = {}
        row_idx = 0
        for attribute, options in self.attributes.items():
            tk.Label(filter_frame, text=attribute).grid(row=row_idx, column=0, padx=5, pady=2, sticky='w')
            var = tk.StringVar(value="Tous")
            self.filter_vars[attribute] = var
            tk.OptionMenu(filter_frame, var, "Tous", *options).grid(row=row_idx, column=1, padx=5, pady=2, sticky='w')
            row_idx += 1

        list_image_frame = tk.Frame(main_frame)
        list_image_frame.pack(fill="both", expand=True, padx=5, pady=5)
        list_image_frame.grid_columnconfigure(0, weight=0)
        list_image_frame.grid_columnconfigure(1, weight=1)
        list_image_frame.grid_rowconfigure(0, weight=1)

        # --- Liste (col 0) ---
        list_frame = tk.Frame(list_image_frame)
        list_frame.grid(row=0, column=0, sticky="ns")

        self.annotations_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, width=50)
        self.annotations_listbox.pack(side=tk.LEFT, fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.annotations_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill="y")
        self.annotations_listbox.config(yscrollcommand=scrollbar.set)

        self.annotations_listbox.bind("<<ListboxSelect>>", self.on_annotation_select)

        # --- Aperçu (col 1) ---
        image_frame = tk.Frame(list_image_frame)
        image_frame.grid(row=0, column=1, sticky="nsew", padx=10)
        self.manager_image_label = tk.Label(image_frame, bg="#101014")
        self.manager_image_label.pack(fill="both", expand=True)

        self.filtered_count_label = tk.Label(main_frame, text="Nombre d'images filtrées: 0")
        self.filtered_count_label.pack(pady=5)

        # Options de split / hétérogénéité
        options_frame = tk.LabelFrame(main_frame, text="Options de split / hétérogénéité")
        options_frame.pack(fill="x", padx=5, pady=5)

        self.split_by_source_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Split par source vidéo (dossier)", variable=self.split_by_source_var)\
            .grid(row=0, column=0, sticky="w", padx=5, pady=2)

        self.timestamp_diverse_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options_frame, text="Diversifier dans chaque set (espacer les prises)",
                       variable=self.timestamp_diverse_var).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # --- Mode d'écart (secondes vs images) ---
        self.gap_mode_var = tk.StringVar(value="seconds")  # "seconds" | "frames"
        tk.Label(options_frame, text="Mode d'écart:").grid(row=0, column=2, sticky="e", padx=5)
        tk.Radiobutton(options_frame, text="Secondes", variable=self.gap_mode_var, value="seconds")\
            .grid(row=0, column=3, sticky="w", padx=2)
        tk.Radiobutton(options_frame, text="Images", variable=self.gap_mode_var, value="frames")\
            .grid(row=0, column=4, sticky="w", padx=2)

        # Valeurs minimales selon le mode
        tk.Label(options_frame, text="Min écart (s):").grid(row=0, column=5, sticky="e", padx=5)
        self.min_time_gap_var = tk.DoubleVar(value=2.0)
        entry_time = tk.Entry(options_frame, width=6, textvariable=self.min_time_gap_var)
        entry_time.grid(row=0, column=6, sticky="w", padx=5)

        tk.Label(options_frame, text="Min écart (images):").grid(row=0, column=7, sticky="e", padx=5)
        self.min_frame_gap_var = tk.IntVar(value=5)
        entry_frames = tk.Entry(options_frame, width=6, textvariable=self.min_frame_gap_var)
        entry_frames.grid(row=0, column=8, sticky="w", padx=5)

        def _refresh_gap_inputs(*_):
            is_sec = (self.gap_mode_var.get() == "seconds")
            entry_time.configure(state=("normal" if is_sec else "disabled"))
            entry_frames.configure(state=("disabled" if is_sec else "normal"))

        self.gap_mode_var.trace_add("write", _refresh_gap_inputs)
        _refresh_gap_inputs()

        # --- Caps min/max par source ---
        tk.Label(options_frame, text="Min %/source:").grid(row=0, column=9, sticky="e", padx=5)
        self.min_pct_per_source_var = tk.DoubleVar(value=0.0)
        tk.Entry(options_frame, width=6, textvariable=self.min_pct_per_source_var)\
            .grid(row=0, column=10, sticky="w", padx=5)

        tk.Label(options_frame, text="Max %/source:").grid(row=0, column=11, sticky="e", padx=5)
        self.max_pct_per_source_var = tk.DoubleVar(value=40.0)
        tk.Entry(options_frame, width=6, textvariable=self.max_pct_per_source_var)\
            .grid(row=0, column=12, sticky="w", padx=5)

        # --- Soft sampling (Efraimidis–Spirakis) ---
        self.soft_equal_sampling_var = tk.BooleanVar(value=False)
        tk.Checkbutton(options_frame,
                       text="Soft sampling (Efraimidis–Spirakis) — égalité douce entre sources",
                       variable=self.soft_equal_sampling_var)\
            .grid(row=1, column=0, columnspan=6, sticky="w", padx=5, pady=2)

        tk.Label(options_frame, text="Tâche de stratification:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        choices = ["(aucune)"] + list(self.attributes.keys())
        self.stratify_task_var = tk.StringVar(value="(aucune)")
        tk.OptionMenu(options_frame, self.stratify_task_var, *choices)\
            .grid(row=2, column=1, sticky="w", padx=5, pady=2)

        # --- Modes EXACTS (exclusifs) + entrées N train / N test ---
        self.exact_mode_var = tk.BooleanVar(value=False)  # disjoint
        self.exact_shared_mode_var = tk.BooleanVar(value=False)  # sources partagées

        def _toggle_exact_entries():
            any_exact = self.exact_mode_var.get() or self.exact_shared_mode_var.get()
            self.train_exact_entry.configure(state=("normal" if any_exact else "disabled"))
            self.test_exact_entry.configure(state=("normal" if any_exact else "disabled"))
            self.timestamp_diverse_var.set(False)

        def _on_toggle_disjoint():
            if self.exact_mode_var.get():
                self.exact_shared_mode_var.set(False)
            _toggle_exact_entries()

        def _on_toggle_shared():
            if self.exact_shared_mode_var.get():
                self.exact_mode_var.set(False)
            _toggle_exact_entries()

        tk.Checkbutton(
            options_frame,
            text="Mode exact (N train & N test, sources disjointes, quotas Hamilton + min/max, tirage intra-source)",
            variable=self.exact_mode_var,
            command=_on_toggle_disjoint
        ).grid(row=3, column=0, columnspan=12, sticky="w", padx=5, pady=4)

        tk.Checkbutton(
            options_frame,
            text="Mode exact (sources partagées, mêmes distributions, quotas Hamilton combinés, sans répétition d'images)",
            variable=self.exact_shared_mode_var,
            command=_on_toggle_shared
        ).grid(row=4, column=0, columnspan=12, sticky="w", padx=5, pady=2)

        tk.Label(options_frame, text="N train:").grid(row=5, column=0, sticky="e", padx=5)
        self.train_exact_n_var = tk.IntVar(value=0)
        self.train_exact_entry = tk.Entry(options_frame, width=8, textvariable=self.train_exact_n_var, state="disabled")
        self.train_exact_entry.grid(row=5, column=1, sticky="w", padx=5)

        tk.Label(options_frame, text="N test:").grid(row=5, column=2, sticky="e", padx=5)
        self.test_exact_n_var = tk.IntVar(value=0)
        self.test_exact_entry = tk.Entry(options_frame, width=8, textvariable=self.test_exact_n_var, state="disabled")
        self.test_exact_entry.grid(row=5, column=3, sticky="w", padx=5)

        tk.Button(options_frame, text="Diagnostiquer faisabilité", command=self.diagnose_split_feasibility)\
            .grid(row=2, column=2, columnspan=2, sticky="w", padx=5)

        self.manager_displayed_image = None

    # ----------------- Helpers sources/timestamps/frames -----------------
    def _extract_source(self, ann):
        return ann.get('folder', 'unknown')

    def _get_timestamp_s(self, ann):
        """
        Extrait un timestamp en SECONDES (float) de façon robuste :
          1) séquence compacte YYYYMMDDhhmmss[sss|uuuuuu|nnnnnnnnn] dans image_name
          2) patterns existants (_TS_PATTERNS) dans image_name
          3) mtime du fichier image_path (si disponible)
        Renvoie 0.0 en dernier recours.
        """
        import os, re, datetime

        name = ann.get('image_name', '') or ''

        # (1) Compact : 20250620142150[188075]...
        m = max(re.findall(r'(\d{14,})', name), key=len, default=None)
        if m:
            digits = m
            try:
                y = int(digits[0:4])
                mo = int(digits[4:6])
                d = int(digits[6:8])
                h = int(digits[8:10])
                mi = int(digits[10:12])
                sec = int(digits[12:14])

                sub = digits[14:]  # sous-secondes optionnelles
                micro = 0
                if sub:
                    if len(sub) >= 9:
                        micro = int(round(int(sub[:9]) / 1000.0))  # ns -> µs
                    elif len(sub) >= 6:
                        micro = int(sub[:6])  # µs
                    elif len(sub) >= 3:
                        micro = int(sub[:3]) * 1000  # ms -> µs
                    else:
                        micro = int(sub) * (10 ** (6 - len(sub)))  # 1–2 chiffres

                dt = datetime.datetime(y, mo, d, h, mi, sec, micro,
                                       tzinfo=datetime.timezone.utc)
                return dt.timestamp()
            except Exception:
                pass  # on tente (2)

        # (2) Tes patterns existants
        for pat in _TS_PATTERNS:
            m = pat.search(name)
            if m:
                try:
                    if len(m.groups()) == 6:
                        y, mo, d, h, mi, s = map(int, m.groups())
                        dt = datetime.datetime(y, mo, d, h, mi, s,
                                               tzinfo=datetime.timezone.utc)
                        return dt.timestamp()
                    else:
                        return float(m.group(1))
                except Exception:
                    pass

        # (3) mtime du fichier
        p = ann.get('image_path', '')
        try:
            if p and os.path.exists(p):
                return os.path.getmtime(p)
        except Exception:
            pass

        return 0.0

    def _group_by_source(self, anns):
        g = defaultdict(list)
        for a in anns:
            g[self._extract_source(a)].append(a)
        return g

    def _extract_frame_index(self, ann) -> Optional[int]:
        name = (ann.get('image_name', '') or '')
        m = re.search(r'(?i)(?:^|[_-])(?:frame|img|image|shot|f)[_-]?(\d{1,9})(?:\D|$)', name)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        tokens = [t for t in re.findall(r'(\d+)', name) if 1 <= len(t) <= 7]
        if tokens:
            try:
                return int(tokens[-1])
            except Exception:
                pass
        return None

    # --------- Nouveaux utilitaires diversité intra-source ---------
    def _auto_series_mode(self, anns):
        idx_present = sum(1 for a in anns if self._extract_frame_index(a) is not None)
        if idx_present >= 0.6 * len(anns):
            return 'frame'
        ts = [self._get_timestamp_s(a) for a in anns]
        if not ts:
            return 'frame'
        ts_sorted = sorted(ts)
        equal_runs = sum(1 for i in range(len(ts_sorted)-1) if abs(ts_sorted[i+1]-ts_sorted[i]) <= 1.0)
        if len(ts_sorted) > 1 and (equal_runs / (len(ts_sorted)-1)) >= 0.5:
            return 'frame'
        return 'time'

    def _thin_by_timestamp(self, anns, min_gap_s):
        if min_gap_s <= 0:
            return list(anns)
        anns_sorted = sorted(anns, key=self._get_timestamp_s)
        keep, last_ts = [], -1e18
        for a in anns_sorted:
            t = self._get_timestamp_s(a)
            if t - last_ts >= min_gap_s:
                keep.append(a)
                last_ts = t
        return keep

    def _thin_by_framegap(self, anns, min_gap_imgs: int):
        if min_gap_imgs <= 0:
            return list(anns)
        with_idx, no_idx = [], []
        for a in anns:
            idx = self._extract_frame_index(a)
            if idx is None:
                no_idx.append(a)
            else:
                with_idx.append((idx, a))
        with_idx.sort(key=lambda x: x[0])
        if no_idx:
            no_idx.sort(key=lambda a: natural_sort_key(a.get('image_name', '')))
        ordered = [a for _, a in with_idx] + no_idx

        kept = []
        last_pos = -10**9
        for pos, a in enumerate(ordered):
            if pos - last_pos >= min_gap_imgs:
                kept.append(a)
                last_pos = pos
        return kept

    def _quantile_interleave(self, ordered_list, n_bins: Optional[int] = None, rng: Optional[random.Random] = None):
        if rng is None:
            rng = random.Random(0)
        n = len(ordered_list)
        if n <= 2:
            return list(ordered_list)
        if n_bins is None:
            n_bins = max(4, min(32, int(math.sqrt(n))))
        bins = [[] for _ in range(n_bins)]
        chunk = math.ceil(n / n_bins)
        for i in range(n_bins):
            bins[i] = ordered_list[i*chunk:(i+1)*chunk]
            rng.shuffle(bins[i])
        out, idxs = [], [0]*n_bins
        while len(out) < n:
            progressed = False
            for b in range(n_bins):
                if idxs[b] < len(bins[b]):
                    out.append(bins[b][idxs[b]])
                    idxs[b] += 1
                    progressed = True
            if not progressed:
                break
        for i in range(0, len(out), 11):
            j = min(len(out)-1, i+5)
            if i < j:
                rng.shuffle(out[i:j])
        return out

    def _ensure_diversity_per_source(self, anns, gap_mode: str, min_gap_s: float, min_gap_frames: int):
        mode = self._auto_series_mode(anns)
        if gap_mode == "frames":
            mode = "frame"
        elif gap_mode == "seconds":
            mode = "time"

        if mode == "frame":
            lst = self._thin_by_framegap(anns, min_gap_frames)
            key = lambda a: (self._extract_frame_index(a) or 0)
        else:
            lst = self._thin_by_timestamp(anns, min_gap_s)
            key = lambda a: self._get_timestamp_s(a)

        ordered = sorted(lst, key=key)
        return self._quantile_interleave(ordered, n_bins=None, rng=random.Random(42))

    def _interleave_round_robin(self, by_src: dict, target: int, max_pct: float) -> list:
        if target <= 0 or not by_src:
            return []
        per_source_cap = max(1, int(target * max_pct)) if max_pct > 0 else target
        taken_per_src = {s: 0 for s in by_src}
        sources = list(by_src.keys())
        random.shuffle(sources)
        idx_per_src = {s: 0 for s in sources}
        total_available = sum(len(lst) for lst in by_src.values())
        goal = min(target, total_available)
        picked = []
        while len(picked) < goal:
            progressed = False
            for s in sources:
                if len(picked) >= goal:
                    break
                if taken_per_src[s] >= per_source_cap:
                    continue
                lst = by_src[s]
                i = idx_per_src[s]
                if i >= len(lst):
                    continue
                picked.append(lst[i])
                idx_per_src[s] += 1
                taken_per_src[s] += 1
                progressed = True
            if not progressed:
                break
        return picked

    # ---------------------------------------------------------
    # 5) Interface onglet Statistiques (scroll global)
    # ---------------------------------------------------------
    def create_stats_tab_ui(self, parent):
        tab_scroll = SafeScrollableFrame(parent, orient="vertical")
        tab_scroll.pack(fill="both", expand=True)
        main_frame = tk.Frame(tab_scroll.inner)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Langue ---
        lang_frame = tk.LabelFrame(main_frame, text="Langue des graphiques / Charts Language")
        lang_frame.pack(fill="x", pady=5)
        self.stats_lang_var = tk.StringVar(value="EN")

        tk.Radiobutton(lang_frame, text="Français", variable=self.stats_lang_var, value="FR").pack(side=tk.LEFT, padx=8)
        tk.Radiobutton(lang_frame, text="English", variable=self.stats_lang_var, value="EN").pack(side=tk.LEFT, padx=8)

        section_a = tk.LabelFrame(main_frame, text="Analyse d'une tâche")
        section_a.pack(fill="x", pady=5)
        tk.Label(section_a, text="Sélectionnez une tâche:").pack(side=tk.LEFT, padx=5)
        self.stats_attribute_var = tk.StringVar(value=list(self.attributes.keys())[0])
        tk.OptionMenu(section_a, self.stats_attribute_var, *self.attributes.keys()).pack(side=tk.LEFT, padx=5)
        tk.Button(section_a, text="Afficher Diagrammes", command=self.analyze_single_attribute).pack(side=tk.LEFT, padx=5)

        section_b = tk.LabelFrame(main_frame, text="Analyse Globale")
        section_b.pack(fill="both", expand=True, pady=5)
        tk.Button(section_b, text="Afficher Statistiques Globales", command=self.analyze_all_attributes).pack(pady=5)

        section_c = tk.LabelFrame(main_frame, text="Analyse de Corrélation")
        section_c.pack(fill="x", pady=5)
        tk.Label(section_c, text="Tâche 1:").pack(side=tk.LEFT, padx=5)
        self.corr_attr1_var = tk.StringVar(value=list(self.attributes.keys())[0])
        tk.OptionMenu(section_c, self.corr_attr1_var, *self.attributes.keys()).pack(side=tk.LEFT, padx=5)
        tk.Label(section_c, text="Tâche 2:").pack(side=tk.LEFT, padx=5)
        self.corr_attr2_var = tk.StringVar(value=list(self.attributes.keys())[1])
        tk.OptionMenu(section_c, self.corr_attr2_var, *self.attributes.keys()).pack(side=tk.LEFT, padx=5)
        tk.Button(section_c, text="Afficher Corrélation", command=self.analyze_correlation).pack(side=tk.LEFT, padx=5)

        section_d = tk.LabelFrame(main_frame, text="Échantillon & Diversité (par source)")
        section_d.pack(fill="x", pady=5)
        tk.Button(section_d, text="Analyser la diversité de l'échantillon (annotations filtrées ou complètes)",
                  command=self.analyze_sample_diversity).pack(side=tk.LEFT, padx=5)

        self.stats_canvas_frame = tk.Frame(main_frame)
        self.stats_canvas_frame.pack(fill="both", expand=True, pady=10)

    def _ui(self, key: str) -> str:
        """
        Traduction des textes d'interface (boutons, onglets, labels).
        self.ui_lang_var.get() == "EN" -> texte anglais
        self.ui_lang_var.get() == "FR" -> texte français
        """
        FR = {
            # Onglets
            "tab_annotation": "Annotation",
            "tab_manager": "Gestion des Annotations",
            "tab_stats": "Statistiques",

            # Onglet Annotation - haut
            "btn_load_ann": "Charger annotations existantes",
            "btn_create_ann": "Créer un nouveau fichier d'annotations",
            "btn_load_more": "Charger images supplémentaires",
            "btn_manage_ann": "Gérer les annotations",
            "btn_use_json_images": "Charger images depuis le JSON (résolu)",

            # Onglet Annotation - bas
            "btn_prev": "Précédent",
            "btn_next": "Suivant",
            "chk_browse": "Parcourir (lecture seule, n'écrit rien)",
            "chk_only_annotated": "Parcourir uniquement les images déjà annotées (depuis le JSON)",
            "btn_change_defaults": "Changer les valeurs par défaut",
            "btn_change_save": "Changer le chemin de sauvegarde",
            "label_save_path_none": "Chemin de sauvegarde: Non spécifié",

            # Sélecteur de langue
            "lang_title": "Langue de l'interface / UI Language",
            "lang_fr": "Français",
            "lang_en": "English",
        }

        EN = {
            # Tabs
            "tab_annotation": "Annotation",
            "tab_manager": "Annotations Manager",
            "tab_stats": "Statistics",

            # Annotation tab - top
            "btn_load_ann": "Load existing annotations",
            "btn_create_ann": "Create new annotation file",
            "btn_load_more": "Load additional images",
            "btn_manage_ann": "Open annotation manager",
            "btn_use_json_images": "Load images from JSON (resolved)",

            # Annotation tab - bottom
            "btn_prev": "Previous",
            "btn_next": "Next",
            "chk_browse": "Browse mode (read-only, no write)",
            "chk_only_annotated": "Browse only images already annotated (from JSON)",
            "btn_change_defaults": "Change default values",
            "btn_change_save": "Change save path",
            "label_save_path_none": "Save path: Not specified",

            # Language selector
            "lang_title": "UI Language / Langue de l'interface",
            "lang_fr": "French",
            "lang_en": "English",
        }

        d = EN if self.ui_lang_var.get() == "EN" else FR
        return d.get(key, key)

    def setup_ui_language_switch(self):
        """
        Crée un petit cadre en haut de la fenêtre pour choisir la langue de l'interface.
        À appeler une fois dans __init__.
        """
        top_lang_frame = tk.Frame(self.root)
        top_lang_frame.pack(fill="x", side="top", pady=2)

        label = tk.Label(top_lang_frame, text=self._ui("lang_title"))
        label.pack(side="left", padx=5)

        rb_fr = tk.Radiobutton(
            top_lang_frame,
            text=self._ui("lang_fr"),
            variable=self.ui_lang_var,
            value="FR",
            command=self.on_ui_language_change
        )
        rb_fr.pack(side="left", padx=5)

        rb_en = tk.Radiobutton(
            top_lang_frame,
            text=self._ui("lang_en"),
            variable=self.ui_lang_var,
            value="EN",
            command=self.on_ui_language_change
        )
        rb_en.pack(side="left", padx=5)

        # On garde une référence si on veut mettre à jour les textes au changement de langue
        self._lang_widgets = {
            "label": label,
            "rb_fr": rb_fr,
            "rb_en": rb_en,
        }

    def on_ui_language_change(self):
        """
        Callback quand la langue UI change.
        Met à jour les textes des onglets, de quelques boutons, et du sélecteur de langue.
        Tu peux ajouter ici d'autres widgets au fur et à mesure.
        """
        # Mettre à jour le sélecteur lui-même
        if hasattr(self, "_lang_widgets"):
            self._lang_widgets["label"].config(text=self._ui("lang_title"))
            self._lang_widgets["rb_fr"].config(text=self._ui("lang_fr"))
            self._lang_widgets["rb_en"].config(text=self._ui("lang_en"))

        # Onglets du notebook
        self.notebook.tab(self.annotation_tab, text=self._ui("tab_annotation"))
        self.notebook.tab(self.manager_tab, text=self._ui("tab_manager"))
        self.notebook.tab(self.stats_tab, text=self._ui("tab_stats"))

        # Boutons de l'onglet Annotation (si ils existent déjà)
        if hasattr(self, "btn_load_annotations"):
            self.btn_load_annotations.config(text=self._ui("btn_load_ann"))
        if hasattr(self, "btn_create_annotations"):
            self.btn_create_annotations.config(text=self._ui("btn_create_ann"))
        if hasattr(self, "btn_load_more_images"):
            self.btn_load_more_images.config(text=self._ui("btn_load_more"))
        if hasattr(self, "btn_open_manager"):
            self.btn_open_manager.config(text=self._ui("btn_manage_ann"))
        if hasattr(self, "btn_use_json_images"):
            self.btn_use_json_images.config(text=self._ui("btn_use_json_images"))

        if hasattr(self, "prev_button"):
            self.prev_button.config(text=self._ui("btn_prev"))
        if hasattr(self, "next_button"):
            self.next_button.config(text=self._ui("btn_next"))

        if hasattr(self, "browse_checkbutton"):
            self.browse_checkbutton.config(text=self._ui("chk_browse"))
        if hasattr(self, "only_annotated_checkbutton"):
            self.only_annotated_checkbutton.config(text=self._ui("chk_only_annotated"))

        if hasattr(self, "change_defaults_btn"):
            self.change_defaults_btn.config(text=self._ui("btn_change_defaults"))
        if hasattr(self, "change_save_path_btn"):
            self.change_save_path_btn.config(text=self._ui("btn_change_save"))

        if hasattr(self, "save_path_label") and \
                (self.annotation_file_path is None or self.annotation_file_path == "" or
                 self.save_path_label.cget("text").startswith("Chemin de sauvegarde") or
                 self.save_path_label.cget("text").startswith("Save path")):
            # Si aucun chemin défini ou texte par défaut, on remet le texte par défaut dans la bonne langue
            self.save_path_label.config(text=self._ui("label_save_path_none"))

    # Traductions
    def _t(self, key: str) -> str:
        FR = {
            "dist_for": "Répartition pour {attr}",
            "dist_pct_for": "Répartition (%) pour {attr}",
            "classes": "Classes",
            "num_images": "Nombre d'images",
            "no_data": "Pas de données",
            "global_title": "Analyse globale des attributs",
            "correlation_title": "Corrélation entre {a1} et {a2}",
            "entropy_weather": "Entropie Weather Type",
            "images_per_source": "Images par source",
            "sources": "Sources",
            "avg_intra_dist": "Écart moyen (en nombre d'images)",
            "avg_intra_title": "Distance moyenne intra-source (en nombre d'images)",
            "sample_summary": "Échantillon: {n} images | {ns} sources | Gini={g:.3f} | Entropie Weather Type={ew:.3f} | Moyenne des moyennes des écarts intra-source={m:.2f}",
            "save_fig": "Sauvegarder Graphique",
            "diversity_extra": "Jain={j:.3f} | Theil T={th:.3f} | HHI={hhi:.3f} | Simpson={simp:.3f} | Couverture sources={cov:.1f}% | IQR gaps={iqr:.2f} | CV counts={cv:.2f}"
        }
        EN = {
            "dist_for": "Distribution for {attr}",
            "dist_pct_for": "Distribution (%) for {attr}",
            "classes": "Classes",
            "num_images": "Number of images",
            "no_data": "No data",
            "global_title": "Global attribute analysis",
            "correlation_title": "Correlation between {a1} and {a2}",
            "entropy_weather": "Weather Type entropy",
            "images_per_source": "Images per source",
            "sources": "Sources",
            "avg_intra_dist": "Average gap (in number of images)",
            "avg_intra_title": "Average intra-source distance (in number of images)",
            "sample_summary": "Sample: {n} images | {ns} sources | Gini={g:.3f} | Weather Type entropy={ew:.3f} | Mean of means of intra-source gaps={m:.2f}",
            "save_fig": "Save Figure",
            "diversity_extra": "Jain={j:.3f} | Theil T={th:.3f} | HHI={hhi:.3f} | Simpson={simp:.3f} | Source coverage={cov:.1f}% | IQR gaps={iqr:.2f} | CV counts={cv:.2f}"
        }
        d = FR if self.stats_lang_var.get() == "FR" else EN
        return d.get(key, key)

    # ---------------------------------------------------------
    # 6) Fonctions d'analyse statistique
    # ---------------------------------------------------------
    def analyze_single_attribute(self):
        attribute = self.stats_attribute_var.get()
        freq, total = {}, 0
        for images in self.annotations.values():
            for ann in images.values():
                val = ann.get(attribute)
                if val is not None:
                    freq[val] = freq.get(val, 0) + 1
                    total += 1
        if total == 0:
            messagebox.showwarning("Avertissement", "Aucune donnée pour cette tâche.")
            return

        fig, (ax_bar, ax_pie) = plt.subplots(1, 2, figsize=(10, 4))
        ax_bar.bar(list(freq.keys()), list(freq.values()))
        ax_bar.set_title(self._t("dist_for").format(attr=attribute))
        ax_bar.set_xlabel(self._t("classes"))
        ax_bar.set_ylabel(self._t("num_images"))
        for label in ax_bar.get_xticklabels():
            label.set_rotation(30)
            label.set_horizontalalignment('right')

        ax_pie.pie(list(freq.values()), labels=list(freq.keys()), autopct='%1.1f%%', startangle=90)
        ax_pie.set_title(self._t("dist_pct_for").format(attr=attribute))
        plt.tight_layout()
        self.display_stats_figure(fig)

    def analyze_all_attributes(self):
        num_attrs = len(self.attributes)
        cols = 3
        rows = (num_attrs + cols - 1) // cols
        fig, axs = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows), constrained_layout=True)
        axs = axs.flatten()

        idx = -1
        for idx, attribute in enumerate(self.attributes.keys()):
            freq, total = {}, 0
            for images in self.annotations.values():
                for ann in images.values():
                    val = ann.get(attribute)
                    if val is not None:
                        freq[val] = freq.get(val, 0) + 1
                        total += 1
            ax = axs[idx]
            if total > 0:
                ax.bar(list(freq.keys()), list(freq.values()))
                ax.set_title(attribute, fontsize=10, pad=20)
                ax.set_xlabel(self._t("classes"), fontsize=8)
                ax.set_ylabel(self._t("num_images"), fontsize=8)
                ax.tick_params(axis='both', labelsize=8)
                for label in ax.get_xticklabels():
                    label.set_rotation(30)
                    label.set_horizontalalignment('right')
            else:
                ax.text(0.5, 0.5, self._t("no_data"), ha="center", va="center")

        for j in range(idx + 1, len(axs)):
            fig.delaxes(axs[j])

        self.display_stats_figure(fig)

    def analyze_correlation(self):
        attr1 = self.corr_attr1_var.get()
        attr2 = self.corr_attr2_var.get()
        table = {}

        for images in self.annotations.values():
            for ann in images.values():
                v1 = ann.get(attr1)
                v2 = ann.get(attr2)
                if v1 is None or v2 is None:
                    continue
                table.setdefault(v1, {})
                table[v1][v2] = table[v1].get(v2, 0) + 1

        if not table:
            messagebox.showwarning("Avertissement", "Pas de données pour la corrélation.")
            return

        v1_list = sorted(table.keys())
        v2_set = set()
        for d in table.values():
            v2_set.update(d.keys())
        v2_list = sorted(list(v2_set))

        matrix = []
        for v1 in v1_list:
            row = [table[v1].get(v2, 0) for v2 in v2_list]
            matrix.append(row)

        fig, ax = plt.subplots(figsize=(6, 4))
        cax = ax.imshow(matrix, cmap="viridis")
        ax.set_xticks(range(len(v2_list)))
        ax.set_xticklabels(v2_list)
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment('right')
        ax.set_yticks(range(len(v1_list)))
        ax.set_yticklabels(v1_list)
        ax.set_xlabel(attr2)
        ax.set_ylabel(attr1)
        ax.set_title(self._t("correlation_title").format(a1=attr1, a2=attr2))
        fig.colorbar(cax)
        plt.tight_layout()
        self.display_stats_figure(fig)

    def _timestamp_deltas_seconds(self, lst):
        """Retourne les deltas consécutifs en secondes (timestamps triés, >0)."""
        ts = [self._get_timestamp_s(a) for a in lst]
        ts = [t for t in ts if t > 0]
        ts.sort()
        deltas = []
        for i in range(len(ts) - 1):
            d = ts[i + 1] - ts[i]
            if d > 0:
                deltas.append(d)
        return deltas

    def _robust_base_interval_s(self, deltas, min_samples=6):
        """
        Estime l'intervalle nominal entre frames (en s) à partir des deltas.
        Robuste : on utilise le quantile bas/“petits deltas” puis la médiane.
        """
        if not deltas:
            return 0.0
        ds = sorted(deltas)
        n = len(ds)
        q40 = ds[max(0, int(0.40 * (n - 1)))]
        small = [d for d in ds if d <= q40]
        if len(small) >= min_samples:
            import statistics as _st
            return max(1e-6, _st.median(small))
        import statistics as _st
        return max(1e-6, _st.median(ds))

    def _build_frame_index_sequence(self, lst):
        """
        Version historique : si on trouve un index (frame_xxx), on le prend,
        sinon on incrémente (+1) pour conserver la continuité.
        """
        items = []
        for a in lst:
            idx = self._extract_frame_index(a)
            name = a.get('image_name', '') or ''
            items.append((idx, natural_sort_key(name), a))
        items.sort(key=lambda t: ((t[0] is None), (t[0] if t[0] is not None else float('inf')), t[1]))
        seq, last = [], None
        for idx, _, _ in items:
            if idx is None:
                cur = (last + 1) if last is not None else 0
            else:
                cur = idx
            seq.append(cur)
            last = cur
        return seq

    def _source_has_frame_indices(self, lst):
        """
        True si AU MOINS un index de frame est détecté dans la source.
        On force la logique historique dès qu'il y en a un (comme demandé).
        """
        for a in lst:
            if self._extract_frame_index(a) is not None:
                return True
        return False

    def analyze_sample_diversity(self):
        source = self.filtered_annotations if self.filtered_annotations else self.annotations
        if not source:
            messagebox.showwarning("Avertissement", "Aucune annotation (filtrée ou complète) n'est chargée.")
            return

        anns = [a for imgs in source.values() for a in imgs.values()]
        if not anns:
            messagebox.showwarning("Avertissement", "Échantillon vide.")
            return

        by_src = self._group_by_source(anns)

        src_ids, counts = [], []
        mean_dist_frames = []  # (barre du haut droite) : #images (frame ou est. via timestamps)
        mean_dist_seconds = []  # info complémentaire (hist bas droite)
        self._last_diversity_source_map = {}

        def build_frame_index_sequence(lst):
            """Logique d'origine : séquence monotone basée sur index de frame si dispo, sinon +1."""
            items = []
            for a in lst:
                idx = self._extract_frame_index(a)
                name = a.get('image_name', '') or ''
                items.append((idx, natural_sort_key(name), a))
            items.sort(key=lambda t: ((t[0] is None), (t[0] if t[0] is not None else float('inf')), t[1]))

            seq, last = [], None
            for idx, _, _ in items:
                if idx is None:
                    cur = (last + 1) if last is not None else 0
                else:
                    cur = idx
                seq.append(cur)
                last = cur
            return seq

        def timestamp_series(lst):
            """Timestamps triés et deltas (s) consécutifs positifs."""
            ts = [self._get_timestamp_s(a) for a in lst]
            ts = [t for t in ts if t > 0]
            ts.sort()
            deltas = []
            for i in range(len(ts) - 1):
                d = ts[i + 1] - ts[i]
                if d > 0:
                    deltas.append(d)
            return ts, deltas

        def robust_mean_dt(deltas):
            """Moyenne robuste de Δt : trimming 10–90% + cap via IQR (évite outliers)."""
            if not deltas:
                return None
            import numpy as np
            x = np.array(deltas, dtype=float)
            x.sort()
            # trimming quantiles (10%-90%)
            lo, hi = int(0.10 * len(x)), int(0.90 * len(x))
            x = x[lo:hi] if hi > lo else x
            if x.size == 0:
                return None
            # cap doux par IQR
            q1, q3 = np.percentile(x, [25, 75])
            iqr = q3 - q1
            low_cap, high_cap = max(0.0, q1 - 1.5 * iqr), q3 + 1.5 * iqr
            x = np.clip(x, low_cap, high_cap)
            m = float(np.mean(x))
            return m if m > 0 else None

        def has_frame_indices(lst, min_ratio=0.8):
            """Détecte si la source est majoritairement nommée avec index de frame."""
            idxs = [self._extract_frame_index(a) for a in lst]
            ok = sum(1 for v in idxs if v is not None)
            return (ok / max(1, len(lst))) >= min_ratio

        def has_timestamps(lst, min_ratio=0.8):
            ts = [self._get_timestamp_s(a) for a in lst]
            ok = sum(1 for t in ts if t > 0)
            return (ok / max(1, len(lst))) >= min_ratio

        for k, (s, lst) in enumerate(sorted(by_src.items(), key=lambda kv: kv[0])):
            if not lst:
                continue

            use_frames = has_frame_indices(lst, 0.7)  # tolérant
            use_ts = has_timestamps(lst, 0.7)

            # --- A) Valeur affichée en #images :
            if use_frames:
                # Logique historique (#images)
                seq = build_frame_index_sequence(lst)
                if len(seq) >= 2:
                    diffs = []
                    for i in range(len(seq) - 1):
                        d = seq[i + 1] - seq[i]
                        if d <= 0:
                            d = 1
                        elif d > 1000:
                            d = 1000
                        diffs.append(d)
                    md_frames = (sum(diffs) / len(diffs)) if diffs else 0.0
                else:
                    md_frames = 0.0

                # Seconds : informatif, si on a des timestamps
                _, dsecs = timestamp_series(lst)
                md_secs = (sum(dsecs) / len(dsecs)) if dsecs else 0.0

            elif use_ts:
                # Nouvelle logique : estimer #images via Δt / dt_mean_robuste
                ts, dsecs = timestamp_series(lst)
                md_secs = (sum(dsecs) / len(dsecs)) if dsecs else 0.0

                dt_mean = robust_mean_dt(dsecs)
                if dt_mean is None:
                    # fallback : seconds -> 0 et frames -> 0
                    md_frames = 0.0
                else:
                    est_gaps = []
                    for d in dsecs:
                        # estimation du gap en #images : round(Δt / dt_mean)
                        g = int(round(d / dt_mean))
                        if g < 1:   g = 1
                        if g > 1000: g = 1000
                        est_gaps.append(g)
                    md_frames = (sum(est_gaps) / len(est_gaps)) if est_gaps else 0.0
            else:
                # Ni frames ni timestamps fiables → neutre
                md_frames = 0.0
                md_secs = 0.0

            src_ids.append(f"Source {len(src_ids) + 1}")
            counts.append(len(lst))
            mean_dist_frames.append(md_frames)
            mean_dist_seconds.append(md_secs)
            self._last_diversity_source_map[src_ids[-1]] = s

        n_sources = len(src_ids)

        # Indices de diversité (inchangés)
        gini = gini_index(counts) if counts else 0.0
        ent_weather = 0.0
        if 'Weather Type' in self.attributes:
            from collections import Counter
            c = Counter(a.get('Weather Type', 'UNKNOWN') for a in anns)
            ent_weather = entropy_from_counts(list(c.values()))

        global_mean_frames = (sum(mean_dist_frames) / len(mean_dist_frames)) if mean_dist_frames else 0.0
        global_mean_seconds = (sum(mean_dist_seconds) / len(mean_dist_seconds)) if mean_dist_seconds else 0.0

        jain = jain_index(counts) if counts else 1.0
        th = theil_T(counts) if counts else 0.0
        h = hhi(counts) if counts else 0.0
        simp = simpson_diversity(counts) if counts else 0.0
        coverage = (100.0 * sum(1 for x in counts if x > 0) / max(1, n_sources))

        import statistics as _st, math as _m, matplotlib.pyplot as plt
        iqr = 0.0
        if len(mean_dist_frames) >= 4:
            q1 = _st.quantiles(mean_dist_frames, n=4)[0]
            q3 = _st.quantiles(mean_dist_frames, n=4)[2]
            iqr = max(0.0, q3 - q1)
        cv = 0.0
        if len(counts) >= 2 and sum(counts) > 0:
            m = (sum(counts) / len(counts))
            if m > 0:
                cv = _st.pstdev(counts) / m

        # ----- Graphiques 2x2
        fig = plt.figure(figsize=(12, 6.6))
        gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.6], width_ratios=[1, 1])

        ax_src = fig.add_subplot(gs[0, 0])
        ax_src.bar(range(n_sources), counts)
        ax_src.set_title(self._t("images_per_source"))
        ax_src.set_ylabel(self._t("num_images"))
        ax_src.set_xlabel(self._t("sources"))
        ax_src.set_xticks(range(n_sources))
        ax_src.set_xticklabels(src_ids, rotation=60)
        for lbl in ax_src.get_xticklabels():
            lbl.set_horizontalalignment('right')

        ax_dist_frames = fig.add_subplot(gs[0, 1])
        ax_dist_frames.bar(range(n_sources), mean_dist_frames)
        ax_dist_frames.set_title(
            "Distance moyenne intra-source (en nombre d'images)" if self.stats_lang_var.get() == "FR"
            else "Average intra-source distance (in #images)")
        ax_dist_frames.set_ylabel("Écart moyen (#images)" if self.stats_lang_var.get() == "FR"
                                  else "Mean gap (#images)")
        ax_dist_frames.set_xlabel(self._t("sources"))
        ax_dist_frames.set_xticks(range(n_sources))
        ax_dist_frames.set_xticklabels(src_ids, rotation=60)
        for lbl in ax_dist_frames.get_xticklabels():
            lbl.set_horizontalalignment('right')

        ax_h1 = fig.add_subplot(gs[1, 0])
        ax_h1.hist(counts, bins=min(20, max(5, int(_m.sqrt(max(1, len(counts)))))), density=False)
        ax_h1.set_title("Distribution des comptes/source" if self.stats_lang_var.get() == "FR"
                        else "Counts per source distribution")
        ax_h1.set_xlabel(self._t("num_images"))
        ax_h1.set_ylabel("Fréquence" if self.stats_lang_var.get() == "FR" else "Frequency")

        ax_h2 = fig.add_subplot(gs[1, 1])
        ax_h2.hist(mean_dist_seconds, bins=min(20, max(5, int(_m.sqrt(max(1, len(mean_dist_seconds)))))), density=False)
        ax_h2.set_title("Distribution des écarts moyens (secondes)" if self.stats_lang_var.get() == "FR"
                        else "Mean gaps distribution (seconds)")
        ax_h2.set_xlabel("Écart moyen (secondes)" if self.stats_lang_var.get() == "FR"
                         else "Mean gap (seconds)")
        ax_h2.set_ylabel("Fréquence" if self.stats_lang_var.get() == "FR" else "Frequency")

        fig.suptitle(
            self._t("sample_summary").format(
                n=len(anns), ns=n_sources, g=gini, ew=ent_weather, m=global_mean_frames
            )
            + (f"  |  Mean of means (seconds)={global_mean_seconds:.3f}s")
            + "\n" + self._t("diversity_extra").format(
                j=jain, th=th, hhi=h, simp=simp, cov=coverage, iqr=iqr, cv=cv
            ),
            y=0.98
        )
        plt.tight_layout()
        self.display_stats_figure(fig)

    def display_stats_figure(self, fig):
        for widget in self.stats_canvas_frame.winfo_children():
            widget.destroy()

        scrollable = SafeScrollableFrame(self.stats_canvas_frame, orient="vertical")
        scrollable.pack(fill="both", expand=True)
        frame = scrollable.inner

        fig_canvas = FigureCanvasTkAgg(fig, master=frame)
        fig_canvas.draw()
        fig_canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar = NavigationToolbar2Tk(fig_canvas, frame)
        toolbar.update()

        tk.Button(frame, text=self._t("save_fig"), command=lambda: self.save_figure(fig)).pack(pady=5)

    def save_figure(self, fig):
        file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("PNG files", "*.png"), ("All Files", "*.*")],
                                                 title="Enregistrer le graphique")
        if file_path:
            fig.savefig(file_path, bbox_inches='tight')
            messagebox.showinfo("Succès", f"Graphique sauvegardé sous {file_path}")

    # ---------------------------------------------------------
    # 7) Navigation & affichage
    # ---------------------------------------------------------
    def update_interface(self, load_saved_annotations=True):
        # Si aucune image active mais des annotations existent -> charger automatiquement les images résolues du JSON
        active_images = self._get_active_images()
        if not active_images and self.annotations:
            self._rebuild_annotated_image_list()
            if self.annotated_image_paths:
                # Utiliser les images du JSON résolu pour l'onglet Annotation
                self.images = list(self.annotated_image_paths)
                self.current_index = 0
                # Si l'utilisateur veut strictement "uniquement annotées", la checkbox fera le même résultat
                # mais ici on force l'affichage correct.
                active_images = self._get_active_images()

        if not active_images:
            messagebox.showinfo("Information", "Aucune image à afficher dans le mode actuel.")
            return

        if self.current_index >= len(active_images):
            self.current_index = max(0, len(active_images) - 1)

        img_path = active_images[self.current_index]
        if not os.path.exists(img_path):
            messagebox.showerror("Erreur", f"Le fichier n'existe pas : {img_path}")
            return

        try:
            if self._last_image_path != img_path:
                self.original_image = Image.open(img_path).convert("RGB")
                try:
                    self.original_image.load()
                except Exception:
                    pass
                self._last_image_path = img_path
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'ouvrir l'image {img_path} : {e}")
            return

        self.display_image()

        remaining = len(active_images) - self.current_index - 1
        self.remaining_label.config(text=f"Images restantes: {remaining}")

        img_name = os.path.basename(img_path)
        folder_name = os.path.basename(os.path.dirname(img_path))
        if load_saved_annotations and folder_name in self.annotations and img_name in self.annotations[folder_name]:
            annotation = self.annotations[folder_name][img_name]
            for attribute, var in self.annotation_vars.items():
                selected_option = annotation.get(attribute, None)
                if selected_option:
                    var.set(selected_option)
                else:
                    var.set(self.default_values.get(attribute, self.attributes[attribute][0]))
        else:
            for attribute, var in self.annotation_vars.items():
                var.set(self.default_values.get(attribute, self.attributes[attribute][0]))

    def display_image(self):
        if self._rendering_image:
            return
        self._rendering_image = True
        try:
            self.root.update_idletasks()
            # Valeurs par défaut raisonnables si le Label n'est pas encore dimensionné
            frame_width = max(200, self.image_label.winfo_width() or 800)
            frame_height = max(150, self.image_label.winfo_height() or 600)

            # Toujours re-rendre si nouvelle image ; sinon, éviter de rerendre au même size
            if self._last_render_size == (frame_width, frame_height) and self._last_image_path:
                pass  # on peut rerendre quand même pour être sûr de coller à la nouvelle image
            self._last_render_size = (frame_width, frame_height)

            img = self.original_image
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            img = img.copy()
            img.thumbnail((frame_width, frame_height), resample=Image.BILINEAR)

            self.img_tk = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.img_tk)

        except Exception as e:
            print(f"[display_image] erreur: {e}")
        finally:
            self._rendering_image = False

    def _display_image_safe(self):
        self._resize_job = None
        if not hasattr(self, 'original_image'):
            return
        self.display_image()

    def on_window_resize(self, event):
        try:
            if self._resize_job is not None:
                self.root.after_cancel(self._resize_job)
        except Exception:
            pass
        self._resize_job = self.root.after(60, self._display_image_safe)

    def on_left_arrow(self, event):
        self.prev_image()

    def on_right_arrow(self, event):
        self.next_image()

    # ---------------------------------------------------------
    # 8) Split / Export / etc.
    # ---------------------------------------------------------
    def split_train_test(self):
        if not self.annotations:
            messagebox.showerror("Erreur", "Aucune annotation chargée.")
            return

        source = [ann for imgs in (self.filtered_annotations or self.annotations).values() for ann in imgs.values()]
        if not source:
            messagebox.showerror("Erreur", "Aucune annotation disponible pour le split.")
            return

        rng = random.Random(42)

        # ==============================
        # MODE EXACT — SOURCES DISJOINTES
        # ==============================
        if self.exact_mode_var.get():
            by_src_all = self._group_by_source(source)
            total_available = sum(len(v) for v in by_src_all.values())
            if total_available == 0:
                messagebox.showerror("Erreur", "Aucune image disponible.")
                return

            n_train = max(0, int(self.train_exact_n_var.get() or 0))
            n_test  = max(0, int(self.test_exact_n_var.get() or 0))
            if n_train == 0 and n_test == 0:
                n_test = max(1, int(round(0.2 * total_available)))
                n_train = max(1, total_available - n_test)
            elif n_train == 0:
                n_train = max(0, total_available - n_test)
            elif n_test == 0:
                n_test = max(0, total_available - n_train)

            if n_train < 0 or n_test < 0 or (n_train + n_test) > total_available:
                messagebox.showerror("Erreur", f"N train ({n_train}) + N test ({n_test}) dépasse le total disponible ({total_available}).")
                return

            sizes = {s: len(v) for s, v in by_src_all.items()}
            train_sources, test_sources = self._partition_sources_by_targets(sizes, n_train, n_test)

            cap_train = sum(sizes[s] for s in train_sources)
            cap_test  = sum(sizes[s] for s in test_sources)
            if cap_train < n_train or cap_test < n_test:
                train_sources, test_sources = self._rebalance_sources_greedily(sizes, train_sources, test_sources, n_train, n_test)
                cap_train = sum(sizes[s] for s in train_sources)
                cap_test  = sum(sizes[s] for s in test_sources)
                if cap_train < n_train or cap_test < n_test:
                    messagebox.showerror("Erreur", f"Capacité insuffisante après rééquilibrage (train {cap_train}/{n_train}, test {cap_test}/{n_test}).")
                    return

            min_frac = max(0.0, min(100.0, float(self.min_pct_per_source_var.get()))) / 100.0
            max_frac = max(0.0, min(100.0, float(self.max_pct_per_source_var.get()))) / 100.0
            max_frac = max(max_frac, 1.0/ max(1, len(train_sources)))

            train_sizes = {s: sizes[s] for s in train_sources}
            test_sizes  = {s: sizes[s] for s in test_sources}
            train_quota = fair_quotas(train_sizes, n_train, min_frac=min_frac, max_frac=max_frac)
            test_quota  = fair_quotas(test_sizes,  n_test,  min_frac=min_frac, max_frac=max_frac)

            def draw_from_sources(src_list, quota_map):
                picked = []
                if not self.soft_equal_sampling_var.get():
                    for s in src_list:
                        k = quota_map[s]
                        if k > 0:
                            items = list(by_src_all[s])
                            rng.shuffle(items)
                            picked.extend(items[:k])
                    return picked
                by_src_limited = {}
                for s in src_list:
                    items = list(by_src_all[s])
                    rng.shuffle(items)
                    by_src_limited[s] = items[:quota_map[s]*2 + 32]
                target = sum(quota_map.values())
                picked = efraimidis_spirakis_pick(by_src_limited, target, rng)
                if len(picked) > target:
                    picked = picked[:target]
                elif len(picked) < target:
                    rest = []
                    for s in src_list:
                        rest.extend(by_src_all[s])
                    rng.shuffle(rest)
                    need = target - len(picked)
                    for a in rest:
                        if a not in picked:
                            picked.append(a)
                            need -= 1
                            if need == 0: break
                return picked

            train_list = draw_from_sources(train_sources, train_quota)
            test_list  = draw_from_sources(test_sources,  test_quota)

            if len(train_list) != n_train or len(test_list) != n_test:
                messagebox.showwarning("Avertissement",
                                       f"Taille finale inattendue: train={len(train_list)} (demande {n_train}), test={len(test_list)} (demande {n_test}).")

            self._save_train_test_lists(train_list, test_list, disjoint_ok=True)
            return

        # ==============================
        # MODE EXACT — SOURCES PARTAGÉES (sans répétition d’images)
        # ==============================
        if self.exact_shared_mode_var.get():
            by_src_all = self._group_by_source(source)
            sizes = {s: len(v) for s, v in by_src_all.items()}
            total_available = sum(sizes.values())
            if total_available == 0:
                messagebox.showerror("Erreur", "Aucune image disponible.")
                return

            n_train = max(0, int(self.train_exact_n_var.get() or 0))
            n_test  = max(0, int(self.test_exact_n_var.get() or 0))
            if n_train == 0 and n_test == 0:
                n_test = max(1, int(round(0.2 * total_available)))
                n_train = max(1, total_available - n_test)
            elif n_train == 0:
                n_train = max(0, total_available - n_test)
            elif n_test == 0:
                n_test = max(0, total_available - n_train)

            if n_train < 0 or n_test < 0 or (n_train + n_test) > total_available:
                messagebox.showerror("Erreur", f"N train ({n_train}) + N test ({n_test}) dépasse le total disponible ({total_available}).")
                return

            min_frac = max(0.0, min(100.0, float(self.min_pct_per_source_var.get()))) / 100.0
            max_frac = max(0.0, min(100.0, float(self.max_pct_per_source_var.get()))) / 100.0
            N_total = n_train + n_test

            combined_quota = fair_quotas(sizes, N_total, min_frac=min_frac, max_frac=max_frac)

            ratio = n_train / N_total if N_total > 0 else 0.5
            train_quota = {}
            frac_parts = []
            for s in combined_quota:
                raw = combined_quota[s] * ratio
                floor_val = int(math.floor(raw))
                train_quota[s] = floor_val
                frac_parts.append((raw - floor_val, s))
            cur_train = sum(train_quota.values())
            need = n_train - cur_train
            if need > 0:
                frac_parts.sort(reverse=True, key=lambda t: t[0])
                for _, s in frac_parts:
                    if need == 0:
                        break
                    if train_quota[s] < combined_quota[s]:
                        train_quota[s] += 1
                        need -= 1
            elif need < 0:
                frac_parts.sort(key=lambda t: t[0])
                for _, s in frac_parts:
                    if need == 0:
                        break
                    if train_quota[s] > 0:
                        train_quota[s] -= 1
                        need += 1

            test_quota = {s: combined_quota[s] - train_quota[s] for s in combined_quota}

            train_list, test_list = [], []
            rng = random.Random(42)
            for s, items in by_src_all.items():
                lst = list(items)
                rng.shuffle(lst)
                k_tr = max(0, min(train_quota.get(s, 0), len(lst)))
                tr = lst[:k_tr]
                remaining = lst[k_tr:]
                k_te = max(0, min(test_quota.get(s, 0), len(remaining)))
                te = remaining[:k_te]
                train_list.extend(tr)
                test_list.extend(te)

            if len(train_list) < n_train or len(test_list) < n_test:
                used = set((id(a) for a in train_list)) | set((id(a) for a in test_list))
                leftovers = []
                for s, items in by_src_all.items():
                    for a in items:
                        if id(a) not in used:
                            leftovers.append(a)
                rng.shuffle(leftovers)

                need_tr = n_train - len(train_list)
                need_te = n_test  - len(test_list)
                if need_tr > 0:
                    add = leftovers[:max(0, need_tr)]
                    train_list.extend(add)
                    leftovers = leftovers[max(0, need_tr):]
                if need_te > 0:
                    add = leftovers[:max(0, need_te)]
                    test_list.extend(add)
                    leftovers = leftovers[max(0, need_te):]

            if len(train_list) != n_train or len(test_list) != n_test:
                messagebox.showwarning(
                    "Avertissement",
                    f"Taille finale inattendue: train={len(train_list)} (demande {n_train}), "
                    f"test={len(test_list)} (demande {n_test}). Ajustements appliqués."
                )

            self._save_train_test_lists(train_list, test_list, disjoint_ok=False)
            return

        # ==============================
        # MODE NON EXACT
        # ==============================
        pct = simpledialog.askfloat("Taille du test (%)",
                                    "Pourcentage test (ex: 20 pour 20%). Laisser vide ou Annuler pour 20%.",
                                    minvalue=1.0, maxvalue=90.0)
        test_ratio = (pct / 100.0) if pct else 0.2

        train_cap = simpledialog.askinteger("Taille max train (optionnel)",
                                            "Nombre max d'images train (laisser vide = auto)", minvalue=1)
        test_cap = simpledialog.askinteger("Taille max test (optionnel)",
                                           "Nombre max d'images test (laisser vide = auto)", minvalue=1)

        strat_task = self.stratify_task_var.get()
        if strat_task == "(aucune)":
            strat_task = None

        by_src_all = self._group_by_source(source)

        prepared_by_src = {}
        for s, lst in by_src_all.items():
            prepared_by_src[s] = self._ensure_diversity_per_source(
                lst,
                gap_mode=self.gap_mode_var.get(),
                min_gap_s=float(self.min_time_gap_var.get()),
                min_gap_frames=int(self.min_frame_gap_var.get())
            )

        total_after = sum(len(v) for v in prepared_by_src.values())
        if total_after == 0:
            messagebox.showerror("Erreur", "Aucune image après préparation (thinning/filtrage).")
            return

        test_target = min(test_cap or math.inf, max(1, int(round(total_after * test_ratio))))
        train_target = min(train_cap or math.inf, max(1, total_after - test_target))
        max_pct = max(5.0, min(100.0, float(self.max_pct_per_source_var.get()))) / 100.0
        min_pct = max(0.0, min(100.0, float(self.min_pct_per_source_var.get()))) / 100.0

        sources = list(prepared_by_src.keys())
        rng = random.Random(42)
        rng.shuffle(sources)

        test_src = []
        size_est = 0
        for s in sorted(sources, key=lambda x: len(prepared_by_src[x]), reverse=True):
            if size_est >= test_target: break
            if len(prepared_by_src[s]) == 0: continue
            test_src.append(s)
            size_est += len(prepared_by_src[s])
        test_src_set = set(test_src)
        train_src = [s for s in sources if s not in test_src_set]

        test_by_src = {s: prepared_by_src[s] for s in test_src}
        train_by_src = {s: prepared_by_src[s] for s in train_src}

        if self.soft_equal_sampling_var.get():
            test_list  = efraimidis_spirakis_pick(test_by_src,  test_target, rng)
            train_list = efraimidis_spirakis_pick(train_by_src, train_target, rng)
        else:
            test_list  = self._interleave_round_robin(test_by_src,  test_target, max_pct)
            train_list = self._interleave_round_robin(train_by_src, train_target, max_pct)

        def max_share_ok(lst, target):
            if target <= 0:
                return True
            per_src = defaultdict(int)
            for a in lst:
                per_src[self._extract_source(a)] += 1
            cap_max = target if max_pct <= 0 else max(1, int(math.floor(target * max_pct)))
            cap_min = 0 if min_pct <= 0 else int(math.floor(target * min_pct))
            ok_max = all(cnt <= cap_max for cnt in per_src.values())
            ok_min = True if cap_min == 0 else all(cnt >= cap_min for cnt in per_src.values())
            return ok_max and ok_min

        leaked = any(self._extract_source(a) in test_src_set for a in train_list)
        warn_lines = []
        if leaked:
            warn_lines.append("⚠️ Fuite de source possible (train/test partagent un dossier).")
        if not max_share_ok(train_list, len(train_list)):
            warn_lines.append(f"⚠️ Train: au moins une source hors bornes min/max.")
        if not max_share_ok(test_list, len(test_list)):
            warn_lines.append(f"⚠️ Test: au moins une source hors bornes min/max.")

        self._save_train_test_lists(train_list, test_list, disjoint_ok=(not leaked), extra_warn=warn_lines)

    # --------- Sauvegarde train/test ----------
    def _save_train_test_lists(self, train_list, test_list, disjoint_ok=True, extra_warn=None):
        def by_folder(items):
            out = {}
            for ann in items:
                out.setdefault(ann['folder'], {})[ann['image_name']] = ann
            return out

        save_dir = filedialog.askdirectory(title="Sélectionnez le répertoire de sauvegarde (train/test)")
        if not save_dir:
            return

        def atomic_write_json(path, data):
            import tempfile
            dir_ = os.path.dirname(path) or '.'
            with tempfile.NamedTemporaryFile('w', dir=dir_, delete=False) as tf:
                json.dump(data, tf, indent=4)
                tmp = tf.name
            os.replace(tmp, path)

        train_path = os.path.join(save_dir, "train.json")
        test_path = os.path.join(save_dir, "test.json")
        try:
            atomic_write_json(train_path, by_folder(train_list))
            atomic_write_json(test_path, by_folder(test_list))
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de générer les fichiers : {e}")
            return

        n_src_train = len({self._extract_source(a) for a in train_list})
        n_src_test = len({self._extract_source(a) for a in test_list})
        total_after = len(train_list) + len(test_list)

        msg = [
            "✅ Split terminé" + (" (sources TRAIN/TEST disjointes)" if disjoint_ok else " (sources partagées — sans doublon d’images)"),
            f"Total: {total_after} | Train={len(train_list)} ({n_src_train} sources) | Test={len(test_list)} ({n_src_test} sources)",
            f"Fichiers:\n- Train: {train_path}\n- Test:  {test_path}"
        ]
        if extra_warn:
            msg.append("\nDiagnostics:")
            msg.extend(extra_warn)
        messagebox.showinfo("Succès", "\n".join(msg))

    # --------- Partition et rééquilibrage (mode exact disjoint) ----------
    def _partition_sources_by_targets(self, sizes: dict, train_target: int, test_target: int):
        train_sources, test_sources = [], []
        sum_train = 0
        sum_test = 0
        targets = {'train': max(1, train_target), 'test': max(1, test_target)}
        for s, sz in sorted(sizes.items(), key=lambda kv: kv[1], reverse=True):
            need_train = targets['train'] - sum_train
            need_test  = targets['test'] - sum_test
            if need_train >= need_test:
                train_sources.append(s)
                sum_train += sz
            else:
                test_sources.append(s)
                sum_test += sz
        return train_sources, test_sources

    def _rebalance_sources_greedily(self, sizes: dict, train_sources: list, test_sources: list, n_train: int, n_test: int):
        sum_train = sum(sizes[s] for s in train_sources)
        sum_test  = sum(sizes[s] for s in test_sources)
        need_train = n_train - sum_train
        need_test  = n_test - sum_test
        if need_train > 0 and test_sources:
            s_move = max(test_sources, key=lambda s: sizes[s])
            test_sources.remove(s_move)
            train_sources.append(s_move)
        elif need_test > 0 and train_sources:
            s_move = max(train_sources, key=lambda s: sizes[s])
            train_sources.remove(s_move)
            test_sources.append(s_move)
        return train_sources, test_sources

    def copy_annotated_images(self):
        if not self.annotations:
            messagebox.showerror("Erreur", "Aucune annotation chargée.")
            return
        destination_folder = filedialog.askdirectory(title="Sélectionnez le répertoire de destination")
        if not destination_folder:
            return

        new_annotations = {}
        for folder, images in self.annotations.items():
            for image_name, annotation in images.items():
                # Résoudre le chemin actuel
                src = self._resolve_image_path(folder, image_name, annotation)
                if not (src and os.path.exists(src)):
                    messagebox.showwarning("Attention", f"L'image {annotation.get('image_path', image_name)} n'existe pas. Ignorée.")
                    continue
                _, ext = os.path.splitext(image_name)
                if not ext:
                    ext = '.jpg'
                new_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}{ext}"
                new_path = os.path.join(destination_folder, new_name)
                try:
                    shutil.copy(src, new_path)
                except Exception as e:
                    messagebox.showerror("Erreur", f"Impossible de copier {src} vers {new_path} : {e}")
                    continue

                updated_annotation = annotation.copy()
                updated_annotation['image_path'] = new_path
                updated_annotation['image_name'] = new_name
                new_annotations.setdefault(folder, {})[new_name] = updated_annotation

        if not new_annotations:
            messagebox.showinfo("Information", "Aucune image copiée.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json")],
                                                 title="Enregistrer le nouveau fichier d'annotations")
        if save_path:
            try:
                with open(save_path, 'w') as f:
                    json.dump(new_annotations, f, indent=4)
                messagebox.showinfo("Succès", f"Fichier JSON exporté à {save_path}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'exporter : {e}")
        else:
            messagebox.showwarning("Attention", "Aucun chemin de sauvegarde spécifié.")

    # ---------------------------------------------------------
    # 9) Fermeture de l'application
    # ---------------------------------------------------------
    def on_closing(self):
        if messagebox.askokcancel("Quitter", "Voulez-vous quitter ? Les annotations seront sauvegardées."):
            self.save_annotations_to_file()
            self.root.destroy()

    # ---------------------------------------------------------
    # Chargement & création d’annotations (onglet Annotation)
    # ---------------------------------------------------------
    def load_annotations(self):
        self.annotation_file_path = filedialog.askopenfilename(defaultextension=".json",
                                                               filetypes=[("JSON files", "*.json")],
                                                               title="Sélectionnez un fichier d'annotations")
        if not self.annotation_file_path:
            messagebox.showwarning("Attention", "Aucun fichier d'annotations n'a été sélectionné.")
            return

        if os.path.exists(self.annotation_file_path):
            with open(self.annotation_file_path, 'r') as f:
                data = json.load(f)

            # Accepter JSON plat (liste) ou imbriqué (par dossier)
            if isinstance(data, list):
                anns = {}
                for ann in data:
                    folder = ann.get('folder') or 'unknown'
                    name = ann.get('image_name') or os.path.basename(ann.get('image_path', 'image.jpg'))
                    ann['image_name'] = name
                    ann['folder'] = folder
                    anns.setdefault(folder, {})[name] = ann
                self.annotations = anns
            elif isinstance(data, dict):
                self.annotations = data
            else:
                messagebox.showerror("Erreur", "Format JSON non supporté.")
                return

            # Détection : s'il y a beaucoup de chemins introuvables, proposer une racine
            total = sum(len(v) for v in self.annotations.values())
            unresolved = 0
            for folder, imgs in self.annotations.items():
                for name, ann in imgs.items():
                    if not self._resolve_image_path(folder, name, ann):
                        unresolved += 1

            if unresolved > 0 and messagebox.askyesno("Chemins à résoudre",
                                                      f"{unresolved}/{total} images introuvables.\n"
                                                      f"Voulez-vous choisir une racine d'images pour résoudre les chemins ?"):
                root = filedialog.askdirectory(title="Choisissez la racine d'images correspondant au JSON")
                if root:
                    self.annotations_images_root = root

            self._rebuild_annotated_image_list()

            # Si aucune image dossier n'a été chargée, basculer automatiquement sur les images du JSON résolu
            if not self.images and self.annotated_image_paths:
                self.images = list(self.annotated_image_paths)
                self.current_index = 0
                # Optionnel : activer la case "uniquement annotées"
                self.only_annotated_var.set(True)

            # Si des images existent, se placer sur la première non annotée
            if self.images:
                active = self._get_active_images()
                for i, img_path in enumerate(active):
                    folder = os.path.basename(os.path.dirname(img_path))
                    img_name = os.path.basename(img_path)
                    if not (folder in self.annotations and img_name in self.annotations[folder]):
                        self.current_index = i
                        break
                else:
                    self.current_index = 0

            self.save_path_label.config(text=f"Chemin de sauvegarde: {self.annotation_file_path}")
            self.enable_annotation_widgets()
            self.update_interface(load_saved_annotations=True)
        else:
            messagebox.showerror("Erreur", "Le fichier d'annotations sélectionné n'existe pas.")

    def create_new_annotations(self):
        self.annotation_file_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                                 filetypes=[("JSON files", "*.json")],
                                                                 title="Créer un nouveau fichier d'annotations")
        if not self.annotation_file_path:
            messagebox.showwarning("Attention", "Aucun chemin de sauvegarde n'a été spécifié.")
            return
        self.annotations = {}
        self.annotated_image_paths = []
        self.current_index = 0
        self.save_path_label.config(text=f"Chemin de sauvegarde: {self.annotation_file_path}")
        self.enable_annotation_widgets()
        self.update_interface()

    def load_additional_images(self):
        directory = filedialog.askdirectory(title="Sélectionnez le répertoire des images supplémentaires")
        if not directory:
            return
        if not self.initial_images_root:
            self.initial_images_root = directory
        folder_name = os.path.basename(directory)
        new_images = []
        for root_dir, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(_IMG_EXTS):
                    img_path = os.path.join(root_dir, file)
                    if img_path not in self.images:
                        new_images.append(img_path)
                        self.image_folders.setdefault(folder_name, []).append(file)
        if new_images:
            new_images.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
            self.images.extend(new_images)
            self.image_folders[folder_name].sort(key=natural_sort_key)
            self.current_index = self.images.index(new_images[0])
            messagebox.showinfo("Succès", f"{len(new_images)} images supplémentaires ont été chargées.")
            self.update_interface()
        else:
            messagebox.showinfo("Information", "Aucune nouvelle image trouvée.")

    # ---------------------------------------------------------
    # Sauvegarde annotations
    # ---------------------------------------------------------
    def save_annotation(self):
        active_images = self._get_active_images()
        if self.current_index >= len(active_images):
            return True
        if getattr(self, 'browse_mode_var', None) and self.browse_mode_var.get():
            return True

        img_path = active_images[self.current_index]
        img_name = os.path.basename(img_path)
        folder_name = os.path.basename(os.path.dirname(img_path))

        annotation = {
            "image_name": img_name,
            "image_path": img_path,
            "folder": folder_name,
            "id": self.current_index
        }
        for attribute, var in self.annotation_vars.items():
            value = var.get()
            if not value:
                messagebox.showerror("Erreur", f"Veuillez sélectionner une valeur pour '{attribute}'.")
                return False
            annotation[attribute] = value
            self.default_values[attribute] = value

        self.annotations.setdefault(folder_name, {})[img_name] = annotation
        self.save_annotations_to_file()

        if self.only_annotated_var.get():
            if img_path not in self.annotated_image_paths:
                self.annotated_image_paths.append(img_path)

        return True

    def save_default_annotation(self):
        active_images = self._get_active_images()
        if self.current_index >= len(active_images):
            return
        if getattr(self, 'browse_mode_var', None) and self.browse_mode_var.get():
            return

        img_path = active_images[self.current_index]
        img_name = os.path.basename(img_path)
        folder_name = os.path.basename(os.path.dirname(img_path))

        annotation = {
            "image_name": img_name,
            "image_path": img_path,
            "folder": folder_name,
            "id": self.current_index
        }
        for attribute, options in self.attributes.items():
            annotation[attribute] = self.default_values.get(attribute, options[0])

        self.annotations.setdefault(folder_name, {})[img_name] = annotation
        self.save_annotations_to_file()

        if self.only_annotated_var.get() and img_path not in self.annotated_image_paths:
            self.annotated_image_paths.append(img_path)

    def change_save_path(self):
        new_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                filetypes=[("JSON files", "*.json")],
                                                title="Enregistrer le fichier d'annotations")
        if new_path:
            self.annotation_file_path = new_path
            self.save_path_label.config(text=f"Chemin de sauvegarde: {self.annotation_file_path}")
            self.save_annotations_to_file()
        else:
            messagebox.showwarning("Attention", "Aucun chemin de sauvegarde spécifié.")

    def save_annotations_to_file(self):
        if self.annotation_file_path:
            try:
                with open(self.annotation_file_path, 'w') as f:
                    json.dump(self.annotations, f, indent=4)
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de sauvegarder les annotations : {e}")

    # ---------------------------------------------------------
    # Navigation
    # ---------------------------------------------------------
    def prev_image(self):
        active_images = self._get_active_images()
        if not active_images:
            return
        if self.current_index <= 0:
            messagebox.showinfo("Information", "Vous êtes déjà à la première image.")
            return

        if getattr(self, 'browse_mode_var', None) and self.browse_mode_var.get():
            self.current_index -= 1
            self.update_interface(load_saved_annotations=True)
            return

        img_path = active_images[self.current_index]
        img_name = os.path.basename(img_path)
        folder_name = os.path.basename(os.path.dirname(img_path))
        if folder_name in self.annotations and img_name in self.annotations[folder_name]:
            del self.annotations[folder_name][img_name]
            self.save_annotations_to_file()
            if self.only_annotated_var.get() and img_path in self.annotated_image_paths:
                self.annotated_image_paths.remove(img_path)

        self.current_index -= 1
        self.update_interface(load_saved_annotations=False)
        self.save_default_annotation()

    def next_image(self):
        active_images = self._get_active_images()
        if not active_images:
            return

        if getattr(self, 'browse_mode_var', None) and self.browse_mode_var.get():
            if self.current_index < len(active_images) - 1:
                self.current_index += 1
            self.update_interface(load_saved_annotations=True)
            return

        success = self.save_annotation()
        if not success:
            return
        if self.current_index < len(active_images) - 1:
            self.current_index += 1
            self.update_interface()
        else:
            messagebox.showinfo("Information", "Toutes les images ont été parcourues dans le mode actuel.")
            self.update_interface()

    # ---------------------------------------------------------
    # Manager: navigation/affichage liste
    # ---------------------------------------------------------
    def open_annotation_manager(self):
        self.notebook.select(self.manager_tab)

    def load_annotations_manager(self):
        annotation_file = filedialog.askopenfilename(defaultextension=".json",
                                                     filetypes=[("JSON files", "*.json")],
                                                     title="Sélectionnez le fichier d'annotations")
        if not annotation_file:
            messagebox.showwarning("Attention", "Aucun fichier d'annotations sélectionné.")
            return

        if os.path.exists(annotation_file):
            with open(annotation_file, 'r') as f:
                data = json.load(f)

            if isinstance(data, list):
                anns = {}
                for ann in data:
                    folder = ann.get('folder') or 'unknown'
                    name = ann.get('image_name') or os.path.basename(ann.get('image_path', 'image.jpg'))
                    ann['image_name'] = name
                    ann['folder'] = folder
                    anns.setdefault(folder, {})[name] = ann
                self.annotations = anns
            elif isinstance(data, dict):
                self.annotations = data
            else:
                messagebox.showerror("Erreur", "Format JSON non supporté.")
                return

            # Résoudre les chemins introuvables (option racine)
            total = sum(len(v) for v in self.annotations.values())
            unresolved = 0
            for folder, imgs in self.annotations.items():
                for name, ann in imgs.items():
                    if not self._resolve_image_path(folder, name, ann):
                        unresolved += 1
            if unresolved > 0 and messagebox.askyesno("Chemins à résoudre",
                                                      f"{unresolved}/{total} images introuvables.\n"
                                                      f"Choisir une racine d'images ?"):
                root = filedialog.askdirectory(title="Choisissez la racine d'images correspondant au JSON")
                if root:
                    self.annotations_images_root = root

            self._rebuild_annotated_image_list()
            messagebox.showinfo("Succès", f"Annotations chargées depuis {annotation_file}")
            self.populate_annotations_listbox()
        else:
            messagebox.showerror("Erreur", "Le fichier sélectionné n'existe pas.")

    def populate_annotations_listbox(self):
        self.annotations_listbox.delete(0, tk.END)
        for folder in sorted(self.annotations.keys()):
            images = self.annotations[folder]
            for image_name in sorted(images.keys(), key=natural_sort_key):
                annotation = images[image_name]
                display_text = f"{folder}/{image_name} | " + ", ".join(
                    [f"{k}: {v}" for k, v in annotation.items() if k in self.attributes]
                )
                self.annotations_listbox.insert(tk.END, display_text)
        self.filtered_count_label.config(text=f"Nombre d'images filtrées: {self.annotations_listbox.size()}")

    def on_annotation_select(self, event):
        selection = self.annotations_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        selected_text = self.annotations_listbox.get(index)
        image_info = selected_text.split(' | ')[0]
        if '/' not in image_info:
            return
        folder_name, image_name = image_info.split('/', 1)
        images_dict = self.filtered_annotations.get(folder_name, {}) if self.filtered_annotations else self.annotations.get(folder_name, {})
        annotation = images_dict.get(image_name, None)
        if not annotation:
            messagebox.showerror("Erreur", "Annotation non trouvée pour l'image sélectionnée.")
            return

        image_path = self._resolve_image_path(folder_name, image_name, annotation)
        if not (image_path and os.path.exists(image_path)):
            # Proposer de fixer la racine puis réessayer une seule fois
            if messagebox.askyesno("Image introuvable",
                                   "Chemin d'image introuvable.\nSouhaitez-vous définir une racine d'images ?"):
                root = filedialog.askdirectory(title="Choisissez la racine d'images correspondant au JSON")
                if root:
                    self.annotations_images_root = root
                    image_path = self._resolve_image_path(folder_name, image_name, annotation)

        if not (image_path and os.path.exists(image_path)):
            messagebox.showerror("Erreur", "Le chemin de l'image est invalide ou n'existe pas.")
            return

        try:
            image = Image.open(image_path).convert("RGB")
            image = ImageOps.exif_transpose(image)
            w = max(200, self.manager_image_label.winfo_width() or 600)
            h = max(150, self.manager_image_label.winfo_height() or 400)
            img = image.copy()
            img.thumbnail((w, h), resample=Image.BILINEAR)
            self.manager_displayed_image = ImageTk.PhotoImage(img)
            self.manager_image_label.config(image=self.manager_displayed_image)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'image : {e}")

    def filter_annotations(self):
        if not self.annotations:
            messagebox.showerror("Erreur", "Aucune annotation chargée.")
            return

        selected_filters = {attr: var.get() for attr, var in self.filter_vars.items() if var.get() != "Tous"}
        self.filtered_annotations = {}
        for folder, images in self.annotations.items():
            for image_name, annotation in images.items():
                if all(annotation.get(attr) == val for attr, val in selected_filters.items()):
                    self.filtered_annotations.setdefault(folder, {})[image_name] = annotation

        self.annotations_listbox.delete(0, tk.END)
        if not self.filtered_annotations:
            messagebox.showinfo("Information", "Aucune image ne correspond aux filtres.")
            self.filtered_count_label.config(text="Nombre d'images filtrées: 0")
            self.manager_image_label.config(image='')
            self.manager_displayed_image = None
            return

        for folder in sorted(self.filtered_annotations.keys()):
            images = self.filtered_annotations[folder]
            for image_name in sorted(images.keys(), key=natural_sort_key):
                annotation = images[image_name]
                display_text = f"{folder}/{image_name} | " + ", ".join(
                    [f"{k}: {v}" for k, v in annotation.items() if k in self.attributes]
                )
                self.annotations_listbox.insert(tk.END, display_text)

        total_filtered = sum(len(imgs) for imgs in self.filtered_annotations.values())
        self.filtered_count_label.config(text=f"Nombre d'images filtrées: {total_filtered}")

    def export_filtered_annotations(self):
        if not self.filtered_annotations:
            messagebox.showerror("Erreur", "Aucune annotation filtrée à exporter.")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json")],
                                                 title="Enregistrer le fichier filtré")
        if not save_path:
            messagebox.showwarning("Attention", "Aucun chemin de sauvegarde spécifié.")
            return
        try:
            with open(save_path, 'w') as f:
                json.dump(self.filtered_annotations, f, indent=4)
            messagebox.showinfo("Succès", f"Fichier JSON exporté à {save_path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'exporter : {e}")

    def generate_selected_json(self):
        if not self.annotations:
            messagebox.showerror("Erreur", "Aucune annotation chargée.")
            return
        n = simpledialog.askinteger("Nombre d'images", "Combien d'images voulez-vous ?", parent=self.root, minvalue=1)
        if n is None:
            return
        self.open_proportion_window(n)

    def open_proportion_window(self, total_images):
        prop_window = tk.Toplevel(self.root)
        prop_window.title("Configurer les Proportions")
        prop_window.grab_set()
        prop_window.minsize(600, 400)

        main_frame = tk.Frame(prop_window)
        main_frame.pack(fill="both", expand=True)

        scrollable = SafeScrollableFrame(main_frame, orient="vertical")
        scrollable.pack(fill="both", expand=True)
        scrollable_frame = scrollable.inner

        self.proportion_vars = {}
        self.selected_values = {}
        num_columns = 2
        attributes = list(self.attributes.items())

        for idx, (attribute, values) in enumerate(attributes):
            col = idx % num_columns
            row = idx // num_columns
            attr_frame = tk.LabelFrame(scrollable_frame, text=attribute)
            attr_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            scrollable_frame.grid_columnconfigure(col, weight=1)
            self.proportion_vars[attribute] = {}
            self.selected_values[attribute] = []
            for value in values:
                value_frame = tk.Frame(attr_frame)
                value_frame.pack(fill="x", padx=5, pady=2)
                var_include = tk.BooleanVar(value=False)
                var_proportion = tk.DoubleVar(value=0.0)
                self.selected_values[attribute].append((value, var_include, var_proportion))
                tk.Checkbutton(value_frame, text=value, variable=var_include).pack(side=tk.LEFT)
                tk.Label(value_frame, text="Proportion (%):").pack(side=tk.LEFT, padx=5)
                tk.Entry(value_frame, textvariable=var_proportion, width=5).pack(side=tk.LEFT)

        btn_frame = tk.Frame(prop_window)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Confirmer",
                  command=lambda: self.confirm_proportions(prop_window, total_images)).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Annuler", command=prop_window.destroy).pack(side=tk.LEFT, padx=5)

    def confirm_proportions(self, prop_window, total_images):
        proportions = {}
        for attribute, items in self.selected_values.items():
            total_percentage = 0
            attribute_proportions = {}
            for value, var_include, var_proportion in items:
                if var_include.get():
                    proportion = var_proportion.get()
                    if proportion <= 0:
                        messagebox.showerror("Erreur", f"La proportion pour '{value}' dans '{attribute}' doit être > 0.")
                        return
                    total_percentage += proportion
                    attribute_proportions[value] = proportion
            if total_percentage == 0:
                continue
            for value in attribute_proportions:
                attribute_proportions[value] /= total_percentage
            proportions[attribute] = attribute_proportions

        if not proportions:
            messagebox.showerror("Erreur", "Aucune proportion valide.")
            return

        prop_window.destroy()
        self.generate_json_with_proportions(total_images, proportions)

    def generate_json_with_proportions(self, total_images, proportions):
        source_annotations = [ann for imgs in (self.filtered_annotations or self.annotations).values() for ann in imgs.values()]
        total_available = len(source_annotations)
        if total_images > total_available:
            messagebox.showerror("Erreur", f"Le nombre demandé ({total_images}) dépasse le nombre disponible ({total_available}).")
            return

        attribute_values = []
        for attribute, vals in proportions.items():
            value_list = list(vals.keys())
            attribute_values.append([(attribute, v) for v in value_list])

        combinations = list(itertools.product(*attribute_values))
        combination_proportions = {}
        for combo in combinations:
            prop = 1
            for attribute, value in combo:
                prop *= proportions[attribute][value]
            combination_proportions[combo] = prop

        total_prop = sum(combination_proportions.values())
        for combo in combination_proportions:
            combination_proportions[combo] /= total_prop

        combination_counts = {combo: int(round(prop * total_images)) for combo, prop in combination_proportions.items()}

        selected_annotations = []
        remaining_annotations = source_annotations.copy()
        random.shuffle(remaining_annotations)
        for combo, count in combination_counts.items():
            filtered = [ann for ann in remaining_annotations if all(ann.get(a) == v for (a, v) in combo)]
            if len(filtered) < count:
                count = len(filtered)
            subset = random.sample(filtered, count)
            selected_annotations.extend(subset)
            for s in subset:
                remaining_annotations.remove(s)

        if len(selected_annotations) < total_images:
            needed = total_images - len(selected_annotations)
            plus = random.sample(remaining_annotations, min(needed, len(remaining_annotations)))
            selected_annotations.extend(plus)

        selected_by_folder = {}
        for ann in selected_annotations:
            folder = ann['folder']
            image_name = ann['image_name']
            selected_by_folder.setdefault(folder, {})[image_name] = ann

        save_path = filedialog.asksaveasfilename(defaultextension=".json",
                                                 filetypes=[("JSON files", "*.json")],
                                                 title="Enregistrer le fichier JSON")
        if not save_path:
            messagebox.showwarning("Attention", "Aucun chemin de sauvegarde spécifié.")
            return
        try:
            with open(save_path, 'w') as f:
                json.dump(selected_by_folder, f, indent=4)
            messagebox.showinfo("Succès", f"Fichier JSON généré à {save_path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de générer le JSON : {e}")


# Lancer l'application
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageAnnotator(root)
    root.mainloop()
