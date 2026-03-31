    def update_enhanced_plots(self):
        # Clear existing canvases
        for w in self.canvas_widgets: w.destroy()
        self.canvas_widgets.clear()
        if not self.ss: return

        ff = UNIT_FORCE_TO_KN[self.unit_force]
        lf = UNIT_LENGTH_TO_M[self.unit_length]

        # 1. Structure Model
        fig_struct = self.ss.show_structure(show=False)
        fig_struct.suptitle("1. Structure Model", fontsize=12, fontweight='bold')
        self._rescale_graph_labels(fig_struct, "structure")
        self.scale_support_symbols(fig_struct)
        self.add_dimensions(fig_struct)
        self._add_to_right_panel(fig_struct)

        # 2. Axial Force Diagram (Professional Visualization)
        fig_axial, ax = plt.subplots(figsize=(12, 8))
        ax.set_facecolor('white')
        try:
            elem_ids = list(self.ss.element_map.keys())
            max_f = max([abs(self.get_element_results(eid).get("N", 0.0)) for eid in elem_ids], default=1.0)
            for elem_id, elem in self.ss.elements.items():
                res = self.get_element_results(elem_id)
                force = res.get("N", 0.0)
                start, end = elem['start'], elem['end']
                color = '#E74C3C' if force > 0.1 else ('#2980B9' if force < -0.1 else '#7F8C8D')
                fill_color = '#FDEDEC' if force > 0.1 else ('#EBF5FB' if force < -0.1 else '#F2F4F4')
                lw = 3 + int(2 * abs(force) / max_f)
                ax.plot([start[0], end[0]], [start[1], end[1]], color=color, linewidth=lw, alpha=0.9)
                mid_x, mid_y = (start[0] + end[0])/2, (start[1] + end[1])/2
                angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
                if abs(angle) > 90: angle += 180
                ax.text(mid_x, mid_y, f"{force / ff:.1f}", fontsize=8, fontweight='bold', ha='center', va='center',
                       rotation=angle, bbox=dict(boxstyle="round,pad=0.2", fc=fill_color, ec=color, alpha=0.9))
            for nid, node in self.ss.nodes.items():
                ax.plot(node['x'], node['y'], 'ko', markersize=4, zorder=15)
            ax.set_aspect('equal'); ax.grid(True, linestyle='--', alpha=0.3)
            ax.set_title("Axial Force Diagram", fontsize=14, fontweight='bold')
            self._add_to_right_panel(fig_axial)
        except Exception: pass

        # 3. Displacement Diagram with Deflection Values
        fig_disp = self.ss.show_displacement(show=False)
        ax_disp = fig_disp.gca()
        fig_disp.suptitle("3. Displacement Diagram (Scaled)", fontsize=12, fontweight='bold')
        displacements = self.ss.displacements
        for nid, node in self.ss.nodes.items():
            if nid in displacements:
                dy = displacements[nid]['dy']
                ax_disp.text(node['x'], node['y'], f"N{nid}: {dy*1000:.1f}mm", 
                            fontsize=7, color='purple', ha='center', va='bottom')
        self.scale_support_symbols(fig_disp); self.add_dimensions(fig_disp)
        self._add_to_right_panel(fig_disp)

        # 4. Utilization Diagram
        fig_util, ax = plt.subplots(figsize=(12, 8))
        ax.set_facecolor('white')
        try:
            if self.analysis_results:
                for i, result in enumerate(self.analysis_results):
                    elem = self.ss.elements[i+1]; util = result["utilization"]
                    color = '#27AE60' if util <= 1.0 else '#E74C3C'
                    ax.plot([elem['start'][0], elem['end'][0]], [elem['start'][1], elem['end'][1]], color=color, lw=2 + min(util*3, 6))
                    mx, my = (elem['start'][0] + elem['end'][0])/2, (elem['start'][1] + elem['end'][1])/2
                    ax.text(mx, my, f"{util:.2f}", fontsize=9, ha='center', bbox=dict(boxstyle="round,pad=0.2", fc='white', alpha=0.8))
                ax.set_aspect('equal'); ax.grid(True, linestyle='--', alpha=0.3); ax.set_title("Utilization Diagram")
                self._add_to_right_panel(fig_util)
        except Exception: pass

    def _add_to_right_panel(self, fig):
        fig.set_facecolor("#f0f0f0")
        canvas = FigureCanvasTkAgg(fig, master=self.right_panel)
        canvas.draw()
        toolbar_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        toolbar_frame.pack(fill="x", padx=10)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame, pack_toolbar=False)
        toolbar.update(); toolbar.pack(side="left")
        w = canvas.get_tk_widget(); w.pack(fill="x", padx=10, pady=(0, 20))
        self.canvas_widgets.extend([w, toolbar_frame])

    def show_enhanced_results(self):
        """Enhanced results display with peak summaries"""
        for w in self.tab_res.winfo_children(): w.destroy()
        if not self.ss or not self.analysis_results:
            ctk.CTkLabel(self.tab_res, text="No analysis results available.", font=TYPO_SCALE["body"]).pack(pady=50)
            return
        
        # Calculate peaks
        max_tension = max(self.analysis_results, key=lambda x: x["force"])
        max_comp = min(self.analysis_results, key=lambda x: x["force"])
        max_disp_node = max(self.ss.displacements.items(), key=lambda x: abs(x[1]['dy']))

        # Peak Results Cards
        peaks_frame = ctk.CTkFrame(self.tab_res, fg_color=COLOR_PALETTE["secondary"], corner_radius=10)
        peaks_frame.pack(fill="x", padx=15, pady=15)
        ctk.CTkLabel(peaks_frame, text="🏆 STRUCTURAL PEAK RESULTS", font=TYPO_SCALE["h3"], text_color="white").pack(pady=10)
        
        peak_grid = ctk.CTkFrame(peaks_frame, fg_color="transparent")
        peak_grid.pack(fill="x", padx=20, pady=10)
        
        def add_card(label, val, unit, color):
            f = ctk.CTkFrame(peak_grid, fg_color="white", corner_radius=8, width=200, height=80)
            f.pack(side="left", expand=True, padx=10, pady=5); f.pack_propagate(False)
            ctk.CTkLabel(f, text=label, font=TYPO_SCALE["small"], text_color="gray").pack(pady=(5,0))
            ctk.CTkLabel(f, text=val, font=TYPO_SCALE["h2"], text_color=color).pack()
            ctk.CTkLabel(f, text=unit, font=TYPO_SCALE["small"], text_color="gray").pack()

        add_card("Max Tension", f"{max_tension['force']:.1f}", "kN", "#E74C3C")
        add_card("Max Compression", f"{max_comp['force']:.1f}", "kN", "#2980B9")
        add_card("Max Deflection", f"{abs(max_disp_node[1]['dy']*1000):.2f}", "mm", "#7C3AED")

        # Results table
        table_frame = ctk.CTkScrollableFrame(self.tab_res, height=400)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        res_header = ["Member", "Profile", "Force (kN)", "Type", "Utilization", "Status"]
        h_row = ctk.CTkFrame(table_frame, fg_color=COLOR_PALETTE["secondary"])
        h_row.pack(fill="x", pady=2)
        for h in res_header: ctk.CTkLabel(h_row, text=h, width=100, font=TYPO_SCALE["small"]).pack(side="left", padx=5)
        
        for r in self.analysis_results:
            row = ctk.CTkFrame(table_frame, fg_color=COLOR_PALETTE["danger"] if r["status"] == "FAIL" else COLOR_PALETTE["surface"])
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=r["member_id"], width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=r["profile"], width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=f"{r['force']:.1f}", width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=r["type"], width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=f"{r['utilization']:.2f}", width=100).pack(side="left", padx=5)
            ctk.CTkLabel(row, text=r["status"], width=100).pack(side="left", padx=5)

    def export_report(self):
        """Export a professional PDF analysis report with peak summaries and values on diagrams"""
        if not self.analysis_results:
            messagebox.showwarning("Warning", "No results to export.")
            return
        fpath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Documents", "*.pdf")])
        if not fpath: return
        try:
            import io
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, Image as RLImage
            doc = SimpleDocTemplate(fpath, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            elements, styles = [], getSampleStyleSheet()
            title_style = ParagraphStyle("Title", fontSize=22, textColor=colors.HexColor("#2563EB"), alignment=1)
            h2_style = ParagraphStyle("H2", fontSize=14, fontName="Helvetica-Bold", textColor=colors.HexColor("#1F2937"), spaceBefore=12, spaceAfter=8)
            elements.append(Paragraph("🏗️ Structural Analysis Report", title_style)); elements.append(Spacer(1, 20))
            
            # Peak Table
            max_tension = max(self.analysis_results, key=lambda x: x["force"])
            max_comp = min(self.analysis_results, key=lambda x: x["force"])
            max_d_node = max(self.ss.displacements.items(), key=lambda x: abs(x[1]['dy']))
            peak_data = [["Summary Peak Results", "ID", "Value", "Unit"],
                         ["Max Tension Force", max_tension['member_id'], f"{max_tension['force']:.2f}", "kN"],
                         ["Max Compression Force", max_comp['member_id'], f"{max_comp['force']:.2f}", "kN"],
                         ["Max Vertical Deflection", f"Node {max_d_node[0]}", f"{abs(max_d_node[1]['dy']*1000):.3f}", "mm"]]
            t_peaks = Table(peak_data, colWidths=[180, 80, 100, 80])
            t_peaks.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2563EB")), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
            elements.append(Paragraph("🏆 Structural Peak Summary", h2_style)); elements.append(t_peaks); elements.append(Spacer(1, 20))

            def fig_to_img(fig):
                buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                buf.seek(0); img = RLImage(buf); img.drawWidth = 500
                img.drawHeight = 500 * (img.drawHeight / img.drawWidth); return img

            # Diagrams
            elements.append(Paragraph("1. Structural Geometry", h2_style))
            f1 = self.ss.show_structure(show=False); self.scale_support_symbols(f1); elements.append(fig_to_img(f1)); plt.close(f1)
            
            elements.append(Paragraph("2. Axial Force Diagram (kN)", h2_style))
            f2, ax = plt.subplots(figsize=(10, 5))
            for i, r in enumerate(self.analysis_results):
                elem = self.ss.elements[i+1]; force = r["force"]
                color = '#E74C3C' if force > 0.1 else ('#2980B9' if force < -0.1 else '#7F8C8D')
                ax.plot([elem['start'][0], elem['end'][0]], [elem['start'][1], elem['end'][1]], color=color, lw=2)
                mx, my = (elem['start'][0] + elem['end'][0])/2, (elem['start'][1] + elem['end'][1])/2
                ax.text(mx, my, f"{force:.1f}", fontsize=7, ha='center', bbox=dict(boxstyle="round,pad=0.1", fc='white', alpha=0.8))
            ax.axis('off'); elements.append(fig_to_img(f2)); plt.close(f2)

            elements.append(PageBreak())
            elements.append(Paragraph("3. Displacement Diagram (Deflection Labels)", h2_style))
            f3 = self.ss.show_displacement(show=False); ax3 = f3.gca()
            for nid, d in self.ss.displacements.items():
                node = self.ss.nodes[nid]
                ax3.text(node['x'], node['y'], f"{d['dy']*1000:.1f}mm", fontsize=6, color='blue')
            elements.append(fig_to_img(f3)); plt.close(f3)

            elements.append(Paragraph("4. Member Utilization", h2_style))
            f4, ax = plt.subplots(figsize=(10, 5))
            for i, r in enumerate(self.analysis_results):
                elem = self.ss.elements[i+1]; util = r["utilization"]
                color = '#27AE60' if util <= 1.0 else '#E74C3C'
                ax.plot([elem['start'][0], elem['end'][0]], [elem['start'][1], elem['end'][1]], color=color, lw=2)
                mx, my = (elem['start'][0] + elem['end'][0])/2, (elem['start'][1] + elem['end'][1])/2
                ax.text(mx, my, f"{util:.2f}", fontsize=7, ha='center', bbox=dict(boxstyle="round,pad=0.1", fc='white', alpha=0.8))
            ax.axis('off'); elements.append(fig_to_img(f4)); plt.close(f4)

            doc.build(elements); messagebox.showinfo("Success", f"Full Report generated: {fpath}")
        except Exception as e: messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    app = TrussAnalyzerPro()
    app.mainloop()
