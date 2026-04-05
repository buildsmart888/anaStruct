from __future__ import annotations

import datetime
import json
import os
import math
import copy
import csv
from tkinter import filedialog, messagebox

import customtkinter as ctk
import matplotlib.patches as patches
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

# Import real FEA solver from anastruct
try:
    from anastruct import SystemElements as AnaStructSystemElements
    from anastruct.basic import FEMException
    ANACSTRUCT_AVAILABLE = True
except (ImportError, TypeError) as e:
    print(f"Warning: Could not import anastruct: {e}")
    ANACSTRUCT_AVAILABLE = False
    AnaStructSystemElements = None
    FEMException = Exception

from truss_model import TrussModel
from truss_generators import TrussGenerators
from truss_analysis import TrussAnalysisEngine, calculate_buckling_stress, check_member_stability
from truss_exporter import TrussExporter

# Wrapper for anaStruct to integrate with GUI
class TrussAnalyzer:
    """Wrapper around anastruct SystemElements for GUI compatibility"""
    def __init__(self):
        self.ss = AnaStructSystemElements()
        self.element_map = {}  # Maps GUI element IDs to anaStruct element IDs
        self.node_map = {}     # Maps coordinates to node IDs
        self.solved = False
        
    def add_truss_element(self, location, EA):
        """Add a truss element to the system"""
        elem_id = self.ss.add_truss_element(
            location=location,
            EA=EA
        )
        self.element_map[elem_id] = elem_id
        return elem_id
        
    def add_support_hinged(self, node_id):
        """Add hinged support (2 DOF fixed: x, y)"""
        self.ss.add_support_hinged(node_id=node_id)
        
    def add_support_roll(self, node_id, direction):
        """Add roller support"""
        self.ss.add_support_roll(node_id=node_id, direction=direction)
        
    def point_load(self, node_id, Fx, Fy):
        """Apply point load to a node"""
        self.ss.point_load(node_id=node_id, Fx=Fx, Fy=Fy)
        
    def solve(self):
        """Solve the truss system using FEA"""
        try:
            self.ss.solve()
            self.solved = True
        except FEMException as e:
            raise FEMException("Analysis Error", f"Failed to solve: {str(e)}")
            
    def get_element_results(self, element_id):
        """Get axial forces from analyzed truss"""
        if not self.solved:
            return {"Nmin": 0.0, "Nmax": 0.0, "N": 0.0}
        res = self.ss.get_element_results(element_id)
        # Ensure 'N' is not None (anaStruct returns None if verbose=False)
        if isinstance(res, dict) and res.get("N") is None:
            res["N"] = res.get("Nmin", 0.0)
        return res
        
    def validate(self):
        """Check structure stability"""
        return self.ss.validate()
        
    def show_structure(self, show=False, verbosity=0):
        """Visualize structure using base anastruct method"""
        return self.ss.show_structure(show=show, verbosity=verbosity)
        
    def show_displacement(self, show=False, factor=500):
        """Visualize displacements"""
        return self.ss.show_displacement(factor=factor, show=show)
        
    def show_axial_force(self, show=False):
        """Visualize axial forces"""
        return self.ss.show_axial_force(show=show)
        
    @property
    def nodes(self):
        """Get node information from anaStruct"""
        nodes = {}
        for node_id, node in self.ss.node_map.items():
            nodes[node_id] = {
                'id': node_id,
                'x': node.vertex.x,
                'y': node.vertex.y
            }
        return nodes
        
    @property
    def elements(self):
        """Get element information from anaStruct"""
        elements = {}
        for elem_id, elem in self.ss.element_map.items():
            elements[elem_id] = {
                'start': [elem.vertex_1.x, elem.vertex_1.y],
                'end': [elem.vertex_2.x, elem.vertex_2.y],
                'EA': elem.EA,
                'length': elem.l
            }
        return elements
        
    @property
    def displacements(self):
        """Get nodal displacements from solution"""
        displacements = {}
        if self.solved and self.ss.system_displacement_vector is not None:
            for node_id, node in self.ss.node_map.items():
                # Each node has 3 DOF: Fx, Fy, Tz (for 2D)
                idx = (node_id - 1) * 3
                displacements[node_id] = {
                    'dx': self.ss.system_displacement_vector[idx],
                    'dy': self.ss.system_displacement_vector[idx + 1],
                    'rz': self.ss.system_displacement_vector[idx + 2]
                }
        return displacements
        
    @property
    def forces(self):
        """Get element axial forces"""
        forces = {}
        if self.solved:
            for elem_id in self.ss.element_map:
                results = self.get_element_results(elem_id)
                forces[elem_id] = results.get("N", 0.0)
        return forces
        
    @property
    def supports(self):
        """Get support information"""
        supports = {}
        # Get support nodes from ss
        for node in self.ss.supports_fixed:
            supports[node.id] = 'fixed'
        for node, _ in self.ss.supports_spring_y:
            if node.id not in supports:
                supports[node.id] = 'hinged'
        return supports
        
    @property
    def loads(self):
        """Get applied loads"""
        loads = {}
        if hasattr(self.ss, 'loads_point') and self.ss.loads_point:
            for node_id, load_data in self.ss.loads_point.items():
                loads[node_id] = {
                    'Fx': load_data[0][0] if load_data and load_data[0] else 0,
                    'Fy': load_data[0][1] if load_data and load_data[0] else 0
                }
        return loads

    @property
    def reaction_forces(self):
        """Reaction forces at support nodes: {node_id: {'x', 'y', 'Fx', 'Fy'}}"""
        reactions = {}
        for nid, node in self.ss.reaction_forces.items():
            reactions[nid] = {
                'x': node.vertex.x,
                'y': node.vertex.y,
                'Fx': node.Fx,
                'Fy': node.Fy,
            }
        return reactions

# Use real FEA solver
SystemElements = TrussAnalyzer

# --- Professional Steel Database with Grades and Properties ---
STEEL_GRADES = {
    "A36": {"Fy": 250, "Fu": 400, "E": 200000},
    "A572-50": {"Fy": 345, "Fu": 450, "E": 200000},
    "A992": {"Fy": 345, "Fu": 450, "E": 200000},
    "SS400": {"Fy": 235, "Fu": 400, "E": 200000}
}

from steel_database import ALL_PROFILES, SECTION_DB, get_profiles
STEEL_PROFILES = ALL_PROFILES

UNIT_FORCE_TO_KN = {"kN": 1.0, "N": 0.001, "tf": 9.81, "kgf": 0.00981, "kip": 4.448}
UNIT_LENGTH_TO_M = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}

# --- Load Combinations per ASCE 7-16 ---
LOAD_COMBINATIONS = {
    "ASD": {
        "1.0D": {"DL": 1.0, "LL": 0.0, "WL": 0.0, "SL": 0.0},
        "1.0D + 1.0L": {"DL": 1.0, "LL": 1.0, "WL": 0.0, "SL": 0.0},
        "1.0D + 0.75L + 0.75(Lr or S or R)": {"DL": 1.0, "LL": 0.75, "WL": 0.0, "SL": 0.75},
        "1.0D + (1.0W or 0.7E)": {"DL": 1.0, "LL": 0.0, "WL": 1.0, "SL": 0.0}
    },
    "LRFD": {
        "1.4D": {"DL": 1.4, "LL": 0.0, "WL": 0.0, "SL": 0.0},
        "1.2D + 1.6L": {"DL": 1.2, "LL": 1.6, "WL": 0.0, "SL": 0.0},
        "1.2D + 1.6(Lr or S or R)": {"DL": 1.2, "LL": 0.0, "WL": 0.0, "SL": 1.6},
        "1.2D + 1.0W + L + 0.5(Lr or S or R)": {"DL": 1.2, "LL": 1.0, "WL": 1.0, "SL": 0.5},
        "0.9D + 1.0W": {"DL": 0.9, "LL": 0.0, "WL": 1.0, "SL": 0.0}
    }
}

# --- Load case colors (used in load arrow diagrams) ---
CASE_COLORS = {
    "DL": "#E74C3C",   # red
    "LL": "#2980B9",   # blue
    "WL": "#27AE60",   # green
    "SL": "#8E44AD",   # purple
}

# --- Modern Design System ---
PALETTES = {
    "dark": {
        "primary":        "#2563EB",
        "secondary":      "#7C3AED",
        "success":        "#059669",
        "warning":        "#D97706",
        "danger":         "#DC2626",
        "surface":        "#1F2937",
        "background":     "#111827",
        "text_primary":   "#F9FAFB",
        "text_secondary": "#9CA3AF",
        "accent":         "#06B6D4",
        "row_alt":        "#374151",
        "plot_bg":        "#FFFFFF",
        "plot_text":      "#0F172A",
        "header_bar":     "#0F172A",
    },
    "light": {
        "primary":        "#1D4ED8",
        "secondary":      "#6D28D9",
        "success":        "#047857",
        "warning":        "#B45309",
        "danger":         "#B91C1C",
        "surface":        "#FFFFFF",
        "background":     "#F1F5F9",
        "text_primary":   "#0F172A",
        "text_secondary": "#64748B",
        "accent":         "#0891B2",
        "row_alt":        "#E2E8F0",
        "plot_bg":        "#FFFFFF",
        "plot_text":      "#111827",
        "header_bar":     "#1E3A8A",
    },
}
COLOR_PALETTE: dict = dict(PALETTES["dark"])

TYPO_SCALE = {
    "h1": ("Segoe UI", 24, "bold"),
    "h2": ("Segoe UI", 18, "bold"),
    "h3": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 12, "normal"),
    "small": ("Segoe UI", 10, "normal"),
    "mono": ("Consolas", 11, "normal")
}

def _apply_mpl_theme(palette: dict) -> None:
    """Plots always use a light/white background regardless of app theme."""
    plt.rcParams.update({
        "font.family":        "Segoe UI",
        "figure.facecolor":   "#FFFFFF",
        "axes.facecolor":     "#FFFFFF",
        "axes.edgecolor":     "#475569",
        "axes.labelcolor":    "#0F172A",
        "text.color":         "#0F172A",
        "xtick.color":        "#334155",
        "ytick.color":        "#334155",
        "grid.color":         "#CBD5E1",
        "grid.alpha":         0.5,
    })


def _force_light_fig(fig) -> None:
    """Force any matplotlib figure (including anastruct output) to white background."""
    fig.patch.set_facecolor("#FFFFFF")
    for ax in fig.get_axes():
        ax.set_facecolor("#FFFFFF")
        ax.tick_params(colors="#334155")
        ax.xaxis.label.set_color("#0F172A")
        ax.yaxis.label.set_color("#0F172A")
        ax.title.set_color("#0F172A")
        for spine in ax.spines.values():
            spine.set_edgecolor("#CBD5E1")

_apply_mpl_theme(COLOR_PALETTE)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class TrussAnalyzerPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._theme = "dark"
        self.title("Advanced Truss Analyzer PRO v3.0")
        self.geometry("1800x960")
        self.minsize(1100, 650)
        self.configure(bg_color=COLOR_PALETTE["background"])

        # Delegate structural data and history to TrussModel
        self.model = TrussModel()
        self.engine = TrussAnalysisEngine()
        self.ss = None
        self.analysis_results = None

        self.canvas_widgets = []
        self.mini_canvas_widgets = []

        # Node drag state (for preview canvas)
        self._drag_node_idx: int | None = None
        self._drag_ax = None
        self._preview_canvas_ref = None

        # Profile filter state (Standard + Type) — used by members & templates tabs
        self._prof_std_filter  = ctk.StringVar(value="All")
        self._prof_type_filter = ctk.StringVar(value="All")

        self.setup_ui()
        self.refresh_ui()

        # Save initial state for undo/redo after UI setup
        self.save_state()

        # Real-time preview timer
        self.preview_timer = None
        self.auto_preview = True

        # ── Keyboard shortcuts ──────────────────────────────────────────
        self.bind_all("<Control-z>",      lambda e: self.undo())
        self.bind_all("<Control-y>",      lambda e: self.redo())
        self.bind_all("<F5>",             lambda e: self.calculate())
        self.bind_all("<Control-s>",      lambda e: self.save_project())
        self.bind_all("<Control-o>",      lambda e: self.load_project())
        self.bind_all("<Control-p>",      lambda e: self.export_report())
        self.bind_all("<Control-t>",      lambda e: self.toggle_theme())

    def _get_filtered_profiles(self) -> list[str]:
        """Return a list of profile names filtered by the current standard/type dropdowns."""
        std  = self._prof_std_filter.get()
        stype = self._prof_type_filter.get()
        filtered = get_profiles(
            standard=None if std == "All" else std,
            section_type=None if stype == "All" else stype,
        )
        return list(filtered.keys()) or list(STEEL_PROFILES.keys())

    def toggle_theme(self):
        """Switch between dark and light mode, rebuild UI."""
        self._theme = "light" if self._theme == "dark" else "dark"
        COLOR_PALETTE.update(PALETTES[self._theme])
        ctk.set_appearance_mode(self._theme)
        _apply_mpl_theme(COLOR_PALETTE)

        # Destroy and rebuild all UI children
        for w in list(self.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        self.canvas_widgets = []
        self.mini_canvas_widgets = []
        self.configure(bg_color=COLOR_PALETTE["background"])
        self.setup_ui()
        self.refresh_ui()
        if self.ss and self.analysis_results:
            self.update_enhanced_plots()
    
    def save_state(self):
        self.model.save_state()

    def undo(self):
        if self.model.undo():
            self.refresh_ui()

    def redo(self):
        if self.model.redo():
            self.refresh_ui()
    
    def schedule_preview_update(self):
        """Schedule a preview update after a short delay"""
        if self.preview_timer:
            self.after_cancel(self.preview_timer)
        
        if self.auto_preview:
            self.preview_timer = self.after(500, self.update_preview_only)  # 500ms delay
    
    def update_preview_only(self):
        """Update only the structure preview without full analysis"""
        if not self.sync_data(show_errors=False):
            return

        try:
            # Quick structural preview without full analysis
            temp_ss = SystemElements()
            for i, el in enumerate(self.model.elements_data):
                if el["node_a"] > len(self.model.nodes_data) or el["node_b"] > len(self.model.nodes_data):
                    continue
                n1, n2 = self.model.nodes_data[el["node_a"]-1], self.model.nodes_data[el["node_b"]-1]
                temp_ss.add_truss_element(location=[[n1["x"], n1["y"]], [n2["x"], n2["y"]]], EA=1000)

            for i, n in enumerate(self.model.nodes_data):
                if n["support"] == "Pinned": temp_ss.add_support_hinged(node_id=i+1)
                elif n["support"] == "Roller": temp_ss.add_support_roll(node_id=i+1, direction=2)

            # Update preview visualization (custom per-case arrows drawn inside)
            self.update_structure_preview(temp_ss)
        except Exception:
            pass

    def setup_ui(self):
        # ── Responsive grid: left panel fixed-ish, right panel expands ──
        self.grid_columnconfigure(0, weight=0, minsize=420)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)   # bottom status bar

        # ── Left Panel ───────────────────────────────────────────────────
        self.left_panel = ctk.CTkFrame(self, fg_color=COLOR_PALETTE["surface"], corner_radius=12)
        self.left_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(12, 6), pady=12)

        # Header row: title + theme toggle
        hdr = ctk.CTkFrame(self.left_panel, fg_color=COLOR_PALETTE["header_bar"], corner_radius=8)
        hdr.pack(fill="x", padx=8, pady=(8, 4))

        ctk.CTkLabel(hdr, text="Advanced Truss Designer",
                     font=TYPO_SCALE["h3"],
                     text_color="#FFFFFF").pack(side="left", padx=12, pady=8)

        # Theme toggle button (right side of header)
        theme_icon = "☀" if self._theme == "dark" else "☾"
        theme_tip  = "Light mode (Ctrl+T)" if self._theme == "dark" else "Dark mode (Ctrl+T)"
        self._theme_btn = ctk.CTkButton(
            hdr, text=f"{theme_icon}  {'Light' if self._theme == 'dark' else 'Dark'}",
            width=90, height=28, corner_radius=6,
            fg_color=COLOR_PALETTE["primary"],
            hover_color=COLOR_PALETTE["accent"],
            font=TYPO_SCALE["small"],
            command=self.toggle_theme,
        )
        self._theme_btn.pack(side="right", padx=8, pady=6)

        # Undo / Redo / Auto-preview row
        undo_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        undo_frame.pack(fill="x", padx=8, pady=(4, 0))

        ctk.CTkButton(undo_frame, text="Undo (Ctrl+Z)", width=110, height=28,
                      fg_color=COLOR_PALETTE["secondary"],
                      font=TYPO_SCALE["small"],
                      command=self.undo).pack(side="left", padx=3)
        ctk.CTkButton(undo_frame, text="Redo (Ctrl+Y)", width=110, height=28,
                      fg_color=COLOR_PALETTE["secondary"],
                      font=TYPO_SCALE["small"],
                      command=self.redo).pack(side="left", padx=3)

        self.auto_preview_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(undo_frame, text="Auto Preview",
                        variable=self.auto_preview_var,
                        font=TYPO_SCALE["small"],
                        command=self.toggle_auto_preview).pack(side="right", padx=6)

        # Tab view
        self.tabs = ctk.CTkTabview(self.left_panel, fg_color=COLOR_PALETTE["surface"])
        self.tabs.pack(fill="both", expand=True, padx=6, pady=4)

        self.tab_proj  = self.tabs.add("Project")
        self.tab_nodes = self.tabs.add("Nodes")
        self.tab_elems = self.tabs.add("Members")
        self.tab_loads = self.tabs.add("Loads")
        self.tab_combo = self.tabs.add("Combos")
        self.tab_templ = self.tabs.add("Templates")
        self.tab_res   = self.tabs.add("Results")

        # Action buttons
        ctrl = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        ctrl.pack(fill="x", padx=8, pady=8)

        ctk.CTkButton(ctrl, text="ANALYZE  (F5)",
                      height=44, corner_radius=8,
                      fg_color=COLOR_PALETTE["success"],
                      hover_color="#065F46",
                      font=TYPO_SCALE["h3"],
                      command=self.calculate).pack(fill="x", pady=(0, 6))

        btn_row1 = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row1.pack(fill="x", pady=2)
        ctk.CTkButton(btn_row1, text="Save (Ctrl+S)", height=32, corner_radius=6,
                      fg_color=COLOR_PALETTE["primary"],
                      font=TYPO_SCALE["small"],
                      command=self.save_project).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(btn_row1, text="Load (Ctrl+O)", height=32, corner_radius=6,
                      fg_color=COLOR_PALETTE["primary"],
                      font=TYPO_SCALE["small"],
                      command=self.load_project).pack(side="left", expand=True, fill="x", padx=(3, 0))

        btn_row2 = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row2.pack(fill="x", pady=2)
        ctk.CTkButton(btn_row2, text="CSV Export", height=32, corner_radius=6,
                      fg_color=COLOR_PALETTE["warning"],
                      font=TYPO_SCALE["small"],
                      command=self.export_csv).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(btn_row2, text="PDF Report (Ctrl+P)", height=32, corner_radius=6,
                      fg_color=COLOR_PALETTE["danger"],
                      font=TYPO_SCALE["small"],
                      command=self.export_report).pack(side="left", expand=True, fill="x", padx=(3, 0))

        # ── Right Panel wrapper ──────────────────────────────────────────
        right_wrapper = ctk.CTkFrame(self, fg_color=COLOR_PALETTE["background"], corner_radius=12)
        right_wrapper.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=(12, 0))
        right_wrapper.grid_rowconfigure(0, weight=0)
        right_wrapper.grid_rowconfigure(1, weight=1)
        right_wrapper.grid_columnconfigure(0, weight=1)

        # ── Plot layer toggle bar ────────────────────────────────────────
        toggle_bar = ctk.CTkFrame(right_wrapper, fg_color=COLOR_PALETTE["surface"], corner_radius=8)
        toggle_bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))
        ctk.CTkLabel(toggle_bar, text="Show Plots:",
                     font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=(10, 4), pady=4)

        self._plot_vars: dict[str, ctk.BooleanVar] = {}
        _plot_names = [
            ("Structure",     "show_structure"),
            ("Axial Force",   "show_axial"),
            ("Displacement",  "show_disp"),
            ("Utilization",   "show_util"),
            ("Reactions",     "show_react"),
        ]
        def _make_toggle(label, key):
            var = ctk.BooleanVar(value=True)
            self._plot_vars[key] = var
            def _cb():
                if self.ss and self.analysis_results:
                    self.update_enhanced_plots()
            ctk.CTkCheckBox(toggle_bar, text=label, variable=var,
                            font=TYPO_SCALE["small"], width=110,
                            command=_cb).pack(side="left", padx=4, pady=4)
        for lbl, key in _plot_names:
            _make_toggle(lbl, key)

        # ── Right Panel (plots) ──────────────────────────────────────────
        self.right_panel = ctk.CTkScrollableFrame(
            right_wrapper, fg_color=COLOR_PALETTE["background"], corner_radius=0)
        self.right_panel.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # Status bar (full width, bottom)
        self.status_frame = ctk.CTkFrame(
            self, height=32, fg_color=COLOR_PALETTE["header_bar"], corner_radius=0)
        self.status_frame.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(4, 12))
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(1, weight=0)

        self.status_label = ctk.CTkLabel(
            self.status_frame, text="Ready  |  F5 = Analyze   Ctrl+Z/Y = Undo/Redo   Ctrl+T = Theme",
            font=TYPO_SCALE["small"], text_color=COLOR_PALETTE["text_secondary"])
        self.status_label.grid(row=0, column=0, padx=12, pady=4, sticky="w")

        # Keyboard shortcut hint (right side of status bar)
        ctk.CTkLabel(self.status_frame,
                     text=f"{'Dark' if self._theme == 'dark' else 'Light'} mode",
                     font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["accent"]).grid(
                     row=0, column=1, padx=12, pady=4, sticky="e")

    def toggle_auto_preview(self):
        self.auto_preview = self.auto_preview_var.get()

    def refresh_ui(self):
        self.draw_nodes_tab()
        self.draw_elements_tab()
        self.draw_loads_tab()
        self.draw_combo_tab()
        self.draw_templates_tab()
        self.draw_project_tab()

    def sync_data(self, show_errors=True):
        try:
            # Enhanced validation with engineering checks
            new_nodes = []
            for i, e in enumerate(self.node_entries):
                try:
                    x, y = float(e["x"].get()), float(e["y"].get())
                    if abs(x) > 1000 or abs(y) > 1000:
                        raise ValueError(f"Unrealistic coordinates at Node N{i+1} (>1000m)")
                    new_nodes.append({"x": x, "y": y, "support": e["support"].get()})
                except ValueError as ve:
                    if "could not convert" in str(ve):
                        raise ValueError(f"Non-numeric coordinate at Node N{i+1}")
                    raise ve
            
            new_elems = []
            for i, e in enumerate(self.elem_entries):
                try:
                    node_a, node_b = int(e["a"].get()), int(e["b"].get())
                    if node_a == node_b:
                        raise ValueError(f"Member E{i+1}: Same start/end node")
                    if node_a < 1 or node_b < 1 or node_a > len(new_nodes) or node_b > len(new_nodes):
                        raise ValueError(f"Member E{i+1}: Invalid node reference (Max N{len(new_nodes)})")
                    
                    profile = e["profile"].get()
                    if profile not in STEEL_PROFILES:
                        raise ValueError(f"Member E{i+1}: Unknown profile '{profile}'")
                    
                    new_elems.append({"node_a": node_a, "node_b": node_b, "profile": profile})
                except ValueError as ve:
                    if "invalid literal" in str(ve):
                        raise ValueError(f"Non-numeric node ID at Member E{i+1}")
                    raise ve

            new_loads = []
            for i, e in enumerate(self.load_entries):
                try:
                    node_id = int(e["id"].get())
                    fx, fy = float(e["fx"].get()), float(e["fy"].get())
                    
                    if node_id < 1 or node_id > len(new_nodes):
                        raise ValueError(f"Load #{i+1}: Invalid node N{node_id} (Max N{len(new_nodes)})")
                    
                    if abs(fx) > 10000 or abs(fy) > 10000:
                        raise ValueError(f"Load #{i+1}: Unrealistic load magnitude (>10,000 kN). Input must be in kN.")
                        
                    new_loads.append({"node_id": node_id, "fx": fx, "fy": fy, "case": e["case"].get()})
                except ValueError as ve:
                    if "invalid literal" in str(ve):
                        raise ValueError(f"Non-numeric value at Load #{i+1}")
                    raise ve

            # Structural validation
            if len(new_nodes) < 2:
                raise ValueError("Minimum 2 nodes required for analysis")
            
            if len(new_elems) < 1:
                raise ValueError("Minimum 1 member required for analysis")
            
            # Check for zero-length elements (coincident endpoint nodes)
            # Note: coincident *nodes* are allowed — anastruct merges them automatically.
            # Only reject elements whose two endpoints are at exactly the same position.
            import math as _math
            for k, el in enumerate(new_elems):
                na, nb = el["node_a"] - 1, el["node_b"] - 1
                if 0 <= na < len(new_nodes) and 0 <= nb < len(new_nodes):
                    n1, n2 = new_nodes[na], new_nodes[nb]
                    dist = _math.sqrt((n1["x"]-n2["x"])**2 + (n1["y"]-n2["y"])**2)
                    if dist < 1e-6:
                        raise ValueError(
                            f"Member E{k+1} (N{el['node_a']}–N{el['node_b']}) "
                            f"has zero length — the two nodes are at the same location"
                        )

            self.model.nodes_data = new_nodes
            self.model.elements_data = new_elems
            self.model.loads_data = new_loads
            
            self.update_status("✓ Data validated successfully", "success")
            return True
            
        except Exception as e:
            if show_errors:
                messagebox.showerror("⚠️ Validation Error", str(e))
                self.update_status(f"⚠️ Error: {str(e)}", "error")
            return False
    
    def update_status(self, message, status_type="info"):
        """Update status bar with color coding"""
        # Check if status_label exists (GUI might not be initialized yet)
        if not hasattr(self, 'status_label'):
            return
            
        color_map = {
            "success": COLOR_PALETTE["success"],
            "warning": COLOR_PALETTE["warning"], 
            "error": COLOR_PALETTE["danger"],
            "info": COLOR_PALETTE["text_secondary"]
        }
        self.status_label.configure(text=message, text_color=color_map.get(status_type, color_map["info"]))

    def draw_nodes_tab(self):
        self.update_idletasks()
        for w in self.tab_nodes.winfo_children():
            try: w.destroy()
            except Exception: pass
        
        # Header with instructions
        header = ctk.CTkFrame(self.tab_nodes, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Node Coordinates & Boundary Conditions", 
                     font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["text_primary"]).pack()
        ctk.CTkLabel(header, text="Units: Length in meters, Supports define restraints", 
                     font=TYPO_SCALE["small"], text_color=COLOR_PALETTE["text_secondary"]).pack()
        
        # Column headers
        header_row = ctk.CTkFrame(self.tab_nodes, fg_color=COLOR_PALETTE["secondary"])
        header_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header_row, text="Node", width=40, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="X (m)", width=70, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Y (m)", width=70, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Support Type", width=120, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        
        scroll = ctk.CTkScrollableFrame(self.tab_nodes, height=350, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        
        self.node_entries = []
        for i, n in enumerate(self.model.nodes_data):
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=3)
            
            ctk.CTkLabel(row, text=f"N{i+1}", width=40, font=TYPO_SCALE["body"]).pack(side="left", padx=5)
            
            ex = ctk.CTkEntry(row, width=70, font=TYPO_SCALE["mono"])
            ex.insert(0, f"{n['x']:.3f}")
            ex.pack(side="left", padx=5)
            ex.bind('<KeyRelease>', lambda e: self.schedule_preview_update())
            
            ey = ctk.CTkEntry(row, width=70, font=TYPO_SCALE["mono"])
            ey.insert(0, f"{n['y']:.3f}")
            ey.pack(side="left", padx=5)
            ey.bind('<KeyRelease>', lambda e: self.schedule_preview_update())
            
            sv = ctk.StringVar(value=n["support"])
            support_menu = ctk.CTkOptionMenu(row, values=["Free", "Pinned", "Roller"], 
                                           variable=sv, width=120, font=TYPO_SCALE["small"])
            support_menu.pack(side="left", padx=5)
            
            delete_btn = ctk.CTkButton(row, text="✗", width=35, height=30, 
                                       fg_color=COLOR_PALETTE["danger"], 
                                       command=lambda idx=i: self.delete_row_with_save("node", idx))
            delete_btn.pack(side="right", padx=5)
            
            self.node_entries.append({"x": ex, "y": ey, "support": sv})
        
        # Add button
        add_frame = ctk.CTkFrame(self.tab_nodes, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(add_frame, text="✚ Add Node", height=40, 
                      fg_color=COLOR_PALETTE["success"], command=self.add_node_with_save).pack()

    def draw_elements_tab(self):
        self.update_idletasks()
        for w in self.tab_elems.winfo_children():
            try: w.destroy()
            except Exception: pass
        
        # Header
        header = ctk.CTkFrame(self.tab_elems, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Structural Members & Cross-Sections", 
                     font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["text_primary"]).pack()
        ctk.CTkLabel(header, text="Connect nodes with steel profiles - Properties include buckling resistance", 
                     font=TYPO_SCALE["small"], text_color=COLOR_PALETTE["text_secondary"]).pack()
        
        # Profile filter bar
        filter_bar = ctk.CTkFrame(self.tab_elems, fg_color=COLOR_PALETTE["row_alt"])
        filter_bar.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(filter_bar, text="Standard:", font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=(8, 2), pady=4)
        ctk.CTkOptionMenu(
            filter_bar,
            values=["All", "TIS", "JIS", "EN", "AISC", "Custom"],
            variable=self._prof_std_filter,
            width=80, height=26, font=TYPO_SCALE["small"],
            command=lambda _v: self.draw_elements_tab(),
        ).pack(side="left", padx=2, pady=4)
        ctk.CTkLabel(filter_bar, text="Type:", font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=(10, 2), pady=4)
        ctk.CTkOptionMenu(
            filter_bar,
            values=["All", "RHS", "CHS", "Angle", "I-Beam", "H-Beam", "Channel", "Custom"],
            variable=self._prof_type_filter,
            width=100, height=26, font=TYPO_SCALE["small"],
            command=lambda _v: self.draw_elements_tab(),
        ).pack(side="left", padx=2, pady=4)

        # Column headers
        header_row = ctk.CTkFrame(self.tab_elems, fg_color=COLOR_PALETTE["secondary"])
        header_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header_row, text="Member", width=50, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Node A", width=50, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Node B", width=50, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Steel Profile", width=140, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Type", width=80, font=TYPO_SCALE["small"]).pack(side="left", padx=5)

        scroll = ctk.CTkScrollableFrame(self.tab_elems, height=350, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        
        self.elem_entries = []
        for i, el in enumerate(self.model.elements_data):
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=3)
            
            ctk.CTkLabel(row, text=f"E{i+1}", width=50, font=TYPO_SCALE["body"]).pack(side="left", padx=5)
            
            ea = ctk.CTkEntry(row, width=50, font=TYPO_SCALE["mono"])
            ea.insert(0, str(el["node_a"]))
            ea.pack(side="left", padx=5)
            ea.bind('<KeyRelease>', lambda e: self.schedule_preview_update())
            
            eb = ctk.CTkEntry(row, width=50, font=TYPO_SCALE["mono"])
            eb.insert(0, str(el["node_b"]))
            eb.pack(side="left", padx=5)
            eb.bind('<KeyRelease>', lambda e: self.schedule_preview_update())
            
            _filtered_profiles = self._get_filtered_profiles()
            _default_profile   = el.get("profile", "RHS 50x50x2.3")
            if _default_profile not in _filtered_profiles:
                _default_profile = _filtered_profiles[0] if _filtered_profiles else "RHS 50x50x2.3"
            pv = ctk.StringVar(value=_default_profile)
            profile_menu = ctk.CTkOptionMenu(row, values=_filtered_profiles,
                                             variable=pv, width=140, font=TYPO_SCALE["small"])
            profile_menu.pack(side="left", padx=5)
            
            # Member type display
            member_type = el.get("member_type", "General")
            type_colors = {
                "Top Chord": "#E74C3C",
                "Bottom Chord": "#3498DB", 
                "Vertical": "#27AE60",
                "Diagonal": "#F39C12",
                "General": "#95A5A6"
            }
            ctk.CTkLabel(row, text=member_type, width=80, font=TYPO_SCALE["small"],
                        text_color=type_colors.get(member_type, "#95A5A6")).pack(side="left", padx=5)
            
            delete_btn = ctk.CTkButton(row, text="✗", width=35, height=30, 
                                       fg_color=COLOR_PALETTE["danger"], 
                                       command=lambda idx=i: self.delete_row_with_save("elem", idx))
            delete_btn.pack(side="right", padx=5)
            
            self.elem_entries.append({"a": ea, "b": eb, "profile": pv})
        
        # Add button
        add_frame = ctk.CTkFrame(self.tab_elems, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(add_frame, text="✚ Add Member", height=40, 
                      fg_color=COLOR_PALETTE["success"], command=self.add_member_with_save).pack()

    def draw_loads_tab(self):
        self.update_idletasks()
        for w in self.tab_loads.winfo_children():
            try: w.destroy()
            except Exception: pass
        
        # Header
        header = ctk.CTkFrame(self.tab_loads, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Applied Loads & Load Cases", 
                     font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["text_primary"]).pack()
        ctk.CTkLabel(header,
                     text="Input unit: kN  |  Fx = horizontal, Fy = vertical (-ve = downward)",
                     font=TYPO_SCALE["small"], text_color=COLOR_PALETTE["text_secondary"]).pack()

        # Column headers
        header_row = ctk.CTkFrame(self.tab_loads, fg_color=COLOR_PALETTE["secondary"])
        header_row.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(header_row, text="Node", width=50, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Fx (kN)", width=70, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Fy (kN)", width=70, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(header_row, text="Case", width=80, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        
        scroll = ctk.CTkScrollableFrame(self.tab_loads, height=300, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        
        self.load_entries = []
        for i, ld in enumerate(self.model.loads_data):
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=3)
            
            en = ctk.CTkEntry(row, width=50, font=TYPO_SCALE["mono"])
            en.insert(0, str(ld["node_id"]))
            en.pack(side="left", padx=5)
            
            efx = ctk.CTkEntry(row, width=70, font=TYPO_SCALE["mono"])
            efx.insert(0, f"{ld.get('fx', 0):.1f}")
            efx.pack(side="left", padx=5)
            
            efy = ctk.CTkEntry(row, width=70, font=TYPO_SCALE["mono"])
            efy.insert(0, f"{ld['fy']:.1f}")
            efy.pack(side="left", padx=5)
            
            cv = ctk.StringVar(value=ld["case"])
            case_menu = ctk.CTkOptionMenu(row, values=["DL", "LL", "WL", "SL"], 
                                        variable=cv, width=80, font=TYPO_SCALE["small"])
            case_menu.pack(side="left", padx=5)
            
            delete_btn = ctk.CTkButton(row, text="✗", width=35, height=30, 
                                       fg_color=COLOR_PALETTE["danger"], 
                                       command=lambda idx=i: self.delete_row_with_save("load", idx))
            delete_btn.pack(side="right", padx=5)
            
            self.load_entries.append({"id": en, "fx": efx, "fy": efy, "case": cv})
        
        # Add button
        add_frame = ctk.CTkFrame(self.tab_loads, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(add_frame, text="➕ Add Load", height=40, 
                      fg_color=COLOR_PALETTE["success"], command=self.add_load_with_save).pack()
        
        # Load case legend
        legend_frame = ctk.CTkFrame(self.tab_loads, fg_color=COLOR_PALETTE["surface"])
        legend_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(legend_frame, text="Load Cases: DL=Dead, LL=Live, WL=Wind, SL=Snow", 
                     font=TYPO_SCALE["small"], text_color=COLOR_PALETTE["text_secondary"]).pack(pady=5)
    
    def draw_combo_tab(self):
        """Load Combinations Tab"""
        self.update_idletasks()
        for w in self.tab_combo.winfo_children():
            try: w.destroy()
            except Exception: pass
        
        # Header
        header = ctk.CTkFrame(self.tab_combo, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Load Combinations (ASCE 7-16)", 
                     font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["text_primary"]).pack()
        
        # Method selection
        method_frame = ctk.CTkFrame(self.tab_combo, fg_color=COLOR_PALETTE["surface"])
        method_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(method_frame, text="Design Method:", font=TYPO_SCALE["body"]).pack(side="left", padx=10)
        
        self.method_var = ctk.StringVar(value=self.model.design_method)
        method_radio_frame = ctk.CTkFrame(method_frame, fg_color="transparent")
        method_radio_frame.pack(side="left", padx=20)
        
        ctk.CTkRadioButton(method_radio_frame, text="ASD (Allowable Stress)", 
                          variable=self.method_var, value="ASD", command=self.update_combinations).pack(pady=2)
        ctk.CTkRadioButton(method_radio_frame, text="LRFD (Load & Resistance Factor)", 
                          variable=self.method_var, value="LRFD", command=self.update_combinations).pack(pady=2)
        
        # Combination selection
        combo_frame = ctk.CTkFrame(self.tab_combo, fg_color="transparent")
        combo_frame.pack(fill="both", expand=True, padx=10, pady=(5, 0))

        ctk.CTkLabel(combo_frame, text="Select Load Combination:", font=TYPO_SCALE["body"]).pack(anchor="w", pady=5)

        self.combo_var = ctk.StringVar(value=self.model.selected_combo)
        self.combo_listbox = ctk.CTkScrollableFrame(combo_frame, height=180)
        self.combo_listbox.pack(fill="both", expand=True)

        # ── Add Custom Combination ────────────────────────────────────────────
        add_frame = ctk.CTkFrame(self.tab_combo, fg_color=COLOR_PALETTE["surface"])
        add_frame.pack(fill="x", padx=10, pady=(6, 10))

        ctk.CTkLabel(add_frame, text="➕ Add Custom Combination",
                     font=TYPO_SCALE["body"]).pack(anchor="w", padx=10, pady=(8, 4))

        name_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        name_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(name_row, text="Name:", width=50).pack(side="left")
        self._custom_name_var = ctk.StringVar()
        ctk.CTkEntry(name_row, textvariable=self._custom_name_var,
                     placeholder_text="e.g. 1.35D + 1.5L", width=260).pack(side="left", padx=(4, 0))

        factor_row = ctk.CTkFrame(add_frame, fg_color="transparent")
        factor_row.pack(fill="x", padx=10, pady=2)
        self._custom_factors: dict[str, ctk.StringVar] = {}
        for case in ("DL", "LL", "WL", "SL"):
            ctk.CTkLabel(factor_row, text=f"{case}:", width=28).pack(side="left")
            sv = ctk.StringVar(value="0.0")
            ctk.CTkEntry(factor_row, textvariable=sv, width=56).pack(side="left", padx=(2, 8))
            self._custom_factors[case] = sv

        ctk.CTkButton(add_frame, text="Add", width=80,
                      command=self._add_custom_combination).pack(anchor="e", padx=10, pady=(4, 8))

        self.update_combinations()
    
    def update_combinations(self):
        """Update available load combinations based on selected method."""
        self.update_idletasks()
        for w in self.combo_listbox.winfo_children():
            try: w.destroy()
            except Exception: pass

        method = self.method_var.get()
        self.model.design_method = method

        # Merge built-in + custom for this method
        all_combos: dict = {**LOAD_COMBINATIONS[method],
                            **self.model.custom_combinations.get(method, {})}

        # Reset selection if current value doesn't belong to the new method
        if self.combo_var.get() not in all_combos:
            first_combo = next(iter(all_combos))
            self.combo_var.set(first_combo)
            self.model.selected_combo = first_combo

        custom_names = set(self.model.custom_combinations.get(method, {}).keys())

        for combo_name, factors in all_combos.items():
            is_custom = combo_name in custom_names
            row = ctk.CTkFrame(self.combo_listbox,
                               fg_color=COLOR_PALETTE["surface"] if not is_custom else "#1e3a2f")
            row.pack(fill="x", pady=2)

            radio = ctk.CTkRadioButton(row, text=combo_name, variable=self.combo_var,
                                       value=combo_name,
                                       command=lambda v=combo_name: setattr(self.model, "selected_combo", v))
            radio.pack(side="left", padx=10)

            factors_text = " | ".join([f"{k}:{v}" for k, v in factors.items() if v != 0])
            ctk.CTkLabel(row, text=factors_text, font=TYPO_SCALE["small"],
                         text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=6)

            if is_custom:
                ctk.CTkButton(row, text="✕", width=28, height=22, fg_color="#c0392b",
                              command=lambda n=combo_name: self._delete_custom_combination(n)
                              ).pack(side="right", padx=6)

    def _add_custom_combination(self):
        """Validate inputs and add a new custom combination."""
        name = self._custom_name_var.get().strip()
        if not name:
            messagebox.showwarning("Custom Combination", "Please enter a combination name.")
            return

        method = self.method_var.get()
        all_combos = {**LOAD_COMBINATIONS[method], **self.model.custom_combinations.get(method, {})}
        if name in all_combos:
            messagebox.showwarning("Custom Combination", f'"{name}" already exists.')
            return

        try:
            factors = {case: float(sv.get()) for case, sv in self._custom_factors.items()}
        except ValueError:
            messagebox.showerror("Custom Combination", "Factors must be numbers.")
            return

        if all(v == 0.0 for v in factors.values()):
            messagebox.showwarning("Custom Combination", "At least one factor must be non-zero.")
            return

        self.model.custom_combinations.setdefault(method, {})[name] = factors
        self._custom_name_var.set("")
        for sv in self._custom_factors.values():
            sv.set("0.0")
        self.update_combinations()
        # Auto-select the newly added combo
        self.combo_var.set(name)
        self.model.selected_combo = name

    def _delete_custom_combination(self, name: str):
        """Remove a custom combination and reset selection if it was active."""
        method = self.method_var.get()
        self.model.custom_combinations.get(method, {}).pop(name, None)
        if self.model.selected_combo == name:
            first = next(iter(LOAD_COMBINATIONS[method]))
            self.combo_var.set(first)
            self.model.selected_combo = first
        self.update_combinations()

    # Enhanced add/delete with state saving
    def add_node_with_save(self): 
        if self.sync_data(): 
            self.model.nodes_data.append({"x": 0, "y": 0, "support": "Free"})
            self.save_state()
            self.refresh_ui()
            self.schedule_preview_update()
    
    def add_member_with_save(self): 
        if self.sync_data(): 
            max_node = len(self.model.nodes_data)
            if max_node >= 2:
                self.model.elements_data.append({"node_a": 1, "node_b": min(2, max_node), "profile": "Box 50x50x2.3"})
                self.save_state()
                self.refresh_ui()
                self.schedule_preview_update()
            else:
                messagebox.showwarning("Warning", "Need at least 2 nodes to create a member")
    
    def add_load_with_save(self): 
        if self.sync_data(): 
            if self.model.nodes_data:
                self.model.loads_data.append({"node_id": 1, "fx": 0, "fy": -10, "case": "LL"})
                self.save_state()
                self.refresh_ui()
            else:
                messagebox.showwarning("Warning", "Need at least 1 node to apply load")
    
    def delete_row_with_save(self, row_type, idx):
        if self.sync_data():
            if row_type == "node" and len(self.model.nodes_data) <= 2:
                messagebox.showwarning("Warning", "Cannot delete - minimum 2 nodes required")
                return
            elif row_type == "elem" and len(self.model.elements_data) <= 1:
                messagebox.showwarning("Warning", "Cannot delete - minimum 1 member required")
                return
                
            if row_type == "node": self.model.nodes_data.pop(idx)
            elif row_type == "elem": self.model.elements_data.pop(idx)
            elif row_type == "load": self.model.loads_data.pop(idx)
            
            self.save_state()
            self.refresh_ui()
            self.schedule_preview_update()

    def calculate(self):
        if not self.sync_data():
            return
        if not self.model.elements_data:
            messagebox.showwarning("⚠️ Analysis Error", "No members to analyze!")
            return

        unique_coords = {(round(n["x"], 6), round(n["y"], 6)) for n in self.model.nodes_data}
        nj = len(unique_coords)
        nm = len(self.model.elements_data)
        nr = sum(
            2 if n["support"] == "Pinned" else (1 if n["support"] == "Roller" else 0)
            for n in self.model.nodes_data
        )
        if (nm + nr) < (2 * nj):
            messagebox.showwarning(
                "Stability Alert",
                f"Structure may be unstable!\n{nm} Members + {nr} Reactions < 2x{nj} Nodes\n\nRecommend adding members or supports."
            )
        elif (nm + nr) > (2 * nj):
            self.update_status(
                f"Statically indeterminate: {nm}m + {nr}r > 2x{nj}j", "info"
            )

        _sw_injected: list[dict] = []
        try:
            self.update_status("🔄 Running structural analysis...", "info")
            self.model.selected_combo = self.combo_var.get()

            # ── Self-weight: inject DL loads before analysis ──────────────
            if getattr(self.model, "self_weight_enabled", False):
                for el in self.model.elements_data:
                    prof  = STEEL_PROFILES.get(el["profile"], {})
                    area  = prof.get("Area", 0.0)          # cm²
                    kg_pm = area * 0.785                   # kg/m  (ρ=7850 kg/m³)
                    n1    = self.model.nodes_data[el["node_a"] - 1]
                    n2    = self.model.nodes_data[el["node_b"] - 1]
                    L     = math.sqrt((n2["x"]-n1["x"])**2 + (n2["y"]-n1["y"])**2)
                    w_kN  = kg_pm * L * 9.81 / 1000        # total member weight in kN
                    # Distribute half to each end node
                    for nid in (el["node_a"], el["node_b"]):
                        ld = {"node_id": nid, "fx": 0.0, "fy": -w_kN / 2, "case": "DL"}
                        self.model.loads_data.append(ld)
                        _sw_injected.append(ld)

            # Merge built-in + custom combinations before passing to engine
            merged_combos = {
                method: {**LOAD_COMBINATIONS[method],
                         **self.model.custom_combinations.get(method, {})}
                for method in LOAD_COMBINATIONS
            }
            self.ss = self.engine.build_and_solve(
                self.model, SystemElements, STEEL_GRADES, STEEL_PROFILES, merged_combos
            )
            self.analysis_results = self.engine.member_checks(
                self.model, self.ss, STEEL_GRADES, STEEL_PROFILES
            )

            # ── All-combo utilization sweep ───────────────────────────────
            self.all_combo_results: dict[str, list[dict]] = {}
            _orig_combo = self.model.selected_combo
            _dm = self.model.design_method
            for _combo_name, _factors in merged_combos.get(_dm, {}).items():
                try:
                    _tmp_model = copy.deepcopy(self.model)
                    _tmp_model.selected_combo = _combo_name
                    # Re-inject self-weight if enabled
                    if getattr(self.model, "self_weight_enabled", False):
                        for el in _tmp_model.elements_data:
                            prof  = STEEL_PROFILES.get(el["profile"], {})
                            area  = prof.get("Area", 0.0)
                            kg_pm = area * 0.785
                            n1    = _tmp_model.nodes_data[el["node_a"] - 1]
                            n2    = _tmp_model.nodes_data[el["node_b"] - 1]
                            L     = math.sqrt((n2["x"]-n1["x"])**2 + (n2["y"]-n1["y"])**2)
                            w_kN  = kg_pm * L * 9.81 / 1000
                            for nid in (el["node_a"], el["node_b"]):
                                _tmp_model.loads_data.append(
                                    {"node_id": nid, "fx": 0.0, "fy": -w_kN / 2, "case": "DL"})
                    _tmp_ss = self.engine.build_and_solve(
                        _tmp_model, SystemElements, STEEL_GRADES, STEEL_PROFILES, merged_combos)
                    self.all_combo_results[_combo_name] = self.engine.member_checks(
                        _tmp_model, _tmp_ss, STEEL_GRADES, STEEL_PROFILES)
                except Exception:
                    pass
            self.model.selected_combo = _orig_combo

            self.update_enhanced_plots()
            self.show_enhanced_results()
            self.update_status(f"✅ Analysis complete — {self.model.selected_combo}", "success")

        except Exception as e:
            msg = f"Analysis failed: {e}"
            messagebox.showerror("❌ Analysis Error", msg)
            self.update_status(f"❌ {msg}", "error")

        finally:
            # Remove any injected self-weight loads so they don't persist
            for ld in _sw_injected:
                try:
                    self.model.loads_data.remove(ld)
                except ValueError:
                    pass

    def _rescale_graph_labels(self, fig, diagram_type):
        """Convert anastruct graph text labels to user-selected units."""
        import re

        ff = UNIT_FORCE_TO_KN[self.model.unit_force]
        lf = UNIT_LENGTH_TO_M[self.model.unit_length]
        
        ax = fig.gca()
        for text in ax.texts:
            t = text.get_text().strip()
            if diagram_type == "structure":
                # Match patterns like F=10.0, Fy=-5.0, Fx=5.0
                m = re.match(r"^(F|Fx|Fy)=(-?[\d.eE+\-]+)", t)
                if m:
                    prefix, raw = m.group(1), float(m.group(2))
                    text.set_text(f"{prefix}={raw / ff:.3g}")
            elif diagram_type == "axial":
                try:
                    # Pure numeric values or N=...
                    val_str = t.replace("N=", "")
                    val = float(val_str)
                    text.set_text(f"{val / ff:.2f}")
                except ValueError:
                    pass

    def add_dimensions(self, fig):
        """Add overall span and height dimensions to the truss plot."""
        if not self.model.nodes_data:
            return
        import numpy as np

        ax = fig.gca()
        xs = [n["x"] for n in self.model.nodes_data]
        ys = [n["y"] for n in self.model.nodes_data]
        
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        
        width = xmax - xmin
        height = ymax - ymin
        
        # Get overall plot bounds
        cur_ymin, cur_ymax = ax.get_ylim()
        y_range = cur_ymax - cur_ymin
        
        # 1. Horizontal Span Dimension (Bottom)
        y_dim = cur_ymin - y_range * 0.15
        ax.annotate("", xy=(xmin, y_dim), xytext=(xmax, y_dim),
                    arrowprops=dict(arrowstyle="<|-|>", color="gray", lw=1.5))
        ax.text((xmin + xmax)/2, y_dim + y_range * 0.03, f"Span: {width:.2f} {self.model.unit_length}",
                ha="center", va="bottom", fontsize=10, color="darkblue", fontweight="bold")
        
        # 2. Vertical Height Dimension (Left)
        x_dim = xmin - (xmax - xmin) * 0.1
        ax.annotate("", xy=(x_dim, ymin), xytext=(x_dim, ymax),
                    arrowprops=dict(arrowstyle="<|-|>", color="gray", lw=1.5))
        ax.text(x_dim - (xmax - xmin) * 0.02, (ymin + ymax)/2, f"H: {height:.2f} {self.model.unit_length}",
                ha="right", va="center", rotation=90, fontsize=10, color="darkblue", fontweight="bold")

        # Adjust limits to fit dimensions
        ax.set_ylim(y_dim - y_range * 0.1, cur_ymax + y_range * 0.05)
        ax.set_xlim(x_dim - (xmax - xmin) * 0.1, xmax + (xmax - xmin) * 0.05)

    def scale_support_symbols(self, fig, scale=0.30):
        """Scale down support symbol patches."""
        ax = fig.gca()
        for patch in ax.patches:
            try:
                path = patch.get_path()
                verts = path.vertices
                if 3 <= len(verts) <= 8:  # Support shapes
                    centroid = verts.mean(axis=0)
                    path.vertices[:] = centroid + (verts - centroid) * scale
            except Exception:
                pass

    def _compute_bom(self) -> list[dict]:
        """
        Bill of Materials: group members by (category, profile).
        Categories: Top Chord, Bottom Chord, Vertical, Diagonal.
        Returns list of row-dicts with keys:
          category, profile, count, total_length, kg_per_m, total_weight
        """
        nodes = self.model.nodes_data
        elems = self.model.elements_data
        if not nodes or not elems:
            return []

        ymin = min(n["y"] for n in nodes)
        tol  = max((max(n["y"] for n in nodes) - ymin) * 0.05, 1e-6)

        def is_bottom(n):
            return n["y"] <= ymin + tol

        groups: dict = {}  # (category, profile) -> accumulator
        for el in elems:
            na = nodes[el["node_a"] - 1]
            nb = nodes[el["node_b"] - 1]
            dx = abs(nb["x"] - na["x"])
            dy = abs(nb["y"] - na["y"])
            length = math.sqrt(dx ** 2 + dy ** 2)
            profile = el["profile"]

            if is_bottom(na) and is_bottom(nb):
                cat = "Bottom Chord"
            elif not is_bottom(na) and not is_bottom(nb):
                cat = "Top Chord"
            elif dx < 1e-6:
                cat = "Vertical"
            else:
                cat = "Diagonal"

            key = (cat, profile)
            if key not in groups:
                groups[key] = {"category": cat, "profile": profile,
                               "count": 0, "total_length": 0.0}
            groups[key]["count"] += 1
            groups[key]["total_length"] += length

        # Attach weight info and sort by logical order
        cat_order = {"Top Chord": 0, "Bottom Chord": 1, "Vertical": 2, "Diagonal": 3}
        rows = []
        for (cat, profile), data in sorted(groups.items(),
                                           key=lambda x: cat_order.get(x[0][0], 9)):
            area = STEEL_PROFILES.get(profile, {}).get("Area", 0.0)  # cm²
            kg_per_m = area * 0.785          # steel density 7850 kg/m³
            data["kg_per_m"]     = kg_per_m
            data["total_weight"] = kg_per_m * data["total_length"]
            rows.append(data)
        return rows

    def _classify_members(self):
        """
        Classify each element as 'Top Chord', 'Bottom Chord', or 'Web'.
        Returns:
          types   : list[str]  – one per element (index matches elements_data)
          profiles: dict[str, set[str]]  – member_type → set of profile names
        """
        nodes = self.model.nodes_data
        elems = self.model.elements_data
        if not nodes or not elems:
            return [], {}

        ymin = min(n["y"] for n in nodes)
        tol  = max((max(n["y"] for n in nodes) - ymin) * 0.05, 1e-6)

        def is_bottom(n):
            return n["y"] <= ymin + tol

        types = []
        profiles: dict = {"Top Chord": set(), "Bottom Chord": set(), "Web": set()}
        for el in elems:
            na, nb = nodes[el["node_a"] - 1], nodes[el["node_b"] - 1]
            if is_bottom(na) and is_bottom(nb):
                t = "Bottom Chord"
            elif not is_bottom(na) and not is_bottom(nb):
                t = "Top Chord"
            else:
                t = "Web"
            types.append(t)
            profiles[t].add(el["profile"])
        return types, profiles

    def _add_member_legend(self, ax):
        """
        Draw a compact legend box at upper-left showing profile per member type.
        Uses matplotlib.legend.Legend directly so it never replaces an existing legend.
        """
        _, profiles = self._classify_members()
        colour_map = {
            "Top Chord":    "#E74C3C",
            "Bottom Chord": "#2980B9",
            "Web":          "#27AE60",
        }
        handles, labels = [], []
        for mtype, colour in colour_map.items():
            profs = profiles.get(mtype, set())
            label = f"{mtype}: {', '.join(sorted(profs)) if profs else '—'}"
            from matplotlib.lines import Line2D
            handles.append(Line2D([0], [0], color=colour, lw=3))
            labels.append(label)

        from matplotlib.legend import Legend
        leg = Legend(
            ax, handles, labels,
            loc="lower left",
            bbox_to_anchor=(0, 1.01),
            bbox_transform=ax.transAxes,
            fontsize=7,
            framealpha=0.88, edgecolor="#AAAAAA",
            title="Member Types", title_fontsize=7,
            borderaxespad=0,
        )
        ax.add_artist(leg)
        try:
            ax.figure.subplots_adjust(top=0.82)
        except Exception:
            pass

    def update_enhanced_plots(self):
        # Clear existing canvases
        for w in self.canvas_widgets: w.destroy()
        self.canvas_widgets.clear()
        if not self.ss: return

        ff = UNIT_FORCE_TO_KN[self.model.unit_force]
        lf = UNIT_LENGTH_TO_M[self.model.unit_length]
        member_types, _ = self._classify_members()

        def _enabled(key: str) -> bool:
            v = getattr(self, "_plot_vars", {}).get(key)
            return v.get() if v else True

        # 1. Structure Model
        if _enabled("show_structure"):
            fig_struct = self.ss.show_structure(verbosity=1, show=False)
            fig_struct.suptitle("1. Structure Model", fontsize=12, fontweight='bold')
            ax_struct = fig_struct.gca()
            xs_nd = [nd["x"] for nd in self.model.nodes_data]
            ys_nd = [nd["y"] for nd in self.model.nodes_data]
            _span1 = max(max(xs_nd) - min(xs_nd), max(ys_nd) - min(ys_nd), 1.0)
            _off1  = _span1 * 0.015
            for _i, _nd in enumerate(self.model.nodes_data):
                ax_struct.text(_nd["x"] + _off1, _nd["y"] + _off1, str(_i + 1),
                               fontsize=9, color="#334155", zorder=10)
            self._draw_load_arrows_on_ax(ax_struct, _span1)
            self._rescale_graph_labels(fig_struct, "structure")
            self.scale_support_symbols(fig_struct)
            self.add_dimensions(fig_struct)
            self._add_member_legend(ax_struct)
            self._add_to_right_panel(fig_struct)

        # 2. Axial Force Diagram
        if _enabled("show_axial"):
            fig_axial, ax = plt.subplots(figsize=(12, 8))
            try:
                elem_ids = list(self.ss.elements.keys())
                max_f = max([abs(self.ss.get_element_results(eid).get("N", 0.0)) for eid in elem_ids], default=1.0) or 1.0
                for elem_id, elem in self.ss.elements.items():
                    res = self.ss.get_element_results(elem_id)
                    force = res.get("N", 0.0)
                    start, end = elem['start'], elem['end']
                    color = '#C0392B' if force > 0.1 else ('#1A5276' if force < -0.1 else '#7F8C8D')
                    fill_color = '#FADBD8' if force > 0.1 else ('#D6EAF8' if force < -0.1 else '#F2F3F4')
                    lw = 3 + int(2 * abs(force) / max_f)
                    ax.plot([start[0], end[0]], [start[1], end[1]], color=color, linewidth=lw, alpha=0.9)
                    mid_x, mid_y = (start[0] + end[0])/2, (start[1] + end[1])/2
                    angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
                    if abs(angle) > 90: angle += 180
                    ax.text(mid_x, mid_y, f"{force / ff:.1f}", fontsize=8, fontweight='bold', ha='center', va='center',
                           color="#0F172A", rotation=angle,
                           bbox=dict(boxstyle="round,pad=0.2", fc=fill_color, ec=color, alpha=0.9))
                for node_id, node in self.ss.nodes.items():
                    ax.plot(node['x'], node['y'], 'ko', markersize=4, zorder=15)
                ax.set_aspect('equal')
                ax.grid(True, linestyle='--', alpha=0.4, color='#CBD5E1')
                ax.set_title("2. Axial Force Diagram", fontsize=14, fontweight='bold', color='#0F172A')
                ax.set_xlabel(f"X ({self.model.unit_length})", color='#334155')
                ax.set_ylabel(f"Y ({self.model.unit_length})", color='#334155')
                self._add_member_legend(ax)
                self._add_to_right_panel(fig_axial)
            except Exception:
                plt.close(fig_axial)

        # 3. Displacement Diagram with Deflection Check
        if _enabled("show_disp"):
            fig_disp = self.ss.show_displacement(show=False)
            ax_disp = fig_disp.gca()
            fig_disp.suptitle("3. Displacement Diagram (Scaled)", fontsize=12, fontweight='bold')
            displacements = self.ss.displacements
            for node_id, node in self.ss.nodes.items():
                if node_id in displacements:
                    dy = displacements[node_id]['dy']
                    if abs(dy * 1000) > 0.01:
                        ax_disp.text(node['x'], node['y'], f"N{node_id}: {dy*1000:.1f}mm",
                                    fontsize=7, color='purple', ha='center', va='bottom')
            xs_all = [n["x"] for n in self.model.nodes_data]
            span_m = (max(xs_all) - min(xs_all)) * lf
            max_dy_mm = max(
                (abs(displacements[nid]["dy"]) * 1000 for nid in self.ss.nodes if nid in displacements),
                default=0.0,
            )
            if span_m > 0:
                lim_240 = span_m * 1000 / 240
                lim_360 = span_m * 1000 / 360
                lim_420 = span_m * 1000 / 420
                def _check(limit, val): return "OK" if val <= limit else "FAIL"
                defl_text = (
                    f"Span L = {span_m:.2f} m   |   Max δ = {max_dy_mm:.2f} mm\n"
                    f"L/240 = {lim_240:.1f} mm  [{_check(lim_240, max_dy_mm)}]\n"
                    f"L/360 = {lim_360:.1f} mm  [{_check(lim_360, max_dy_mm)}]\n"
                    f"L/420 = {lim_420:.1f} mm  [{_check(lim_420, max_dy_mm)}]"
                )
                all_ok = max_dy_mm <= lim_240
                bg_color = "#E8F8F5" if all_ok else "#FDEDEC"
                ax_disp.text(0.99, 0.98, defl_text, transform=ax_disp.transAxes,
                    fontsize=8, va="top", ha="right", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.5", fc=bg_color,
                              ec="#27AE60" if all_ok else "#E74C3C", alpha=0.9))
            self._add_member_legend(ax_disp)
            self.scale_support_symbols(fig_disp)
            self.add_dimensions(fig_disp)
            self._add_to_right_panel(fig_disp)

        # 4. Utilization Diagram
        if _enabled("show_util"):
            fig_util, ax = plt.subplots(figsize=(12, 8))
            try:
                if self.analysis_results:
                    for i, result in enumerate(self.analysis_results):
                        elem = self.ss.elements[i + 1]
                        util = result["utilization"]
                        color = '#1D8348' if util <= 0.6 else ('#D4AC0D' if util <= 0.9 else ('#E67E22' if util <= 1.0 else '#C0392B'))
                        ax.plot([elem['start'][0], elem['end'][0]], [elem['start'][1], elem['end'][1]],
                                color=color, linewidth=2 + min(util * 3, 6))
                        mid_x = (elem['start'][0] + elem['end'][0]) / 2
                        mid_y = (elem['start'][1] + elem['end'][1]) / 2
                        ax.text(mid_x, mid_y, f"{util:.2f}", fontsize=9, fontweight='bold',
                                ha='center', color='#0F172A',
                                bbox=dict(boxstyle="round,pad=0.2", fc='#FFFFFF', ec=color, alpha=0.9))
                    ax.set_aspect('equal')
                    ax.grid(True, linestyle='--', alpha=0.4, color='#CBD5E1')
                    ax.set_title("4. Member Utilization Diagram", fontsize=14, fontweight='bold', color='#0F172A')
                    ax.set_xlabel(f"X ({self.model.unit_length})", color='#334155')
                    ax.set_ylabel(f"Y ({self.model.unit_length})", color='#334155')
                    self._add_member_legend(ax)
                    self._add_to_right_panel(fig_util)
                else:
                    plt.close(fig_util)
            except Exception:
                plt.close(fig_util)

        # 5. Reaction Forces Diagram
        if _enabled("show_react"):
            try:
                rf = self.ss.reaction_forces
                if rf:
                    fig_react, ax = plt.subplots(figsize=(12, 8))
                    for elem in self.ss.elements.values():
                        ax.plot([elem['start'][0], elem['end'][0]],
                                [elem['start'][1], elem['end'][1]],
                                color='#94A3B8', linewidth=2, zorder=1)
                    for node in self.ss.nodes.values():
                        ax.plot(node['x'], node['y'], 'o', color='#7F8C8D',
                                markersize=5, zorder=2)
                    xs = [n['x'] for n in self.ss.nodes.values()]
                    ys = [n['y'] for n in self.ss.nodes.values()]
                    span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
                    ff = UNIT_FORCE_TO_KN[self.model.unit_force]
                    for nid, node_rf in rf.items():
                        x = node_rf['x']
                        y = node_rf['y']
                        rfx = -node_rf['Fx']
                        rfy = -node_rf['Fy']
                        fixed_len = span * 0.12

                        def _draw_arrow(dx, dy, val, color, label_offset,
                                        _x=x, _y=y, _fl=fixed_len):
                            if abs(val) < 0.01:
                                return
                            if dy != 0:
                                tail_xy = (_x, _y - _fl)
                                head_xy = (_x, _y)
                                lx = _x + label_offset[0]
                                ly = _y - _fl + label_offset[1]
                            else:
                                ddx = (dx / abs(dx)) * _fl
                                tail_xy = (_x, _y)
                                head_xy = (_x + ddx, _y)
                                lx = _x + ddx + label_offset[0]
                                ly = _y + label_offset[1]
                            ax.annotate('', xy=head_xy, xytext=tail_xy,
                                arrowprops=dict(arrowstyle='->', color=color,
                                               lw=2.5, mutation_scale=18), zorder=5)
                            ax.text(lx, ly,
                                    f"{abs(val) / ff:.2f} {self.model.unit_force}",
                                    fontsize=9, fontweight='bold', color=color,
                                    ha='center', va='center',
                                    bbox=dict(boxstyle='round,pad=0.25',
                                              fc='white', ec=color, alpha=0.85), zorder=6)

                        offset_x = span * 0.03
                        offset_y = span * 0.06
                        _draw_arrow(rfx, 0,   rfx, '#E74C3C', (0,  offset_y))
                        _draw_arrow(0,   rfy, rfy, '#2980B9', (offset_x, 0))
                        ax.text(x, y - span * 0.06, f"N{nid}",
                                fontsize=8, color='#334155', ha='center', zorder=6)

                    from matplotlib.lines import Line2D
                    legend_elems = [
                        Line2D([0], [0], color='#E74C3C', lw=2, label='Fx (Horizontal)'),
                        Line2D([0], [0], color='#2980B9', lw=2, label='Fy (Vertical)'),
                    ]
                    ax.legend(handles=legend_elems, loc='upper right', fontsize=9)
                    self._add_member_legend(ax)
                    ax.set_aspect('equal')
                    ax.grid(True, linestyle='--', alpha=0.4, color='#CBD5E1')
                    ax.set_title("5. Reaction Forces Diagram", fontsize=14, fontweight='bold', color='#0F172A')
                    ax.set_xlabel(f"X ({self.model.unit_length})", color='#334155')
                    ax.set_ylabel(f"Y ({self.model.unit_length})", color='#334155')
                    self._add_to_right_panel(fig_react)
            except Exception:
                pass

    def _add_to_right_panel(self, fig):
        _force_light_fig(fig)
        canvas = FigureCanvasTkAgg(fig, master=self.right_panel)
        canvas.draw()
        plt.close(fig)

        # Add Toolbar
        toolbar_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        toolbar_frame.pack(fill="x", padx=10)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side="left")
        
        w = canvas.get_tk_widget()
        w.pack(fill="x", padx=10, pady=(0, 20))
        self.canvas_widgets.extend([w, toolbar_frame])

    def show_enhanced_results(self):
        """Enhanced results display with comprehensive member checks"""
        self.update_idletasks()
        for w in self.tab_res.winfo_children():
            try: w.destroy()
            except Exception: pass
        
        if not self.ss or not self.analysis_results:
            ctk.CTkLabel(self.tab_res, text="No analysis results available. Run analysis first.", 
                        font=TYPO_SCALE["body"]).pack(pady=50)
            return
        
        # Header
        header = ctk.CTkFrame(self.tab_res, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        title_frame = ctk.CTkFrame(header, fg_color=COLOR_PALETTE["primary"])
        title_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(title_frame, text="🔬 STRUCTURAL ANALYSIS REPORT v3.0", 
                     font=TYPO_SCALE["h2"], text_color="white").pack(pady=10)
        
        info_frame = ctk.CTkFrame(header, fg_color=COLOR_PALETTE["surface"])
        info_frame.pack(fill="x", pady=5)
        
        info_text = f"Project: {self.model.project_data['name']} | Method: {self.model.design_method} | Combination: {self.model.selected_combo}"
        ctk.CTkLabel(info_frame, text=info_text, font=TYPO_SCALE["small"]).pack(pady=5)
        
        # Results table
        table_frame = ctk.CTkScrollableFrame(self.tab_res, height=400)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Table headers
        headers_frame = ctk.CTkFrame(table_frame, fg_color=COLOR_PALETTE["secondary"])
        headers_frame.pack(fill="x", pady=2)
        
        fu = self.model.unit_force
        ff_res = UNIT_FORCE_TO_KN[fu]
        headers = ["Member", "Profile", f"Force ({fu})", "Type", "Utilization", "Status", "Properties"]
        widths = [60, 140, 80, 80, 80, 60, 200]
        
        for header, width in zip(headers, widths):
            ctk.CTkLabel(headers_frame, text=header, width=width, 
                        font=TYPO_SCALE["small"]).pack(side="left", padx=2, pady=5)
        
        # Results rows
        for result in self.analysis_results:
            row_color = COLOR_PALETTE["danger"] if result["status"] == "FAIL" else COLOR_PALETTE["surface"]
            row_frame = ctk.CTkFrame(table_frame, fg_color=row_color)
            row_frame.pack(fill="x", pady=1)
            
            # Member ID
            ctk.CTkLabel(row_frame, text=result["member_id"], width=60, 
                        font=TYPO_SCALE["mono"]).pack(side="left", padx=2, pady=3)
            
            # Profile
            ctk.CTkLabel(row_frame, text=result["profile"], width=140, 
                        font=TYPO_SCALE["small"]).pack(side="left", padx=2, pady=3)
            
            # Force — convert from kN to display unit
            force_display = result['force'] / ff_res
            force_text = f"{force_display:.2f}"
            ctk.CTkLabel(row_frame, text=force_text, width=80,
                        font=TYPO_SCALE["mono"]).pack(side="left", padx=2, pady=3)
            
            # Type
            ctk.CTkLabel(row_frame, text=result["type"], width=80, 
                        font=TYPO_SCALE["small"]).pack(side="left", padx=2, pady=3)
            
            # Utilization
            util_text = f"{result['utilization']:.2f}"
            util_color = COLOR_PALETTE["danger"] if result['utilization'] > 1.0 else COLOR_PALETTE["success"]
            util_label = ctk.CTkLabel(row_frame, text=util_text, width=80, 
                                    font=TYPO_SCALE["mono"], text_color=util_color)
            util_label.pack(side="left", padx=2, pady=3)
            
            # Status
            status_text = "✅ OK" if result["status"] == "OK" else "❌ FAIL"
            ctk.CTkLabel(row_frame, text=status_text, width=60, 
                        font=TYPO_SCALE["small"]).pack(side="left", padx=2, pady=3)
            
            # Properties
            if "slenderness" in result:
                props_text = f"σ={result.get('stress', 0):.1f} MPa, λ={result.get('slenderness', 0):.1f}"
            else:
                props_text = f"σ={result.get('stress', 0):.1f} MPa"
            
            ctk.CTkLabel(row_frame, text=props_text, width=200, 
                        font=TYPO_SCALE["small"]).pack(side="left", padx=2, pady=3)
        
        # Summary
        summary_frame = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["surface"])
        summary_frame.pack(fill="x", padx=10, pady=10)
        
        total_members = len(self.analysis_results)
        failed_members = sum(1 for r in self.analysis_results if r["status"] == "FAIL")
        max_utilization = max((r["utilization"] for r in self.analysis_results), default=0)
        
        summary_text = f"📊 Summary: {total_members} members analyzed | {failed_members} failures | Max utilization: {max_utilization:.2f}"
        ctk.CTkLabel(summary_frame, text=summary_text, font=TYPO_SCALE["body"]).pack(pady=10)
        
        if failed_members > 0:
            warning_frame = ctk.CTkFrame(summary_frame, fg_color=COLOR_PALETTE["warning"])
            warning_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(warning_frame, text="⚠️ WARNING: Some members exceed capacity. Consider larger sections or design modifications.",
                        font=TYPO_SCALE["small"]).pack(pady=5)

        # ── All-combo utilization summary ────────────────────────────────
        all_combo_res = getattr(self, "all_combo_results", {})
        if all_combo_res:
            combo_outer = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["surface"], corner_radius=8)
            combo_outer.pack(fill="x", padx=10, pady=(4, 6))
            combo_title = ctk.CTkFrame(combo_outer, fg_color=COLOR_PALETTE["secondary"], corner_radius=6)
            combo_title.pack(fill="x", padx=6, pady=(6, 4))
            ctk.CTkLabel(combo_title, text="Utilization Summary — All Load Combinations",
                         font=TYPO_SCALE["h3"], text_color="#FFFFFF").pack(side="left", padx=12, pady=6)

            combo_scroll = ctk.CTkScrollableFrame(combo_outer, fg_color="transparent", height=200)
            combo_scroll.pack(fill="x", padx=6, pady=(0, 6))

            # Header row
            hdr_row = ctk.CTkFrame(combo_scroll, fg_color=COLOR_PALETTE["header_bar"])
            hdr_row.pack(fill="x", pady=(0, 2))
            ctk.CTkLabel(hdr_row, text="Member", width=70, font=TYPO_SCALE["small"],
                         text_color="#FFFFFF").pack(side="left", padx=4, pady=4)
            combo_names = list(all_combo_res.keys())
            for cn in combo_names:
                ctk.CTkLabel(hdr_row, text=cn, width=max(80, len(cn)*7),
                             font=TYPO_SCALE["small"], text_color="#FFFFFF",
                             wraplength=100).pack(side="left", padx=3, pady=4)
            ctk.CTkLabel(hdr_row, text="MAX", width=65, font=TYPO_SCALE["small"],
                         text_color="#F59E0B").pack(side="left", padx=3, pady=4)

            # One row per member
            n_members = len(self.analysis_results)
            for mi in range(n_members):
                alt = mi % 2 == 0
                r_fg = COLOR_PALETTE["row_alt"] if alt else COLOR_PALETTE["surface"]
                r = ctk.CTkFrame(combo_scroll, fg_color=r_fg)
                r.pack(fill="x", pady=1)
                ctk.CTkLabel(r, text=f"E{mi+1}", width=70,
                             font=TYPO_SCALE["mono"],
                             text_color=COLOR_PALETTE["text_primary"]).pack(side="left", padx=4, pady=3)
                vals = []
                for cn in combo_names:
                    res_list = all_combo_res.get(cn, [])
                    u = res_list[mi]["utilization"] if mi < len(res_list) else 0.0
                    vals.append(u)
                    uc = COLOR_PALETTE["danger"] if u > 1.0 else (COLOR_PALETTE["warning"] if u > 0.8 else COLOR_PALETTE["success"])
                    ctk.CTkLabel(r, text=f"{u:.2f}", width=max(80, len(cn)*7),
                                 font=TYPO_SCALE["mono"], text_color=uc).pack(side="left", padx=3, pady=3)
                mx = max(vals) if vals else 0.0
                mc = COLOR_PALETTE["danger"] if mx > 1.0 else (COLOR_PALETTE["warning"] if mx > 0.8 else COLOR_PALETTE["success"])
                ctk.CTkLabel(r, text=f"{mx:.2f}", width=65,
                             font=TYPO_SCALE["h3"], text_color=mc).pack(side="left", padx=3, pady=3)

        # ── Bill of Materials ────────────────────────────────────────────
        bom_rows = self._compute_bom()
        if bom_rows:
            lu = self.model.unit_length
            lf = UNIT_LENGTH_TO_M[lu]

            bom_outer = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["surface"], corner_radius=8)
            bom_outer.pack(fill="x", padx=10, pady=(6, 10))

            # Title bar
            bom_title = ctk.CTkFrame(bom_outer, fg_color=COLOR_PALETTE["header_bar"], corner_radius=6)
            bom_title.pack(fill="x", padx=6, pady=(6, 4))
            ctk.CTkLabel(bom_title,
                         text="Bill of Materials  —  Steel Quantity Takeoff",
                         font=TYPO_SCALE["h3"], text_color="#FFFFFF").pack(side="left", padx=12, pady=6)

            # Column headers
            CAT_COLORS = {
                "Top Chord":    "#E74C3C",
                "Bottom Chord": "#2980B9",
                "Vertical":     "#27AE60",
                "Diagonal":     "#F39C12",
            }
            bom_hdr = ctk.CTkFrame(bom_outer, fg_color=COLOR_PALETTE["secondary"])
            bom_hdr.pack(fill="x", padx=6, pady=(0, 2))
            for txt, w in [("Category", 120), ("Profile", 150), ("Qty", 40),
                           (f"Length ({lu})", 90), ("kg/m", 60), ("Weight (kg)", 90)]:
                ctk.CTkLabel(bom_hdr, text=txt, width=w, font=TYPO_SCALE["small"],
                             text_color="#FFFFFF").pack(side="left", padx=3, pady=4)

            # Data rows
            total_len = 0.0
            total_wt  = 0.0
            for row in bom_rows:
                r_fg = COLOR_PALETTE["row_alt"] if bom_rows.index(row) % 2 == 0 else COLOR_PALETTE["surface"]
                r = ctk.CTkFrame(bom_outer, fg_color=r_fg)
                r.pack(fill="x", padx=6, pady=1)

                # Colour swatch for category
                cat_color = CAT_COLORS.get(row["category"], COLOR_PALETTE["text_secondary"])
                ctk.CTkLabel(r, text="█", width=12,
                             font=TYPO_SCALE["small"], text_color=cat_color).pack(side="left", padx=(4, 0))
                ctk.CTkLabel(r, text=row["category"], width=108,
                             font=TYPO_SCALE["small"],
                             text_color=COLOR_PALETTE["text_primary"]).pack(side="left", padx=2, pady=3)
                ctk.CTkLabel(r, text=row["profile"], width=150,
                             font=TYPO_SCALE["mono"],
                             text_color=COLOR_PALETTE["text_primary"]).pack(side="left", padx=2, pady=3)
                ctk.CTkLabel(r, text=str(row["count"]), width=40,
                             font=TYPO_SCALE["mono"],
                             text_color=COLOR_PALETTE["text_primary"]).pack(side="left", padx=2, pady=3)
                disp_len = row["total_length"] / lf
                ctk.CTkLabel(r, text=f"{disp_len:.2f}", width=90,
                             font=TYPO_SCALE["mono"],
                             text_color=COLOR_PALETTE["text_primary"]).pack(side="left", padx=2, pady=3)
                ctk.CTkLabel(r, text=f"{row['kg_per_m']:.2f}", width=60,
                             font=TYPO_SCALE["mono"],
                             text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=2, pady=3)
                ctk.CTkLabel(r, text=f"{row['total_weight']:.1f}", width=90,
                             font=TYPO_SCALE["mono"],
                             text_color=COLOR_PALETTE["accent"]).pack(side="left", padx=2, pady=3)
                total_len += row["total_length"]
                total_wt  += row["total_weight"]

            # Totals row
            tot = ctk.CTkFrame(bom_outer, fg_color=COLOR_PALETTE["header_bar"])
            tot.pack(fill="x", padx=6, pady=(2, 6))
            ctk.CTkLabel(tot, text="", width=12).pack(side="left", padx=4)
            ctk.CTkLabel(tot, text="TOTAL", width=108, font=TYPO_SCALE["h3"],
                         text_color="#FFFFFF").pack(side="left", padx=2, pady=4)
            ctk.CTkLabel(tot, text="", width=150).pack(side="left", padx=2)
            ctk.CTkLabel(tot, text=str(sum(r["count"] for r in bom_rows)), width=40,
                         font=TYPO_SCALE["h3"], text_color="#FFFFFF").pack(side="left", padx=2, pady=4)
            ctk.CTkLabel(tot, text=f"{total_len / lf:.2f}", width=90,
                         font=TYPO_SCALE["h3"], text_color="#FFFFFF").pack(side="left", padx=2, pady=4)
            ctk.CTkLabel(tot, text="", width=60).pack(side="left", padx=2)
            ctk.CTkLabel(tot, text=f"{total_wt:.1f}", width=90,
                         font=TYPO_SCALE["h3"], text_color="#F59E0B").pack(side="left", padx=2, pady=4)

    def _draw_load_arrows_on_ax(self, ax, span):
        """Draw per-case coloured load arrows (Fx horizontal, Fy vertical) on existing axes."""
        arrow_len  = max(span * 0.13, 0.1)
        lbl_off    = span * 0.04

        for ld in self.model.loads_data:
            if not (1 <= ld["node_id"] <= len(self.model.nodes_data)):
                continue
            nd    = self.model.nodes_data[ld["node_id"] - 1]
            x, y  = nd["x"], nd["y"]
            color = CASE_COLORS.get(ld.get("case", "DL"), "#555555")
            fx    = ld.get("fx", 0.0)
            fy    = ld.get("fy", 0.0)

            if abs(fx) > 1e-6:
                sign = 1 if fx > 0 else -1
                # tail offset from node in opposite direction, head at node
                ax.annotate("", xy=(x, y), xytext=(x - sign * arrow_len, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=2, mutation_scale=14))
                ax.text(x - sign * (arrow_len + lbl_off), y + lbl_off * 0.6,
                    f"Fx={fx:.0f}", fontsize=7, color=color,
                    ha="center", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, alpha=0.85))

            if abs(fy) > 1e-6:
                sign = 1 if fy > 0 else -1
                ax.annotate("", xy=(x, y), xytext=(x, y - sign * arrow_len),
                    arrowprops=dict(arrowstyle="->", color=color, lw=2, mutation_scale=14))
                ax.text(x + lbl_off * 0.6, y - sign * (arrow_len + lbl_off),
                    f"Fy={fy:.0f}", fontsize=7, color=color,
                    ha="left", va="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, alpha=0.85))

        # Legend per case
        from matplotlib.lines import Line2D
        from matplotlib.legend import Legend
        present = {ld.get("case", "DL") for ld in self.model.loads_data}
        handles = [Line2D([0], [0], color=CASE_COLORS.get(c, "#555"), lw=2.5, label=c)
                   for c in ["DL", "LL", "WL", "SL"] if c in present]
        if handles:
            leg = Legend(ax, handles, [h.get_label() for h in handles],
                         loc="lower left", bbox_to_anchor=(0, 1.01),
                         bbox_transform=ax.transAxes,
                         fontsize=7, title="Load Cases", title_fontsize=7,
                         framealpha=0.88, edgecolor="#AAAAAA", borderaxespad=0)
            ax.add_artist(leg)
            try:
                ax.figure.subplots_adjust(top=0.80)
            except Exception:
                pass

    def _remap_node_labels(self, fig, ss):
        """Replace anastruct internal node IDs with model 1-based indices in a figure."""
        coord_to_model = {}
        for i, nd in enumerate(self.model.nodes_data):
            coord_to_model[(round(nd["x"], 6), round(nd["y"], 6))] = i + 1
        ana_to_model = {}
        for ana_id, ana_nd in ss.nodes.items():
            key = (round(ana_nd["x"], 6), round(ana_nd["y"], 6))
            if key in coord_to_model:
                ana_to_model[ana_id] = coord_to_model[key]
        if not ana_to_model:
            return
        for ax in fig.get_axes():
            for txt in ax.texts:
                try:
                    val = int(txt.get_text())
                    if val in ana_to_model:
                        txt.set_text(str(ana_to_model[val]))
                except (ValueError, AttributeError):
                    pass

    def update_structure_preview(self, temp_ss):
        """Update structure preview visualization"""
        try:
            # Clear existing preview canvases
            for w in self.canvas_widgets:
                w.destroy()
            self.canvas_widgets.clear()

            # show_structure with no loads on temp_ss → only members/supports/node labels
            fig_struct = temp_ss.show_structure(show=False)
            fig_struct.suptitle("Live Structure Preview  (drag nodes to reposition)",
                                fontsize=11, fontweight='bold')
            self._remap_node_labels(fig_struct, temp_ss)

            # Draw per-case load arrows on top
            ax = fig_struct.gca()
            xs = [nd["x"] for nd in self.model.nodes_data]
            ys = [nd["y"] for nd in self.model.nodes_data]
            span = max(max(xs) - min(xs), max(ys) - min(ys), 1.0) if xs else 1.0
            self._draw_load_arrows_on_ax(ax, span)

            # ── Embed canvas with drag support ───────────────────────────
            _force_light_fig(fig_struct)
            canvas = FigureCanvasTkAgg(fig_struct, master=self.right_panel)
            canvas.draw()

            self._drag_node_idx = None
            self._drag_ax = ax

            def _on_press(event):
                if event.inaxes != ax or event.xdata is None:
                    return
                # Find nearest model node
                best, best_d = None, float("inf")
                for idx, nd in enumerate(self.model.nodes_data):
                    d = math.hypot(nd["x"] - event.xdata, nd["y"] - event.ydata)
                    if d < best_d:
                        best_d, best = d, idx
                if best is not None and best_d < span * 0.08:
                    self._drag_node_idx = best

            def _on_motion(event):
                if self._drag_node_idx is None or event.inaxes != ax or event.xdata is None:
                    return
                nd = self.model.nodes_data[self._drag_node_idx]
                nd["x"] = round(event.xdata, 3)
                nd["y"] = round(event.ydata, 3)
                # Update node entry widgets if they exist
                try:
                    e = self.node_entries[self._drag_node_idx]
                    e["x"].delete(0, "end"); e["x"].insert(0, f"{nd['x']:.3f}")
                    e["y"].delete(0, "end"); e["y"].insert(0, f"{nd['y']:.3f}")
                except Exception:
                    pass
                canvas.draw_idle()

            def _on_release(event):
                if self._drag_node_idx is not None:
                    self.model.save_state()
                    self._drag_node_idx = None
                    self.schedule_preview_update()

            canvas.mpl_connect("button_press_event",   _on_press)
            canvas.mpl_connect("motion_notify_event",  _on_motion)
            canvas.mpl_connect("button_release_event", _on_release)

            self._preview_canvas_ref = canvas
            plt.close(fig_struct)

            toolbar_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
            toolbar_frame.pack(fill="x", padx=10)
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
            toolbar.update()
            toolbar.pack(side="left")

            w = canvas.get_tk_widget()
            w.pack(fill="x", padx=10, pady=(0, 20))
            self.canvas_widgets.extend([w, toolbar_frame])

        except Exception as e:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.text(0.5, 0.5, f"Preview Error: {str(e)}", ha="center", va="center",
                   transform=ax.transAxes, fontsize=12, color='red')
            ax.set_title("Structure Preview")
            self._add_to_right_panel(fig)
        
    def draw_project_tab(self):
        """Enhanced project information tab"""
        self.update_idletasks()
        for w in self.tab_proj.winfo_children():
            try: w.destroy()
            except Exception: pass
        
        # Header
        header = ctk.CTkFrame(self.tab_proj, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="📋 Project Information", 
                     font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["text_primary"]).pack()
        
        # Project details
        details_frame = ctk.CTkScrollableFrame(self.tab_proj, fg_color="transparent")
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.project_entries = {}
        for key, value in self.model.project_data.items():
            row_frame = ctk.CTkFrame(details_frame, fg_color=COLOR_PALETTE["surface"])
            row_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(row_frame, text=f"{key.title()}:", width=120, 
                        font=TYPO_SCALE["body"]).pack(side="left", padx=10, pady=10)
            
            entry = ctk.CTkEntry(row_frame, width=300, font=TYPO_SCALE["body"])
            entry.insert(0, str(value))
            entry.pack(side="left", padx=10, pady=10)
            
            self.project_entries[key] = entry
        
        # Self-weight toggle
        sw_frame = ctk.CTkFrame(self.tab_proj, fg_color=COLOR_PALETTE["surface"])
        sw_frame.pack(fill="x", padx=10, pady=(0, 6))
        self._sw_var = ctk.BooleanVar(value=getattr(self.model, "self_weight_enabled", False))
        def _on_sw(val=None):
            self.model.self_weight_enabled = self._sw_var.get()
        ctk.CTkCheckBox(sw_frame, text="Include self-weight (DL, distributed to nodes)",
                        variable=self._sw_var, command=_on_sw,
                        font=TYPO_SCALE["body"]).pack(anchor="w", padx=12, pady=8)
        ctk.CTkLabel(sw_frame,
                     text="Uses Area×7850 kg/m³ × g = Fy per node. Re-run analysis to apply.",
                     font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).pack(anchor="w", padx=24, pady=(0, 8))

        # Units section
        units_frame = ctk.CTkFrame(self.tab_proj, fg_color=COLOR_PALETTE["surface"])
        units_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(units_frame, text="Units", font=TYPO_SCALE["h3"]).pack(pady=10)

        # Fixed input unit notice
        notice = ctk.CTkFrame(units_frame, fg_color=COLOR_PALETTE["secondary"], corner_radius=8)
        notice.pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkLabel(notice, text="Input units (fixed)",
                     font=TYPO_SCALE["small"], text_color=COLOR_PALETTE["text_secondary"]).pack(pady=(6, 0))
        ctk.CTkLabel(notice,
                     text="Node coordinates: m     |     Loads: kN     |     Stress: MPa",
                     font=TYPO_SCALE["body"], text_color=COLOR_PALETTE["text_primary"]).pack(pady=(0, 6))

        units_grid = ctk.CTkFrame(units_frame, fg_color="transparent")
        units_grid.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(units_grid, text="Display force:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.force_unit_var = ctk.StringVar(value=self.model.unit_force)
        ctk.CTkOptionMenu(units_grid, values=["kN", "N", "tf", "kgf", "kip"],
                          variable=self.force_unit_var,
                          command=lambda v: setattr(self.model, "unit_force", v)).grid(
                          row=0, column=1, padx=5, pady=5)

        ctk.CTkLabel(units_grid, text="Display length:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.length_unit_var = ctk.StringVar(value=self.model.unit_length)
        ctk.CTkOptionMenu(units_grid, values=["m", "cm", "mm", "in", "ft"],
                          variable=self.length_unit_var,
                          command=lambda v: setattr(self.model, "unit_length", v)).grid(
                          row=1, column=1, padx=5, pady=5)

        ctk.CTkLabel(units_grid,
                     text="* Changes display labels only. Re-run analysis to refresh plots.",
                     font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).grid(
                     row=2, column=0, columnspan=2, padx=5, pady=(2, 8), sticky="w")

        # Custom section calculator button
        ctk.CTkButton(self.tab_proj,
                      text="Custom Section Calculator",
                      height=32, corner_radius=6,
                      fg_color=COLOR_PALETTE["accent"],
                      font=TYPO_SCALE["body"],
                      command=self.open_section_calculator).pack(
                          fill="x", padx=10, pady=(6, 10))

    def open_section_calculator(self):
        """Popup dialog to compute section properties and add a custom profile."""
        win = ctk.CTkToplevel(self)
        win.title("Custom Section Calculator")
        win.geometry("480x580")
        win.grab_set()

        ctk.CTkLabel(win, text="Custom Section Property Calculator",
                     font=TYPO_SCALE["h3"]).pack(pady=(12, 4))

        # Shape selector
        shape_var = ctk.StringVar(value="RHS/Box")
        shapes = ["RHS/Box", "CHS/Pipe", "I-Beam", "Angle"]
        shape_row = ctk.CTkFrame(win, fg_color="transparent")
        shape_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(shape_row, text="Shape:", width=100).pack(side="left")
        ctk.CTkOptionMenu(shape_row, values=shapes, variable=shape_var,
                          width=160).pack(side="left", padx=6)

        # Dimension fields
        dim_frame = ctk.CTkFrame(win, fg_color=COLOR_PALETTE["surface"], corner_radius=8)
        dim_frame.pack(fill="x", padx=16, pady=8)
        dim_entries: dict[str, ctk.CTkEntry] = {}

        def _make_field(label, key, default=""):
            r = ctk.CTkFrame(dim_frame, fg_color="transparent")
            r.pack(fill="x", padx=10, pady=3)
            ctk.CTkLabel(r, text=label, width=160, font=TYPO_SCALE["body"],
                         anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, width=120, font=TYPO_SCALE["mono"])
            e.insert(0, str(default))
            e.pack(side="left", padx=6)
            dim_entries[key] = e
            return e

        def _rebuild_dims(*_):
            for w in dim_frame.winfo_children():
                w.destroy()
            dim_entries.clear()
            s = shape_var.get()
            if s == "RHS/Box":
                _make_field("Width b (mm):", "b", 100)
                _make_field("Height h (mm):", "h", 100)
                _make_field("Thickness t (mm):", "t", 4)
            elif s == "CHS/Pipe":
                _make_field("Outer diameter D (mm):", "D", 114.3)
                _make_field("Thickness t (mm):", "t", 4.5)
            elif s == "I-Beam":
                _make_field("Total height H (mm):", "H", 200)
                _make_field("Flange width bf (mm):", "bf", 100)
                _make_field("Flange thickness tf (mm):", "tf", 8)
                _make_field("Web thickness tw (mm):", "tw", 5)
            elif s == "Angle":
                _make_field("Leg a (mm):", "a", 75)
                _make_field("Leg b (mm):", "b", 75)
                _make_field("Thickness t (mm):", "t", 6)

        shape_var.trace_add("write", _rebuild_dims)
        _rebuild_dims()

        # Grade selector
        grade_var = ctk.StringVar(value="SS400")
        gr = ctk.CTkFrame(win, fg_color="transparent")
        gr.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(gr, text="Steel Grade:", width=100).pack(side="left")
        ctk.CTkOptionMenu(gr, values=list(STEEL_GRADES.keys()), variable=grade_var,
                          width=120).pack(side="left", padx=6)

        # Profile name
        name_row = ctk.CTkFrame(win, fg_color="transparent")
        name_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(name_row, text="Profile name:", width=100).pack(side="left")
        name_entry = ctk.CTkEntry(name_row, width=240, font=TYPO_SCALE["mono"])
        name_entry.insert(0, "Custom-1")
        name_entry.pack(side="left", padx=6)

        # Result display
        result_box = ctk.CTkFrame(win, fg_color=COLOR_PALETTE["surface"], corner_radius=8)
        result_box.pack(fill="x", padx=16, pady=8)
        result_label = ctk.CTkLabel(result_box, text="Press Calculate to see results.",
                                    font=TYPO_SCALE["mono"], justify="left", wraplength=430)
        result_label.pack(padx=12, pady=10)

        def _calculate():
            import math as _m
            s = shape_var.get()
            try:
                d = {k: float(v.get()) for k, v in dim_entries.items()}
            except ValueError:
                result_label.configure(text="Invalid input — numbers only.")
                return
            try:
                if s == "RHS/Box":
                    b, h, t = d["b"], d["h"], d["t"]
                    A  = (b*h - (b-2*t)*(h-2*t)) / 100          # mm² → cm²
                    Ix = (b*h**3 - (b-2*t)*(h-2*t)**3) / 12 / 1e4  # mm⁴ → cm⁴
                    Iy = (h*b**3 - (h-2*t)*(b-2*t)**3) / 12 / 1e4
                elif s == "CHS/Pipe":
                    D, t = d["D"], d["t"]
                    di = D - 2*t
                    A  = _m.pi/4 * (D**2 - di**2) / 100
                    Ix = _m.pi/64 * (D**4 - di**4) / 1e4
                    Iy = Ix
                elif s == "I-Beam":
                    H, bf, tf, tw = d["H"], d["bf"], d["tf"], d["tw"]
                    hw = H - 2*tf
                    A  = (2*bf*tf + hw*tw) / 100
                    Ix = (bf*H**3 - (bf-tw)*hw**3) / 12 / 1e4
                    Iy = (2*tf*bf**3/12 + hw*tw**3/12) / 1e4
                elif s == "Angle":
                    a, b, t = d["a"], d["b"], d["t"]
                    A = (a + b - t) * t / 100
                    Ix = (t*a**3/3 + (b-t)*t**3/12) / 1e4
                    Iy = (t*b**3/3 + (a-t)*t**3/12) / 1e4
                else:
                    return
                rx = _m.sqrt(Ix / A)
                ry = _m.sqrt(Iy / A)
                _calc_result.update({"A": A, "Ix": Ix, "Iy": Iy, "rx": rx, "ry": ry})
                result_label.configure(
                    text=f"A  = {A:.3f} cm²\n"
                         f"Ix = {Ix:.2f} cm⁴    rx = {rx:.3f} cm\n"
                         f"Iy = {Iy:.2f} cm⁴    ry = {ry:.3f} cm\n"
                         f"kg/m = {A * 0.785:.2f}")
            except Exception as ex:
                result_label.configure(text=f"Calc error: {ex}")

        _calc_result: dict = {}

        def _add_profile():
            if not _calc_result:
                messagebox.showwarning("Calculate first", "Press Calculate before adding.",
                                       parent=win)
                return
            pname = name_entry.get().strip()
            if not pname:
                messagebox.showwarning("Name required", "Enter a profile name.", parent=win)
                return
            grade = grade_var.get()
            entry = {
                "Area": round(_calc_result["A"],  3),
                "Ix":   round(_calc_result["Ix"], 3),
                "Iy":   round(_calc_result["Iy"], 3),
                "rx":   round(_calc_result["rx"], 3),
                "ry":   round(_calc_result["ry"], 3),
                "Grade": grade,
                "standard": "Custom",
                "section_type": "Custom",
            }
            # Add to live databases so the profile is immediately usable
            from steel_database import SECTION_DB
            SECTION_DB[pname] = entry
            STEEL_PROFILES[pname] = {k: v for k, v in entry.items()
                                      if k in ("Area","Ix","Iy","rx","ry","Grade")}
            messagebox.showinfo("Added", f"Profile '{pname}' added.\nRe-open Members tab to see it.",
                                parent=win)
            win.destroy()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=8)
        ctk.CTkButton(btn_row, text="Calculate", width=140,
                      fg_color=COLOR_PALETTE["primary"],
                      command=_calculate).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Add to Database", width=160,
                      fg_color=COLOR_PALETTE["success"],
                      command=_add_profile).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Cancel", width=80,
                      fg_color=COLOR_PALETTE["secondary"],
                      command=win.destroy).pack(side="right", padx=4)

    def draw_templates_tab(self):
        self.update_idletasks()
        for w in self.tab_templ.winfo_children():
            try: w.destroy()
            except Exception: pass

        # ── Vertical single-column layout (fits inside 420px left panel) ──
        # [Scrollable area: type selector + params + profiles]
        # [Fixed Generate button at bottom]

        outer = ctk.CTkFrame(self.tab_templ, fg_color="transparent")
        outer.pack(fill="both", expand=True)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=0)
        outer.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # ── Section: Type Selector ───────────────────────────────────────
        ctk.CTkLabel(scroll, text="Truss Type",
                     font=TYPO_SCALE["h3"],
                     text_color=COLOR_PALETTE["text_primary"]).pack(anchor="w", padx=8, pady=(8, 2))

        TRUSS_CATEGORIES = {
            "Pitched": ["Howe", "Pratt", "Fan", "Fink", "King Post", "Scissors", "Modified Scissors"],
            "Half / Mono": ["Monopith", "Half Howe", "Half Pratt", "Half Warren", "Half Scissors"],
            "Flat": ["Parallel Chord", "Warren (Flat)", "Modified Warren"],
            "Special": ["Bowstring", "Bowstring (Pratt)", "Bowstring (Warren)", "Curved Truss 1", "Curved Truss 2", "Curved Truss 3", "Single Cantilever", "Double Stub End"],
        }

        # Button colour helpers — readable in both light and dark mode
        def _btn_idle():
            return {"fg_color": COLOR_PALETTE["row_alt"],
                    "text_color": COLOR_PALETTE["text_primary"],
                    "border_color": COLOR_PALETTE["text_secondary"],
                    "border_width": 1,
                    "hover_color": COLOR_PALETTE["secondary"]}

        def _btn_active():
            return {"fg_color": COLOR_PALETTE["primary"],
                    "text_color": "#FFFFFF",
                    "border_color": COLOR_PALETTE["accent"],
                    "border_width": 2,
                    "hover_color": COLOR_PALETTE["accent"]}

        self.template_btn_map = {}
        for cat, types in TRUSS_CATEGORIES.items():
            ctk.CTkLabel(scroll, text=cat,
                         font=TYPO_SCALE["small"],
                         text_color=COLOR_PALETTE["accent"]).pack(anchor="w", padx=10, pady=(10, 2))

            # 3 columns to fit ~400px without overflow
            grid = ctk.CTkFrame(scroll, fg_color="transparent")
            grid.pack(fill="x", padx=6, pady=2)
            grid.grid_columnconfigure((0, 1, 2), weight=1)

            for i, t_type in enumerate(types):
                style = _btn_active() if t_type == self.model.selected_template else _btn_idle()
                btn = ctk.CTkButton(
                    grid, text=t_type, height=32,
                    font=TYPO_SCALE["small"],
                    command=lambda t=t_type: self.select_truss_template(t),
                    **style,
                )
                btn.grid(row=i // 3, column=i % 3, padx=3, pady=3, sticky="ew")
                self.template_btn_map[t_type] = btn

        # ── Section: Mini Preview ────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=COLOR_PALETTE["text_secondary"]).pack(
            fill="x", padx=8, pady=(12, 6))
        ctk.CTkLabel(scroll, text="Preview",
                     font=TYPO_SCALE["h3"],
                     text_color=COLOR_PALETTE["text_primary"]).pack(anchor="w", padx=8, pady=(0, 4))

        self.mini_preview_frame = ctk.CTkFrame(
            scroll, height=150,
            fg_color="#FFFFFF",
            corner_radius=8)
        self.mini_preview_frame.pack(fill="x", padx=8, pady=4)

        # ── Section: Parameters ──────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=COLOR_PALETTE["text_secondary"]).pack(
            fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(scroll, text="Parameters",
                     font=TYPO_SCALE["h3"],
                     text_color=COLOR_PALETTE["text_primary"]).pack(anchor="w", padx=8, pady=(0, 4))

        def _param_row(label, key, default_val):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=3)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=0)
            ctk.CTkLabel(row, text=label, font=TYPO_SCALE["small"],
                         text_color=COLOR_PALETTE["text_primary"],
                         anchor="w").grid(row=0, column=0, sticky="w")
            ent = ctk.CTkEntry(row, width=90, font=TYPO_SCALE["mono"])
            ent.insert(0, str(self.model.template_params.get(key, default_val)))
            ent.grid(row=0, column=1)
            ent.bind("<KeyRelease>", lambda e: self.update_template_param(key, ent.get()))
            return ent

        self.span_entry   = _param_row("Span (m):",   "span",   12.0)
        self.height_entry = _param_row("Height (m):", "height",  3.0)
        self.bays_entry   = _param_row("Bays:",       "bays",      6)

        self.extra_params_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.extra_params_frame.pack(fill="x")
        self.update_extra_param_fields()

        # ── Section: Profiles ────────────────────────────────────────────
        ctk.CTkFrame(scroll, height=1, fg_color=COLOR_PALETTE["text_secondary"]).pack(
            fill="x", padx=8, pady=(10, 6))
        ctk.CTkLabel(scroll, text="Profiles",
                     font=TYPO_SCALE["h3"],
                     text_color=COLOR_PALETTE["text_primary"]).pack(anchor="w", padx=8, pady=(0, 4))

        # Profile filter bar (shared with members tab)
        tmpl_filter = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["row_alt"], corner_radius=6)
        tmpl_filter.pack(fill="x", padx=8, pady=(0, 6))
        ctk.CTkLabel(tmpl_filter, text="Standard:", font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=(8, 2), pady=4)
        ctk.CTkOptionMenu(
            tmpl_filter,
            values=["All", "TIS", "JIS", "EN", "AISC", "Custom"],
            variable=self._prof_std_filter,
            width=80, height=26, font=TYPO_SCALE["small"],
            command=lambda _v: self.draw_templates_tab(),
        ).pack(side="left", padx=2, pady=4)
        ctk.CTkLabel(tmpl_filter, text="Type:", font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_secondary"]).pack(side="left", padx=(10, 2), pady=4)
        ctk.CTkOptionMenu(
            tmpl_filter,
            values=["All", "RHS", "CHS", "Angle", "I-Beam", "H-Beam", "Channel", "Custom"],
            variable=self._prof_type_filter,
            width=100, height=26, font=TYPO_SCALE["small"],
            command=lambda _v: self.draw_templates_tab(),
        ).pack(side="left", padx=2, pady=4)

        def _profile_row(label, var_name, default):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=3)
            ctk.CTkLabel(row, text=label, width=62, anchor="w",
                         font=TYPO_SCALE["small"],
                         text_color=COLOR_PALETTE["text_primary"]).pack(side="left")
            _fp  = self._get_filtered_profiles()
            _def = default if default in _fp else (_fp[0] if _fp else default)
            var  = ctk.StringVar(value=_def)
            menu = ctk.CTkOptionMenu(
                row, values=_fp, variable=var,
                height=28, font=TYPO_SCALE["small"],
                fg_color=COLOR_PALETTE["primary"],
                button_color=COLOR_PALETTE["secondary"],
                button_hover_color=COLOR_PALETTE["accent"],
                text_color="#FFFFFF",
                dynamic_resizing=False,
            )
            menu.pack(side="left", fill="x", expand=True)
            setattr(self, var_name + "_var", var)
            return menu

        self.top_chord_profile_menu    = _profile_row("Top:",    "top_chord_profile",    "IPE 160")
        self.bottom_chord_profile_menu = _profile_row("Bottom:", "bottom_chord_profile", "IPE 160")
        self.web_profile_menu          = _profile_row("Webs:",   "web_profile",          "RHS 50x50x2.3")

        # ── Fixed Generate Button ────────────────────────────────────────
        gen_frame = ctk.CTkFrame(outer, fg_color="transparent")
        gen_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=8)
        ctk.CTkButton(
            gen_frame, text="GENERATE TRUSS", height=44,
            fg_color=COLOR_PALETTE["success"],
            hover_color="#065F46",
            text_color="#FFFFFF",
            font=TYPO_SCALE["h3"],
            command=self.generate_parametric_truss,
        ).pack(fill="x")

        # Initial preview
        self.generate_preview_immediately()

    def select_truss_template(self, t_type):
        """Handle template selection and update UI state"""
        # Reset old button to idle style
        if self.model.selected_template in self.template_btn_map:
            self.template_btn_map[self.model.selected_template].configure(
                fg_color=COLOR_PALETTE["row_alt"],
                text_color=COLOR_PALETTE["text_primary"],
                border_color=COLOR_PALETTE["text_secondary"],
                border_width=1,
            )

        self.model.selected_template = t_type

        # Set new button to active style
        if t_type in self.template_btn_map:
            self.template_btn_map[t_type].configure(
                fg_color=COLOR_PALETTE["primary"],
                text_color="#FFFFFF",
                border_color=COLOR_PALETTE["accent"],
                border_width=2,
            )
            
        self.update_extra_param_fields()
        self.generate_preview_immediately()

    def update_template_param(self, key, val):
        """Update parameter value from entry"""
        try:
            if key == "bays":
                self.model.template_params[key] = int(val)
            else:
                self.model.template_params[key] = float(val)
            self.generate_preview_immediately()
        except ValueError:
            pass

    def update_extra_param_fields(self):
        """Show only relevant parameter fields for the selected truss type"""
        if not hasattr(self, 'extra_params_frame'): return
        for w in self.extra_params_frame.winfo_children(): w.destroy()
        
        t = self.model.selected_template
        
        if t in ["Scissors", "Modified Scissors", "Half Scissors"]:
            self._add_extra_field("Bottom H (m):", "bottom_height", 1.0)
        elif "Curved" in t or "Bowstring" in t:
            self._add_extra_field("Rise (m):", "rise", 2.0)
        elif t == "Single Cantilever":
            self._add_extra_field("Canti L (m):", "cantilever_len", 3.0)
        elif t == "Double Stub End":
            self._add_extra_field("Stub H (m):", "stub_height", 0.5)

    def _add_extra_field(self, label, key, default):
        row = ctk.CTkFrame(self.extra_params_frame, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=0)
        ctk.CTkLabel(row, text=label, font=TYPO_SCALE["small"],
                     text_color=COLOR_PALETTE["text_primary"],
                     anchor="w").grid(row=0, column=0, sticky="w")
        entry = ctk.CTkEntry(row, width=90, font=TYPO_SCALE["mono"])
        entry.insert(0, str(self.model.template_params.get(key, default)))
        entry.grid(row=0, column=1)
        entry.bind("<KeyRelease>", lambda e: self.update_template_param(key, entry.get()))

    def _get_profiles(self) -> dict:
        return {
            "top_chord":    self.top_chord_profile_var.get(),
            "bottom_chord": self.bottom_chord_profile_var.get(),
            "vertical":     self.web_profile_var.get(),
            "diagonal":     self.web_profile_var.get(),
        }

    def generate_parametric_truss(self):
        try:
            p = self.model.template_params
            if p["span"] <= 0 or p["height"] <= 0:
                raise ValueError("Span and Height must be positive")

            profiles = self._get_profiles()
            nodes, elements = TrussGenerators.generate(self.model.selected_template, p, profiles)
            self.model.nodes_data = nodes
            self.model.elements_data = elements
            self.model.loads_data = TrussGenerators.default_loads(nodes)

            self.model.save_state()
            self.refresh_ui()
            self.generate_preview_immediately()
            self.update_status(f"✓ Generated {self.model.selected_template} truss", "success")

        except Exception as e:
            messagebox.showerror("Template Error", f"Failed to generate truss: {e}")

    def generate_preview_immediately(self):
        if not hasattr(self, "mini_preview_frame"):
            return
        orig_nodes = copy.deepcopy(self.model.nodes_data)
        orig_elems = copy.deepcopy(self.model.elements_data)
        try:
            for w in self.mini_canvas_widgets:
                w.destroy()
            self.mini_canvas_widgets.clear()

            p = self.model.template_params
            if p["span"] <= 0 or p["height"] <= 0:
                return

            profiles = self._get_profiles()
            nodes, elements = TrussGenerators.generate(self.model.selected_template, p, profiles)
            self.model.nodes_data = nodes
            self.model.elements_data = elements

            fig, ax = plt.subplots(figsize=(5, 3), dpi=80)
            fig.patch.set_facecolor("#FFFFFF")
            ax.set_facecolor("#FFFFFF")

            for el in self.model.elements_data:
                n1 = self.model.nodes_data[el["node_a"] - 1]
                n2 = self.model.nodes_data[el["node_b"] - 1]
                ax.plot([n1["x"], n2["x"]], [n1["y"], n2["y"]],
                        color="#1D4ED8", linewidth=1.5)
            for n in self.model.nodes_data:
                ax.plot(n["x"], n["y"], "o", color="#0F172A", markersize=3)
                if n["support"] != "Free":
                    ax.plot(n["x"], n["y"] - 0.2, "^", color="#DC2626", markersize=6)

            ax.set_aspect("equal")
            ax.axis("off")
            ax.set_title(f"Preview: {self.model.selected_template}",
                         fontsize=10, color="#0F172A")

            canvas = FigureCanvasTkAgg(fig, master=self.mini_preview_frame)
            canvas.draw()
            plt.close(fig)
            w = canvas.get_tk_widget()
            w.pack(fill="both", expand=True)
            self.mini_canvas_widgets.append(w)

        except Exception:
            pass
        finally:
            self.model.nodes_data = orig_nodes
            self.model.elements_data = orig_elems

    def save_project(self):
        if not self.sync_data():
            return
        f = filedialog.asksaveasfilename(defaultextension=".json")
        if f:
            with open(f, "w", encoding="utf-8") as j:
                json.dump(self.model.to_dict(), j, indent=2)

    def load_project(self):
        f = filedialog.askopenfilename()
        if f:
            with open(f, "r", encoding="utf-8") as j:
                self.model.from_dict(json.load(j))
            self.refresh_ui()

    def export_csv(self):
        if not self.ss:
            return
        f = filedialog.asksaveasfilename(defaultextension=".csv")
        if f:
            TrussExporter.export_csv(self.ss, f)
            messagebox.showinfo("Success", "Exported CSV!")

    def export_report(self):
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No analysis results. Run analysis first.")
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")],
            title="Save Structural Analysis Report",
        )
        if not f:
            return
        try:
            merged_combos_pdf = {
                method: {**LOAD_COMBINATIONS[method],
                         **self.model.custom_combinations.get(method, {})}
                for method in LOAD_COMBINATIONS
            }
            TrussExporter.export_pdf(
                self.model, self.ss, self.analysis_results, f,
                self.scale_support_symbols, self.add_dimensions,
                STEEL_GRADES=STEEL_GRADES,
                STEEL_PROFILES=STEEL_PROFILES,
                LOAD_COMBINATIONS=merged_combos_pdf,
            )
            messagebox.showinfo("Success", f"PDF Report generated!\n{f}")
        except Exception as e:
            import traceback; traceback.print_exc()
            messagebox.showerror("Export Error", f"Failed to generate PDF: {e}")

if __name__ == "__main__":
    app = TrussAnalyzerPro()
    app.mainloop()
