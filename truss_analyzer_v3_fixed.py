from __future__ import annotations
import datetime
import json
import os
import math
import csv
from tkinter import filedialog, messagebox
import customtkinter as ctk
import matplotlib.patches as patches
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

# --- Import Real Solver ---
try:
    from anastruct import SystemElements as AnaStructSystemElements
    from anastruct.basic import FEMException
    ANACSTRUCT_AVAILABLE = True
except (ImportError, TypeError):
    ANACSTRUCT_AVAILABLE = False
    AnaStructSystemElements = None
    FEMException = Exception

# --- Global Configurations ---
STEEL_GRADES = {
    "A36": {"Fy": 250, "Fu": 400, "E": 200000},
    "A572-50": {"Fy": 345, "Fu": 450, "E": 200000},
    "A992": {"Fy": 345, "Fu": 450, "E": 200000},
    "SS400": {"Fy": 235, "Fu": 400, "E": 200000}
}

STEEL_PROFILES = {
    "Box 50x50x2.3": {"Area": 3.71, "Ix": 8.25, "Iy": 8.25, "rx": 1.49, "ry": 1.49, "Grade": "A36"},
    "Box 100x100x3.2": {"Area": 12.1, "Ix": 82.4, "Iy": 82.4, "rx": 2.61, "ry": 2.61, "Grade": "A36"},
    "Pipe 60.3x3.2": {"Area": 5.64, "Ix": 20.1, "Iy": 20.1, "rx": 1.89, "ry": 1.89, "Grade": "A36"},
    "Pipe 114.3x4.5": {"Area": 15.2, "Ix": 147.2, "Iy": 147.2, "rx": 3.11, "ry": 3.11, "Grade": "A36"},
    "Angle 50x50x5": {"Area": 4.80, "Ix": 11.4, "Iy": 11.4, "rx": 1.54, "ry": 1.54, "Grade": "A36"},
    "I-Beam IPE100": {"Area": 10.3, "Ix": 171, "Iy": 15.9, "rx": 4.07, "ry": 1.24, "Grade": "A572-50"},
    "I-Beam IPE160": {"Area": 20.1, "Ix": 869, "Iy": 68.3, "rx": 6.58, "ry": 1.84, "Grade": "A572-50"}
}

UNIT_FORCE_TO_KN = {"kN": 1.0, "N": 0.001, "tf": 9.81, "kgf": 0.00981, "kip": 4.448}
UNIT_LENGTH_TO_M = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}

LOAD_COMBINATIONS = {
    "ASD": {
        "1.0D": {"DL": 1.0, "LL": 0.0, "WL": 0.0, "SL": 0.0},
        "1.0D + 1.0L": {"DL": 1.0, "LL": 1.0, "WL": 0.0, "SL": 0.0}
    },
    "LRFD": {
        "1.4D": {"DL": 1.4, "LL": 0.0, "WL": 0.0, "SL": 0.0},
        "1.2D + 1.6L": {"DL": 1.2, "LL": 1.6, "WL": 0.0, "SL": 0.0}
    }
}

COLOR_PALETTE = {
    "primary": "#2563EB", "secondary": "#7C3AED", "success": "#059669", 
    "warning": "#D97706", "danger": "#DC2626", "surface": "#1F2937", 
    "background": "#111827", "text_primary": "#F9FAFB", "text_secondary": "#9CA3AF", "accent": "#06B6D4"
}

TYPO_SCALE = {"h1": ("Segoe UI", 24, "bold"), "h2": ("Segoe UI", 18, "bold"), "h3": ("Segoe UI", 14, "bold"), "body": ("Segoe UI", 12, "normal"), "small": ("Segoe UI", 10, "normal"), "mono": ("Consolas", 11, "normal")}

class TrussAnalyzer:
    def __init__(self):
        self.ss = AnaStructSystemElements()
        self.solved = False
    def add_truss_element(self, location, EA): return self.ss.add_truss_element(location=location, EA=EA)
    def add_support_hinged(self, node_id): self.ss.add_support_hinged(node_id=node_id)
    def add_support_roll(self, node_id, direction): self.ss.add_support_roll(node_id=node_id, direction=direction)
    def point_load(self, node_id, Fx, Fy): self.ss.point_load(node_id=node_id, Fx=Fx, Fy=Fy)
    def solve(self): self.ss.solve(); self.solved = True
    def get_element_results(self, eid):
        res = self.ss.get_element_results(eid)
        if isinstance(res, dict) and res.get("N") is None: res["N"] = res.get("Nmin", 0.0)
        return res
    @property
    def nodes(self): return self.ss.node_map
    @property
    def elements(self): return self.ss.element_map
    @property
    def displacements(self):
        d = {}
        if self.solved:
            for nid in self.ss.node_map:
                idx = (nid - 1) * 3
                d[nid] = {'dx': self.ss.system_displacement_vector[idx], 'dy': self.ss.system_displacement_vector[idx+1]}
        return d

# --- UI Application ---
class TrussAnalyzerPro(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🏗️ Advanced Truss Analyzer PRO v3.0 - Ultimate Fix")
        self.geometry("1800x1000")
        self.configure(bg_color=COLOR_PALETTE["background"])
        
        self.ss = None
        self.analysis_results = None
        self.nodes_data = [{"x": 0.0, "y": 0.0, "support": "Pinned"}, {"x": 6.0, "y": 0.0, "support": "Roller"}, {"x": 3.0, "y": 4.0, "support": "Free"}]
        self.elements_data = [{"node_a": 1, "node_b": 2, "profile": "Box 50x50x2.3"}, {"node_a": 2, "node_b": 3, "profile": "Box 50x50x2.3"}, {"node_a": 3, "node_b": 1, "profile": "Box 50x50x2.3"}]
        self.loads_data = [{"node_id": 3, "fx": 0.0, "fy": -50.0, "case": "LL"}]
        self.selected_template = "Warren"
        self.template_params = {"span": 12.0, "height": 3.0, "bays": 6, "bottom_height": 1.0, "rise": 2.0, "cantilever_len": 3.0, "stub_height": 0.5}
        self.design_method, self.selected_combo = "LRFD", "1.2D + 1.6L"
        self.unit_force, self.unit_length = "kN", "m"
        self.project_data = {"name": "Project", "engineer": "Engineer", "date": datetime.datetime.now().strftime("%Y-%m-%d"), "location": "Site"}
        
        self.setup_ui()
        self.mini_canvas_widgets = []
        self.refresh_ui()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1, minsize=600); self.grid_columnconfigure(1, weight=3); self.grid_rowconfigure(0, weight=1)
        self.left_panel = ctk.CTkFrame(self, fg_color=COLOR_PALETTE["surface"], corner_radius=15)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.tabs = ctk.CTkTabview(self.left_panel, fg_color=COLOR_PALETTE["surface"])
        self.tabs.pack(fill="both", expand=True, padx=10, pady=5)
        self.tab_proj = self.tabs.add("📋 Project"); self.tab_nodes = self.tabs.add("📍 Nodes")
        self.tab_elems = self.tabs.add("🔗 Members"); self.tab_loads = self.tabs.add("⚡ Loads")
        self.tab_templ = self.tabs.add("🏗️ Templates"); self.tab_res = self.tabs.add("📊 Results")
        
        # Analyze Button
        ctrl = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        ctrl.pack(fill="x", padx=15, pady=15)
        ctk.CTkButton(ctrl, text="🚀 FULL ANALYSIS & DESIGN CHECK", height=50, fg_color=COLOR_PALETTE["success"], font=TYPO_SCALE["h3"], command=self.calculate).pack(fill="x")
        
        # Right Panel
        self.right_panel = ctk.CTkScrollableFrame(self, fg_color=COLOR_PALETTE["background"], corner_radius=15)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 15), pady=15)
        self.canvas_widgets = []

    def refresh_ui(self): self.draw_project_tab(); self.draw_nodes_tab(); self.draw_elements_tab(); self.draw_loads_tab(); self.draw_templates_tab()

    def draw_project_tab(self):
        for w in self.tab_proj.winfo_children(): w.destroy()
        scroll = ctk.CTkScrollableFrame(self.tab_proj, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        self.project_entries = {}
        for k, v in self.project_data.items():
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=f"{k.title()}:", width=120).pack(side="left", padx=10)
            e = ctk.CTkEntry(row, width=250); e.insert(0, str(v)); e.pack(side="left", padx=10)
            self.project_entries[k] = e
        ctk.CTkButton(self.tab_proj, text="📄 PDF Report", command=self.export_report, fg_color=COLOR_PALETTE["danger"]).pack(pady=10)

    def draw_nodes_tab(self):
        for w in self.tab_nodes.winfo_children(): w.destroy()
        scroll = ctk.CTkScrollableFrame(self.tab_nodes, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        self.node_entries = []
        for i, n in enumerate(self.nodes_data):
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"N{i+1}", width=40).pack(side="left", padx=5)
            ex = ctk.CTkEntry(row, width=70); ex.insert(0, f"{n['x']:.2f}"); ex.pack(side="left", padx=5)
            ey = ctk.CTkEntry(row, width=70); ey.insert(0, f"{n['y']:.2f}"); ey.pack(side="left", padx=5)
            sv = ctk.StringVar(value=n["support"])
            ctk.CTkOptionMenu(row, values=["Free", "Pinned", "Roller"], variable=sv, width=100).pack(side="left", padx=5)
            self.node_entries.append({"x": ex, "y": ey, "support": sv})
        ctk.CTkButton(self.tab_nodes, text="✚ Add Node", command=lambda: [self.sync_data(), self.nodes_data.append({"x":0,"y":0,"support":"Free"}), self.refresh_ui()]).pack(pady=10)

    def draw_elements_tab(self):
        for w in self.tab_elems.winfo_children(): w.destroy()
        scroll = ctk.CTkScrollableFrame(self.tab_elems, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        self.elem_entries = []
        for i, el in enumerate(self.elements_data):
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=f"E{i+1}", width=40).pack(side="left", padx=5)
            ea = ctk.CTkEntry(row, width=50); ea.insert(0, str(el["node_a"])); ea.pack(side="left", padx=5)
            eb = ctk.CTkEntry(row, width=50); eb.insert(0, str(el["node_b"])); eb.pack(side="left", padx=5)
            pv = ctk.StringVar(value=el["profile"])
            ctk.CTkOptionMenu(row, values=list(STEEL_PROFILES.keys()), variable=pv, width=150).pack(side="left", padx=5)
            self.elem_entries.append({"a": ea, "b": eb, "profile": pv})
        ctk.CTkButton(self.tab_elems, text="✚ Add Member", command=lambda: [self.sync_data(), self.elements_data.append({"node_a":1,"node_b":2,"profile":"Box 50x50x2.3"}), self.refresh_ui()]).pack(pady=10)

    def draw_loads_tab(self):
        for w in self.tab_loads.winfo_children(): w.destroy()
        scroll = ctk.CTkScrollableFrame(self.tab_loads, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10)
        self.load_entries = []
        for i, ld in enumerate(self.loads_data):
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=3)
            en = ctk.CTkEntry(row, width=50); en.insert(0, str(ld["node_id"])); en.pack(side="left", padx=5)
            efy = ctk.CTkEntry(row, width=70); efy.insert(0, str(ld["fy"])); efy.pack(side="left", padx=5)
            cv = ctk.StringVar(value=ld["case"]); ctk.CTkOptionMenu(row, values=["DL", "LL", "WL"], variable=cv, width=80).pack(side="left", padx=5)
            self.load_entries.append({"id": en, "fy": efy, "case": cv, "fx": ctk.CTkEntry(row, width=0)}) # simplified
        ctk.CTkButton(self.tab_loads, text="✚ Add Load", command=lambda: [self.sync_data(), self.loads_data.append({"node_id":1,"fx":0,"fy":-10,"case":"LL"}), self.refresh_ui()]).pack(pady=10)

    def draw_templates_tab(self):
        for w in self.tab_templ.winfo_children(): w.destroy()
        header = ctk.CTkFrame(self.tab_templ, fg_color="transparent"); header.pack(side="top", fill="x", padx=10, pady=5)
        ctk.CTkLabel(header, text="🏗️ Truss Templates", font=TYPO_SCALE["h3"]).pack()
        
        btn_area = ctk.CTkFrame(self.tab_templ, fg_color=COLOR_PALETTE["surface"], height=90)
        btn_area.pack(side="bottom", fill="x", padx=15, pady=15); btn_area.pack_propagate(False)
        ctk.CTkButton(btn_area, text="🏗️ GENERATE STRUCTURE", height=60, font=TYPO_SCALE["h2"], fg_color=COLOR_PALETTE["success"], command=self.generate_parametric_truss).pack(expand=True, fill="both", padx=10)

        main = ctk.CTkFrame(self.tab_templ, fg_color="transparent"); main.pack(fill="both", expand=True)
        sel_panel = ctk.CTkScrollableFrame(main, fg_color=COLOR_PALETTE["surface"]); sel_panel.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        par_panel = ctk.CTkScrollableFrame(main, width=300, fg_color=COLOR_PALETTE["surface"]); par_panel.pack(side="right", fill="both", expand=False, padx=5, pady=5)

        for cat, types in {"Pitched": ["Howe", "Pratt", "Fan", "Fink"], "Mono/Special": ["Monopith", "Scissors", "Parallel Chord", "Bowstring"]}.items():
            ctk.CTkLabel(sel_panel, text=cat, font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["accent"]).pack(anchor="w", padx=10, pady=5)
            for t in types: ctk.CTkButton(sel_panel, text=t, command=lambda x=t: self.select_truss_template(x)).pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(par_panel, text="🔍 Mini Preview", font=TYPO_SCALE["h3"]).pack(pady=5)
        self.mini_preview_frame = ctk.CTkFrame(par_panel, height=150, fg_color="#f0f0f0"); self.mini_preview_frame.pack(fill="x", padx=10)
        
        def add_p(label, key, default):
            row = ctk.CTkFrame(par_panel, fg_color="transparent"); row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=label, width=100).pack(side="left")
            e = ctk.CTkEntry(row, width=80); e.insert(0, str(self.template_params.get(key, default))); e.pack(side="right")
            e.bind('<KeyRelease>', lambda e_obj: [self.template_params.update({key: float(e.get() or 0)}), self.generate_preview_immediately()])
        add_p("Span (m):", "span", 12); add_p("Height (m):", "height", 3); add_p("Bays:", "bays", 6)
        
        self.top_chord_profile_var = ctk.StringVar(value="I-Beam IPE160")
        self.bottom_chord_profile_var = ctk.StringVar(value="I-Beam IPE160")
        self.web_profile_var = ctk.StringVar(value="Box 50x50x2.3")
        
        self.generate_preview_immediately()

    def select_truss_template(self, t): self.selected_template = t; self.generate_preview_immediately()

    def generate_preview_immediately(self):
        if not hasattr(self, 'mini_preview_frame'): return
        orig_nodes, orig_elems = self.nodes_data.copy(), self.elements_data.copy()
        try:
            for w in self.mini_canvas_widgets: w.destroy()
            self.mini_canvas_widgets.clear()
            p, t = self.template_params, self.selected_template
            self.nodes_data, self.elements_data = [], []
            self._run_generator(t, p)
            fig, ax = plt.subplots(figsize=(4, 2), dpi=70); ax.set_facecolor('#f0f0f0'); fig.patch.set_facecolor('#f0f0f0')
            for el in self.elements_data:
                n1, n2 = self.nodes_data[el["node_a"]-1], self.nodes_data[el["node_b"]-1]
                ax.plot([n1["x"], n2["x"]], [n1["y"], n2["y"]], 'b-', lw=1)
            ax.set_aspect('equal'); ax.axis('off')
            canvas = FigureCanvasTkAgg(fig, master=self.mini_preview_frame); canvas.draw(); w = canvas.get_tk_widget(); w.pack(fill="both"); self.mini_canvas_widgets.append(w)
        except Exception: pass
        finally: self.nodes_data, self.elements_data = orig_nodes, orig_elems

    def _run_generator(self, t, p):
        dx = p["span"]/p["bays"]; profiles = {'top_chord': "Box 50x50x2.3", 'bottom_chord': "Box 50x50x2.3", 'vertical': "Box 50x50x2.3", 'diagonal': "Box 50x50x2.3"}
        if t == "Howe" or t == "Pratt":
            for i in range(int(p["bays"]) + 1):
                self.nodes_data.append({"x": i*dx, "y": 0, "support": "Pinned" if i==0 else ("Roller" if i==p["bays"] else "Free")})
                self.nodes_data.append({"x": i*dx, "y": p["height"] if i==0 or i==p["bays"] else p["height"]*1.2, "support": "Free"})
            for i in range(int(p["bays"])):
                b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
                self.elements_data.append({"node_a": b1, "node_b": b2, "profile": profiles['bottom_chord']})
                self.elements_data.append({"node_a": t1, "node_b": t2, "profile": profiles['top_chord']})
                self.elements_data.append({"node_a": b2, "node_b": t2, "profile": profiles['vertical']})
                self.elements_data.append({"node_a": b1 if t=="Howe" else b2, "node_b": t2 if t=="Howe" else t1, "profile": profiles['diagonal']})
        else: # Default Warren
            for i in range(int(p["bays"]) + 1):
                self.nodes_data.append({"x": i*dx, "y": 0, "support": "Pinned" if i==0 else ("Roller" if i==p["bays"] else "Free")})
                self.nodes_data.append({"x": i*dx, "y": p["height"], "support": "Free"})
            for i in range(int(p["bays"])):
                b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
                self.elements_data.append({"node_a": b1, "node_b": b2, "profile": "Box 50x50x2.3"})
                self.elements_data.append({"node_a": t1, "node_b": t2, "profile": "Box 50x50x2.3"})
                self.elements_data.append({"node_a": b1 if i%2==0 else b2, "node_b": t2 if i%2==0 else t1, "profile": "Box 50x50x2.3"})

    def generate_parametric_truss(self):
        try:
            self.nodes_data, self.elements_data = [], []
            self._run_generator(self.selected_template, self.template_params)
            self.refresh_ui(); self.tabs.set("📍 Nodes")
        except Exception as e: messagebox.showerror("Error", str(e))

    def sync_data(self):
        try:
            self.nodes_data = [{"x": float(e["x"].get()), "y": float(e["y"].get()), "support": e["support"].get()} for e in self.node_entries]
            self.elements_data = [{"node_a": int(e["a"].get()), "node_b": int(e["b"].get()), "profile": e["profile"].get()} for e in self.elem_entries]
            self.loads_data = [{"node_id": int(e["id"].get()), "fx": 0, "fy": float(e["fy"].get()), "case": e["case"].get()} for e in self.load_entries]
        except: pass

    def calculate(self):
        self.sync_data()
        try:
            self.ss = TrussAnalyzer()
            for el in self.elements_data:
                prof = STEEL_PROFILES[el["profile"]]
                ea = STEEL_GRADES[prof["Grade"]]["E"] * prof["Area"] * 10
                n1, n2 = self.nodes_data[el["node_a"]-1], self.nodes_data[el["node_b"]-1]
                self.ss.add_truss_element(location=[[n1["x"], n1["y"]], [n2["x"], n2["y"]]], EA=ea)
            for i, n in enumerate(self.nodes_data):
                if n["support"] == "Pinned": self.ss.add_support_hinged(i+1)
                elif n["support"] == "Roller": self.ss.add_support_roll(i+1, 2)
            for ld in self.loads_data: self.ss.point_load(ld["node_id"], 0, ld["fy"])
            self.ss.solve()
            self.analysis_results = []
            for i, el in enumerate(self.elements_data):
                res = self.ss.get_element_results(i+1)
                force = res["N"]
                prof = STEEL_PROFILES[el["profile"]]; grade = STEEL_GRADES[prof["Grade"]]
                stress = abs(force*1000)/(prof["Area"]*100)
                util = stress/grade["Fy"] # simplified
                self.analysis_results.append({"member_id": f"E{i+1}", "profile": el["profile"], "force": force, "utilization": util, "status": "OK" if util<1 else "FAIL", "type": "Tension" if force>0 else "Comp", "stress": stress})
            self.update_enhanced_plots(); self.show_enhanced_results()
        except Exception as e: messagebox.showerror("Error", str(e))

    def update_enhanced_plots(self):
        for w in self.canvas_widgets: w.destroy()
        self.canvas_widgets.clear()
        if not self.ss: return
        
        # Axial Force with Values
        fig, ax = plt.subplots(figsize=(10, 5))
        for i, r in enumerate(self.analysis_results):
            el = self.ss.elements[i+1]
            color = '#E74C3C' if r["force"] > 0 else '#2980B9'
            ax.plot([el.vertex_1.x, el.vertex_2.x], [el.vertex_1.y, el.vertex_2.y], color=color, lw=2)
            ax.text((el.vertex_1.x+el.vertex_2.x)/2, (el.vertex_1.y+el.vertex_2.y)/2, f"{r['force']:.1f}", fontsize=8, ha='center', bbox=dict(boxstyle="round", fc='white', alpha=0.7))
        ax.set_aspect('equal'); ax.set_title("Axial Force (kN)")
        self._add_to_right_panel(fig)

        # Displacement with Values
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        disps = self.ss.displacements
        for nid, node in self.ss.nodes.items():
            ax2.plot(node.vertex.x, node.vertex.y, 'ko')
            ax2.text(node.vertex.x, node.vertex.y, f"N{nid}\n{disps[nid]['dy']*1000:.1f}mm", fontsize=7, color='purple', ha='center')
        ax2.set_aspect('equal'); ax2.set_title("Displacement (mm)")
        self._add_to_right_panel(fig2)

    def _add_to_right_panel(self, fig):
        canvas = FigureCanvasTkAgg(fig, master=self.right_panel); canvas.draw()
        w = canvas.get_tk_widget(); w.pack(fill="x", padx=10, pady=10); self.canvas_widgets.append(w)

    def show_enhanced_results(self):
        for w in self.tab_res.winfo_children(): w.destroy()
        max_tension = max(self.analysis_results, key=lambda x: x["force"])
        max_comp = min(self.analysis_results, key=lambda x: x["force"])
        max_disp = max(self.ss.displacements.items(), key=lambda x: abs(x[1]['dy']))
        
        peaks = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["secondary"], corner_radius=10); peaks.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(peaks, text=f"🏆 Peak Results: Tension={max_tension['force']:.1f}kN ({max_tension['member_id']}) | Comp={max_comp['force']:.1f}kN ({max_comp['member_id']}) | Defl={max_disp[1]['dy']*1000:.2f}mm (N{max_disp[0]})", text_color="white").pack(pady=10)
        
        scroll = ctk.CTkScrollableFrame(self.tab_res); scroll.pack(fill="both", expand=True)
        for r in self.analysis_results:
            row = ctk.CTkFrame(scroll, fg_color=COLOR_PALETTE["surface"]); row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"{r['member_id']} | {r['profile']} | Force: {r['force']:.1f}kN | Util: {r['utilization']:.2f} | {r['status']}").pack(side="left", padx=10)

    def export_report(self):
        fpath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Documents", "*.pdf")])
        if not fpath: return
        try:
            from reportlab.lib import colors; from reportlab.lib.pagesizes import A4; from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
            from reportlab.lib.styles import getSampleStyleSheet; import io
            doc = SimpleDocTemplate(fpath, pagesize=A4); elements = []; styles = getSampleStyleSheet()
            elements.append(Paragraph("🏗️ Truss Analysis Report", styles["Title"]))
            
            # Peak Summary Table
            max_tension = max(self.analysis_results, key=lambda x: x["force"])
            max_comp = min(self.analysis_results, key=lambda x: x["force"])
            max_disp = max(self.ss.displacements.items(), key=lambda x: abs(x[1]['dy']))
            peak_data = [["Category", "ID", "Value", "Unit"], ["Max Tension", max_tension['member_id'], f"{max_tension['force']:.2f}", "kN"], ["Max Compression", max_comp['member_id'], f"{max_comp['force']:.2f}", "kN"], ["Max Deflection", f"Node {max_disp[0]}", f"{abs(max_disp[1]['dy']*1000):.2f}", "mm"]]
            t = Table(peak_data); t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.blue), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
            elements.append(Paragraph("🏆 Structural Peak Summary", styles["Heading2"])); elements.append(t); elements.append(Spacer(1, 20))
            
            # Simplified diagram inclusion
            def add_fig(title, draw_func):
                elements.append(Paragraph(title, styles["Heading2"]))
                fig, ax = plt.subplots(figsize=(10, 5)); draw_func(ax); buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=120); plt.close(fig)
                buf.seek(0); img = RLImage(buf); img.drawWidth = 500; img.drawHeight = 250; elements.append(img)
            
            def draw_axial(ax):
                for i, r in enumerate(self.analysis_results):
                    el = self.ss.elements[i+1]; color = '#E74C3C' if r["force"] > 0 else '#2980B9'
                    ax.plot([el.vertex_1.x, el.vertex_2.x], [el.vertex_1.y, el.vertex_2.y], color=color, lw=2)
                    ax.text((el.vertex_1.x+el.vertex_2.x)/2, (el.vertex_1.y+el.vertex_2.y)/2, f"{r['force']:.1f}", fontsize=7)
                ax.axis('off')
            
            def draw_disp(ax):
                disps = self.ss.displacements
                for nid, node in self.ss.nodes.items():
                    ax.plot(node.vertex.x, node.vertex.y, 'ko')
                    ax.text(node.vertex.x, node.vertex.y, f"N{nid}:{disps[nid]['dy']*1000:.1f}mm", fontsize=6)
                ax.axis('off')

            add_fig("1. Axial Force Diagram", draw_axial); add_fig("2. Displacement Diagram", draw_disp)
            doc.build(elements); messagebox.showinfo("Success", f"Report generated: {fpath}")
        except Exception as e: messagebox.showerror("Export Error", str(e))

    def _rescale_graph_labels(self, fig, t): pass
    def scale_support_symbols(self, fig): pass
    def add_dimensions(self, fig): pass

if __name__ == "__main__":
    app = TrussAnalyzerPro(); app.mainloop()
