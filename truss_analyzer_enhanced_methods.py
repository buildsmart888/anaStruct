"""
Enhanced methods for Truss Analyzer GUI - Stability Checks & Visualization
Phần เพิ่มเติมนี้ประกอบด้วยวิธี enhanced สำหรับ validation, stability check, และ improved visualization
"""

# Methods to add to TrussAnalyzerPro class

def perform_member_checks(self):
    """Comprehensive member stability and capacity checks per AISC 360-16"""
    if not self.ss or not self.ss.solved:
        return {}
    
    results = {"members": {}, "summary": {"ok": 0, "warning": 0, "critical": 0}}
    
    for elem_id in self.ss.element_map:
        el = self.elements_data[elem_id - 1]
        profile = STEEL_PROFILES[el["profile"]]
        steel_grade = STEEL_GRADES[profile["Grade"]]
        
        # Get element force (in kN)
        elem_results = self.ss.get_element_results(elem_id)
        force = elem_results.get("N")
        if force is None:
            force = elem_results.get("Nmin", 0.0)
        
        # Get element length
        n1, n2 = self.nodes_data[el["node_a"]-1], self.nodes_data[el["node_b"]-1]
        length = ((n2["x"] - n1["x"])**2 + (n2["y"] - n1["y"])**2)**0.5
        
        # Perform stability check
        stability = check_member_stability(force, profile["Area"], length, profile, steel_grade)
        
        results["members"][elem_id] = {
            "element_id": elem_id,
            "force": force,
            "length": length,
            "profile": el["profile"],
            "status": stability["status"],
            "utilization": stability["utilization"],
            "type": stability["type"],
            "details": stability
        }
        
        if stability["status"] == "OK":
            if stability["utilization"] > 0.8:
                results["summary"]["warning"] += 1
            else:
                results["summary"]["ok"] += 1
        else:
            results["summary"]["critical"] += 1
    
    return results

def update_enhanced_plots(self):
    """Update visualization with force colors and stability indicators"""
    if not self.ss:
        return
    
    # Create comprehensive results display
    try:
        # Structure with forces
        fig1 = self.create_force_diagram()
        # Displacement
        fig2 = self.ss.show_displacement(factor=500)
        # Stability chart
        fig3 = self.create_stability_chart()
        
        # Store for display
        self.analysis_plots = [fig1, fig2, fig3]
    except Exception as e:
        self.update_status(f"⚠️ Plotting error: {str(e)}", "error")

def create_force_diagram(self):
    """Create force diagram with color-coded members by stress state"""
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import matplotlib.patches as mpatches
    
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_facecolor('#f5f5f5')
    
    # Draw members with color coding
    for elem_id, member_info in self.analysis_results["members"].items():
        el = self.elements_data[elem_id - 1]
        n1, n2 = self.nodes_data[el["node_a"]-1], self.nodes_data[el["node_b"]-1]
        
        force = member_info["force"]
        util = member_info["utilization"]
        
        # Color based on utilization
        if util < 0.5:
            color, lw = '#2ECC71', 2  # Green - low stress
        elif util < 0.75:
            color, lw = '#F39C12', 2.5  # Orange - medium stress
        elif util < 1.0:
            color, lw = '#E74C3C', 3  # Red - high stress
        else:
            color, lw = '#C0392B', 4  # Dark red - over-stressed
        
        # Line style for tension/compression
        if force > 0:
            ls = '-'  # Solid for tension
        else:
            ls = '--'  # Dashed for compression
        
        # Draw member
        ax.plot([n1["x"], n2["x"]], [n1["y"], n2["y"]], 
               color=color, linewidth=lw, linestyle=ls, alpha=0.8, zorder=10)
        
        # Add force label
        mid_x = (n1["x"] + n2["x"]) / 2
        mid_y = (n1["y"] + n2["y"]) / 2
        force_type = "T" if force > 0 else "C"
        ax.text(mid_x, mid_y + 0.15, f"{force_type}:{abs(force):.1f}kN", 
               ha='center', va='bottom', fontsize=8, 
               bbox=dict(boxstyle="round,pad=0.3", facecolor=color, alpha=0.7))
    
    # Draw nodes
    for i, node in enumerate(self.nodes_data):
        ax.plot(node["x"], node["y"], 'ko', markersize=10, zorder=15)
        ax.text(node["x"], node["y"] - 0.3, f"N{i+1}", ha='center', fontsize=9, fontweight='bold')
        
        # Draw support symbols
        if node["support"] == "Pinned":
            triangle = plt.Polygon([(node["x"]-0.15, node["y"]-0.2), 
                                  (node["x"]+0.15, node["y"]-0.2),
                                  (node["x"], node["y"])], 
                                 color='red', alpha=0.8, zorder=5)
            ax.add_patch(triangle)
        elif node["support"] == "Roller":
            ax.plot([node["x"]-0.15, node["x"]+0.15], [node["y"]-0.2, node["y"]-0.2], 'r-', linewidth=3)
            circle = plt.Circle((node["x"], node["y"]-0.1), 0.05, color='red', alpha=0.8, zorder=5)
            ax.add_patch(circle)
    
    # Enhanced legend
    legend_elements = [
        Line2D([0], [0], color='#2ECC71', lw=2, label='Low Stress (< 50%)'),
        Line2D([0], [0], color='#F39C12', lw=2.5, label='Medium (50-75%)'),
        Line2D([0], [0], color='#E74C3C', lw=3, label='High (75-100%)'),
        Line2D([0], [0], color='#C0392B', lw=4, label='Over-stressed (>100%)'),
        Line2D([0], [0], color='black', lw=2, linestyle='-', label='Tension (+)'),
        Line2D([0], [0], color='black', lw=2, linestyle='--', label='Compression (-)'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9, title='Force Status')
    
    # Format
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.2, linestyle=':')
    ax.set_title(f"🔍 Axial Force Diagram - {self.selected_combo}", fontsize=14, fontweight='bold')
    ax.set_xlabel("X (m)", fontsize=11)
    ax.set_ylabel("Y (m)", fontsize=11)
    
    plt.tight_layout()
    return fig

def create_stability_chart(self):
    """Create member-by-member stability report chart"""
    import matplotlib.pyplot as plt
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    fig.patch.set_facecolor('#f5f5f5')
    
    # Bar chart of utilization ratios
    members = []
    utilizations = []
    statuses = []
    
    for elem_id, info in sorted(self.analysis_results["members"].items()):
        members.append(f"E{elem_id}")
        utilizations.append(min(info["utilization"], 1.2))  # Cap at 1.2 for display
        statuses.append(info["status"])
    
    colors = ['#2ECC71' if u < 0.5 else '#F39C12' if u < 0.75 else '#E74C3C' if u < 1.0 else '#C0392B' 
              for u in utilizations]
    
    bars = ax1.barh(members, utilizations, color=colors, alpha=0.8, edgecolor='black', linewidth=1)
    ax1.axvline(x=1.0, color='red', linestyle='--', linewidth=2, label='Capacity Limit (100%)')
    ax1.set_xlabel('Utilization Ratio', fontsize=11, fontweight='bold')
    ax1.set_title('📊 Member Utilization Ratios', fontsize=12, fontweight='bold')
    ax1.set_xlim(0, 1.2)
    ax1.grid(True, alpha=0.3, axis='x')
    ax1.legend()
    
    # Summary pie chart
    summary = self.analysis_results["summary"]
    sizes = [summary["ok"], summary["warning"], summary["critical"]]
    labels = [f'✓ Safe\n({summary["ok"]})', f'⚠ Warning\n({summary["warning"]})', f'✗ Critical\n({summary["critical"]})']
    colors_pie = ['#2ECC71', '#F39C12', '#E74C3C']
    
    wedges, texts, autotexts = ax2.pie(sizes, labels=labels, colors=colors_pie, autopct='%1.0f%%',
                                        startangle=90, textprops={'fontsize': 10, 'weight': 'bold'})
    ax2.set_title('🎯 Overall Design Status', fontsize=12, fontweight='bold')
    
    plt.tight_layout()
    return fig

def show_enhanced_results(self):
    """Display comprehensive analysis results in Results tab"""
    for w in self.tab_res.winfo_children(): w.destroy()
    
    # Summary panel
    summary_panel = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["surface"], corner_radius=10)
    summary_panel.pack(fill="x", padx=10, pady=10)
    
    summary = self.analysis_results["summary"]
    
    # Status indicators
    status_frame = ctk.CTkFrame(summary_panel, fg_color="transparent")
    status_frame.pack(fill="x", padx=15, pady=10)
    
    ctk.CTkLabel(status_frame, text="DESIGN STATUS", font=TYPO_SCALE["h3"], 
                text_color=COLOR_PALETTE["text_primary"]).pack()
    
    result_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
    result_frame.pack(fill="x", pady=10)
    
    # Status cards
    for label, count, color in [("✓ Safe", summary["ok"], "#2ECC71"),
                               ("⚠ Warning", summary["warning"], "#F39C12"),
                               ("✗ Critical", summary["critical"], "#E74C3C")]:
        card = ctk.CTkFrame(result_frame, fg_color=color, corner_radius=8)
        card.pack(side="left", padx=5, pady=5, fill="both", expand=True)
        
        ctk.CTkLabel(card, text=label, font=("Arial", 14, "bold"), text_color="white").pack(pady=10)
        ctk.CTkLabel(card, text=str(count), font=("Arial", 24, "bold"), text_color="white").pack(pady=5)
    
    # Detailed member results
    details_label = ctk.CTkLabel(self.tab_res, text="Member Analysis Details", 
                                font=TYPO_SCALE["h3"], text_color=COLOR_PALETTE["text_primary"])
    details_label.pack(anchor="w", padx=10, pady=(10, 5))
    
    # Table-like display
    header_frame = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["secondary"])
    header_frame.pack(fill="x", padx=10)
    
    for header_text, width in [("Member", 50), ("Type", 60), ("Force (kN)", 80), 
                               ("Length (m)", 80), ("Utilization", 100), ("Status", 70)]:
        ctk.CTkLabel(header_frame, text=header_text, width=width, font=TYPO_SCALE["small"]).pack(side="left", padx=5, pady=5)
    
    # Scrollable results
    scroll_frame = ctk.CTkScrollableFrame(self.tab_res, height=350, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    for elem_id, info in sorted(self.analysis_results["members"].items()):
        row_frame = ctk.CTkFrame(scroll_frame, fg_color=COLOR_PALETTE["surface"], corner_radius=5)
        row_frame.pack(fill="x", pady=2)
        
        # Color indicator
        util = info["utilization"]
        if util < 0.5:
            ind_color = "#2ECC71"
        elif util < 0.75:
            ind_color = "#F39C12"
        elif util < 1.0:
            ind_color = "#E74C3C"
        else:
            ind_color = "#C0392B"
        
        ctk.CTkLabel(row_frame, text=f"E{elem_id}", width=50, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(row_frame, text=info["type"], width=60, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        ctk.CTkLabel(row_frame, text=f"{info['force']:.1f}", width=80, font=TYPO_SCALE["mono"]).pack(side="left", padx=5)
        ctk.CTkLabel(row_frame, text=f"{info['length']:.2f}", width=80, font=TYPO_SCALE["mono"]).pack(side="left", padx=5)
        
        util_pct = f"{min(info['utilization']*100, 150):.1f}%"
        ctk.CTkLabel(row_frame, text=util_pct, width=100, font=TYPO_SCALE["mono"],
                    text_color=ind_color, text_color_disabled=ind_color).pack(side="left", padx=5)
        
        status_text = "✓ OK" if info["status"] == "OK" else "✗ FAIL"
        ctk.CTkLabel(row_frame, text=status_text, width=70, font=TYPO_SCALE["small"],
                    text_color=ind_color).pack(side="left", padx=5)
    
    # Action buttons
    action_frame = ctk.CTkFrame(self.tab_res, fg_color="transparent")
    action_frame.pack(fill="x", padx=10, pady=10)
    
    ctk.CTkButton(action_frame, text="📊 View Plots", height=35, 
                 fg_color=COLOR_PALETTE["primary"], command=self.show_analysis_plots).pack(side="left", padx=5)
    ctk.CTkButton(action_frame, text="💾 Export Report", height=35,
                 fg_color=COLOR_PALETTE["warning"], command=self.export_report).pack(side="left", padx=5)
    
    self.update_status(f"✓ Analysis Complete! {summary['ok']} OK, {summary['warning']} Warning, {summary['critical']} Critical", "success")

def draw_project_tab(self):
    """Project information tab"""
    for w in self.tab_proj.winfo_children(): w.destroy()
    
    form_frame = ctk.CTkScrollableFrame(self.tab_proj, fg_color="transparent")
    form_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    fields = [("Project Name", "name"), ("Engineer", "engineer"), ("Client", "client"),
             ("Location", "location"), ("Code", "code")]
    
    self.proj_entries = {}
    for label, key in fields:
        frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        ctk.CTkLabel(frame, text=label + ":", width=100, font=TYPO_SCALE["body"]).pack(side="left", padx=5)
        
        entry = ctk.CTkEntry(frame, font=TYPO_SCALE["body"])
        entry.insert(0, self.project_data.get(key, ""))
        entry.pack(side="left", fill="x", expand=True, padx=5)
        self.proj_entries[key] = entry
    
    # Date display
    date_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
    date_frame.pack(fill="x", pady=5)
    ctk.CTkLabel(date_frame, text="Date:", width=100, font=TYPO_SCALE["body"]).pack(side="left", padx=5)
    ctk.CTkLabel(date_frame, text=self.project_data["date"], font=TYPO_SCALE["body"]).pack(side="left", padx=5)

def draw_templates_tab(self):
    """Standard truss template selection"""
    for w in self.tab_templ.winfo_children(): w.destroy()
    
    ctk.CTkLabel(self.tab_templ, text="Standard Truss Templates", font=TYPO_SCALE["h3"],
                text_color=COLOR_PALETTE["text_primary"]).pack(anchor="w", padx=10, pady=10)
    
    templates = {
        "📐 Simple Triangle": [
            {"x": 0, "y": 0, "support": "Pinned"},
            {"x": 10, "y": 0, "support": "Roller"},
            {"x": 5, "y": 5, "support": "Free"}
        ],
        "🎪 Pratt Truss": [
            {"x": 0, "y": 0, "support": "Pinned"},
            {"x": 20, "y": 0, "support": "Roller"},
            {"x": 5, "y": 4, "support": "Free"},
            {"x": 10, "y": 4, "support": "Free"},
            {"x": 15, "y": 4, "support": "Free"}
        ],
        "🏢 Portal Frame": [
            {"x": 0, "y": 0, "support": "Fixed"},
            {"x": 15, "y": 0, "support": "Fixed"},
            {"x": 0, "y": 6, "support": "Free"},
            {"x": 15, "y": 6, "support": "Free"}
        ]
    }
    
    for template_name in templates:
        btn = ctk.CTkButton(self.tab_templ, text=template_name, height=40,
                           command=lambda name=template_name: self.load_template(name, templates[name]))
        btn.pack(fill="x", padx=10, pady=5)

def load_template(self, name, template_nodes):
    """Load a standard template"""
    self.nodes_data = template_nodes.copy()
    self.elements_data = []
    self.loads_data = []
    self.save_state()
    self.refresh_ui()
    self.update_status(f"✓ Loaded template: {name}", "success")

def show_analysis_plots(self):
    """Display analysis plots in a new window"""
    if not hasattr(self, 'analysis_plots'):
        messagebox.showwarning("⚠️ No Results", "Please run analysis first!")
        return
    
    import tkinter as tk
    plot_window = tk.Toplevel(self)
    plot_window.title("Analysis Results - Plots")
    plot_window.geometry("1400x900")
    
    tab_view = ctk.CTkTabview(plot_window)
    tab_view.pack(fill="both", expand=True, padx=10, pady=10)
    
    for i, fig in enumerate(self.analysis_plots):
        tab = tab_view.add(f"Plot {i+1}")
        
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        canvas = FigureCanvasTkAgg(fig, master=tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

def export_report(self):
    """Export comprehensive analysis report"""
    if not self.analysis_results:
        messagebox.showwarning("⚠️ No Results", "Please run analysis first!")
        return
    
    from matplotlib.backends.backend_pdf import PdfPages
    import datetime
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        initialfile=f"Truss_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    
    if not file_path: return
    
    try:
        with PdfPages(file_path) as pdf:
            # Page 1: Summary
            fig = plt.figure(figsize=(8.5, 11))
            ax = fig.add_subplot(111)
            ax.axis('off')
            
            summary_text = f"""
STRUCTURAL ANALYSIS REPORT
Project: {self.project_data['name']}
Engineer: {self.project_data['engineer']}
Date: {self.project_data['date']}
Design Code: {self.project_data['code']}
Method: {self.design_method}
Load Combination: {self.selected_combo}

ANALYSIS SUMMARY
================
Members: {len(self.analysis_results['members'])}
Safe Members: {self.analysis_results['summary']['ok']}
Warning Members: {self.analysis_results['summary']['warning']}
Critical Members: {self.analysis_results['summary']['critical']}

MEMBER DETAILS
================
"""
            for elem_id, info in sorted(self.analysis_results['members'].items()):
                summary_text += f"\nMember E{elem_id}:\n"
                summary_text += f"  Force: {info['force']:.2f} kN ({info['type']})\n"
                summary_text += f"  Utilization: {info['utilization']*100:.1f}%\n"
                summary_text += f"  Status: {info['status']}\n"
            
            ax.text(0.05, 0.95, summary_text, transform=ax.transAxes,
                   fontsize=9, verticalalignment='top', fontfamily='monospace',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Pages 2-4: Analysis plots
            if hasattr(self, 'analysis_plots'):
                for plot_fig in self.analysis_plots:
                    pdf.savefig(plot_fig, bbox_inches='tight')
        
        messagebox.showinfo("✓ Success", f"Report exported to:\n{file_path}")
        self.update_status(f"✓ Report exported: {file_path}", "success")
    except Exception as e:
        messagebox.showerror("❌ Export Error", f"Failed to export:\n{str(e)}")

def export_csv(self):
    """Export member data to CSV"""
    if not self.analysis_results:
        messagebox.showwarning("⚠️ No Results", "Please run analysis first!")
        return
    
    import csv
    import datetime
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        initialfile=f"Truss_Results_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )
    
    if not file_path: return
    
    try:
        with open(file_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Member", "Type", "Force(kN)", "Length(m)", "Profile", "Utilization(%)", "Status"])
            
            for elem_id, info in sorted(self.analysis_results["members"].items()):
                el = self.elements_data[elem_id - 1]
                writer.writerow([
                    f"E{elem_id}",
                    info["type"],
                    f"{info['force']:.2f}",
                    f"{info['length']:.2f}",
                    el["profile"],
                    f"{info['utilization']*100:.1f}",
                    info["status"]
                ])
        
        messagebox.showinfo("✓ Success", f"CSV exported to:\n{file_path}")
    except Exception as e:
        messagebox.showerror("❌ Export Error", f"Failed to export:\n{str(e)}")

def save_project(self):
    """Save project to JSON"""
    if not self.sync_data(show_errors=False):
        messagebox.showwarning("⚠️ Validation Error", "Please fix data errors first!")
        return
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        initialfile=f"{self.project_data['name'].replace(' ', '_')}.json"
    )
    
    if not file_path: return
    
    try:
        project = {
            "project": self.project_data,
            "nodes": self.nodes_data,
            "elements": self.elements_data,
            "loads": self.loads_data,
            "design_method": self.design_method
        }
        
        with open(file_path, 'w') as f:
            json.dump(project, f, indent=2)
        
        messagebox.showinfo("✓ Saved", f"Project saved to:\n{file_path}")
        self.update_status(f"✓ Project saved: {file_path}", "success")
    except Exception as e:
        messagebox.showerror("❌ Save Error", f"Failed to save:\n{str(e)}")

def load_project(self):
    """Load project from JSON"""
    file_path = filedialog.askopenfilename(
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    
    if not file_path: return
    
    try:
        with open(file_path, 'r') as f:
            project = json.load(f)
        
        self.project_data = project.get("project", self.project_data)
        self.nodes_data = project.get("nodes", [])
        self.elements_data = project.get("elements", [])
        self.loads_data = project.get("loads", [])
        self.design_method = project.get("design_method", "LRFD")
        
        self.save_state()
        self.refresh_ui()
        
        messagebox.showinfo("✓ Loaded", f"Project loaded from:\n{file_path}")
        self.update_status(f"✓ Project loaded: {file_path}", "success")
    except Exception as e:
        messagebox.showerror("❌ Load Error", f"Failed to load:\n{str(e)}")

def update_structure_preview(self, temp_ss):
    """Update live preview of structure (called while editing)"""
    # This would update a preview canvas - implementation depends on your UI layout
    pass
