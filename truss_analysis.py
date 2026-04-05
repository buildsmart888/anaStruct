"""
TrussAnalysisEngine — FEA orchestration and member design checks.
No GUI dependency; receives a TrussModel and returns results.
"""
from __future__ import annotations

import math


# ── AISC 360-16 resistance / safety factors ──────────────────────────────────
_PHI_T  = 0.90   # LRFD tension yielding     (§D2)
_PHI_C  = 0.90   # LRFD compression          (§E1)
_OMEGA_T = 1.67  # ASD tension yielding      (§D2)
_OMEGA_C = 1.67  # ASD compression           (§E1)


# ── Free functions (used internally and callable by tests) ───────────────────

def calculate_buckling_stress(L: float, r: float, E: float, Fy: float) -> tuple[float, float]:
    """Critical buckling stress Fcr and slenderness KL/r per AISC 360-16 §E3."""
    sr = L / r
    Fe = (math.pi ** 2 * E) / (sr ** 2)
    Fcr = (0.658 ** (Fy / Fe)) * Fy if sr <= 4.71 * math.sqrt(E / Fy) else 0.877 * Fe
    return Fcr, sr


def check_member_stability(
    force: float,
    area: float,
    length: float,
    profile_data: dict,
    grade_data: dict,
    design_method: str = "LRFD",
) -> dict:
    """
    Return a result dict with keys:
      status, utilization, type, stress, design_method,
      design_capacity  (allowable stress, MPa),
      and for compression: critical_stress, slenderness.

    design_method : "LRFD" applies φ = 0.90
                    "ASD"  applies Ω = 1.67
    """
    dm = design_method.upper()
    if abs(force) < 0.001:
        return {
            "status": "OK", "utilization": 0.0,
            "type": "No Load", "stress": 0.0,
            "design_method": dm, "design_capacity": 0.0,
        }

    # force: kN  |  area: cm²  →  stress MPa
    # 1 kN = 1000 N;  1 cm² = 100 mm²  →  factor = 1000/100 = 10
    stress = abs(force) * 10.0 / area
    Fy     = grade_data["Fy"]
    E      = grade_data["E"]

    if force > 0:  # ── Tension — yield check (§D2) ─────────────────────────
        if dm == "LRFD":
            design_capacity = _PHI_T * Fy          # φt × Fy  (MPa)
        else:
            design_capacity = Fy / _OMEGA_T        # Fy / Ωt  (MPa)

        utilization = stress / design_capacity
        return {
            "status": "OK" if utilization <= 1.0 else "FAIL",
            "utilization": utilization,
            "type": "Tension",
            "stress": stress,
            "design_method": dm,
            "design_capacity": design_capacity,
        }

    else:  # ── Compression — buckling check (§E3) ──────────────────────────
        r_min = min(profile_data["rx"], profile_data["ry"]) * 10  # cm → mm
        Fcr, slenderness = calculate_buckling_stress(
            length * 1000, r_min, E, Fy
        )
        if dm == "LRFD":
            design_capacity = _PHI_C * Fcr         # φc × Fcr  (MPa)
        else:
            design_capacity = Fcr / _OMEGA_C       # Fcr / Ωc  (MPa)

        utilization = stress / design_capacity
        return {
            "status": "OK" if utilization <= 1.0 else "FAIL",
            "utilization": utilization,
            "type": "Compression",
            "stress": stress,
            "design_method": dm,
            "design_capacity": design_capacity,
            "critical_stress": Fcr,
            "slenderness": slenderness,
        }


# ── Engine class ─────────────────────────────────────────────────────────────

class TrussAnalysisEngine:
    """
    Stateless — receives a TrussModel + constants, returns results.
    Raises ValueError on input errors; FEMException on solver failure.
    """

    def build_and_solve(
        self,
        model,
        SystemElements,
        STEEL_GRADES: dict,
        STEEL_PROFILES: dict,
        LOAD_COMBINATIONS: dict,
    ):
        """
        Build a solved SystemElements instance from *model*.
        Returns the solved ss object.
        """
        combo_factors = LOAD_COMBINATIONS[model.design_method][model.selected_combo]
        ss = SystemElements()
        nj = len(model.nodes_data)

        # ── Step 1: Add elements ─────────────────────────────────────────────
        for i, el in enumerate(model.elements_data):
            if not (1 <= el["node_a"] <= nj and 1 <= el["node_b"] <= nj):
                raise ValueError(f"Member E{i+1}: node reference out of range (max N{nj})")
            profile = STEEL_PROFILES[el["profile"]]
            grade = STEEL_GRADES[profile["Grade"]]
            # E (MPa) × A (cm²) × 0.1 → EA (kN)
            ea = grade["E"] * profile["Area"] * 0.1
            n1 = model.nodes_data[el["node_a"] - 1]
            n2 = model.nodes_data[el["node_b"] - 1]
            ss.add_truss_element(location=[[n1["x"], n1["y"]], [n2["x"], n2["y"]]], EA=ea)

        # ── Step 2: Coordinate → anastruct node_id lookup ────────────────────
        # anastruct deduplicates coincident nodes by coordinate, so its node
        # IDs may not match model's 1-based indices.  Build a coord map here.
        coord_to_id: dict = {}
        try:
            if hasattr(ss, "nodes"):
                for nid, nd in ss.nodes.items():
                    coord_to_id[(round(nd["x"], 6), round(nd["y"], 6))] = nid
        except Exception:
            pass

        def _ana_id(model_idx_1based: int) -> int:
            """Resolve model node index → anastruct node ID."""
            if not coord_to_id:
                return model_idx_1based          # fallback for mocks / tests
            nd = model.nodes_data[model_idx_1based - 1]
            key = (round(nd["x"], 6), round(nd["y"], 6))
            return coord_to_id.get(key, model_idx_1based)

        # ── Step 3: Add supports ─────────────────────────────────────────────
        for i, n in enumerate(model.nodes_data):
            if n["support"] == "Pinned":
                ss.add_support_hinged(node_id=_ana_id(i + 1))
            elif n["support"] == "Roller":
                ss.add_support_roll(node_id=_ana_id(i + 1), direction=2)

        # ── Step 4: Accumulate factored loads per coordinate, then apply ─────
        # (anastruct's point_load overwrites previous calls on the same node)
        coord_fx: dict = {}
        coord_fy: dict = {}
        for i, ld in enumerate(model.loads_data):
            if not (1 <= ld["node_id"] <= nj):
                raise ValueError(f"Load #{i+1}: node N{ld['node_id']} does not exist")
            factor = combo_factors.get(ld["case"], 0.0)
            nd = model.nodes_data[ld["node_id"] - 1]
            key = (round(nd["x"], 6), round(nd["y"], 6))
            coord_fx[key] = coord_fx.get(key, 0.0) + ld["fx"] * factor
            coord_fy[key] = coord_fy.get(key, 0.0) + ld["fy"] * factor

        for key, fx in coord_fx.items():
            fy = coord_fy.get(key, 0.0)
            if fx != 0.0 or fy != 0.0:
                if coord_to_id:
                    ana_id = coord_to_id.get(key)
                else:
                    # fallback: match by index
                    ana_id = next(
                        (idx + 1 for idx, nd in enumerate(model.nodes_data)
                         if (round(nd["x"], 6), round(nd["y"], 6)) == key),
                        None,
                    )
                if ana_id is not None:
                    ss.point_load(node_id=ana_id, Fx=fx, Fy=fy)

        ss.solve()
        return ss

    def member_checks(
        self,
        model,
        ss,
        STEEL_GRADES: dict,
        STEEL_PROFILES: dict,
    ) -> list[dict]:
        """
        Perform stability checks for every element.
        Returns a list of result dicts (one per element, in order).
        """
        results = []
        dm = getattr(model, "design_method", "LRFD")
        for i, el in enumerate(model.elements_data):
            elem_id = i + 1
            res = ss.get_element_results(element_id=elem_id)
            profile = STEEL_PROFILES[el["profile"]]
            grade = STEEL_GRADES[profile["Grade"]]
            n1 = model.nodes_data[el["node_a"] - 1]
            n2 = model.nodes_data[el["node_b"] - 1]
            length = math.sqrt((n2["x"] - n1["x"]) ** 2 + (n2["y"] - n1["y"]) ** 2)
            force = res["Nmin"]
            check = check_member_stability(
                force, profile["Area"], length, profile, grade,
                design_method=dm,
            )
            check.update({
                "member_id": f"E{elem_id}",
                "profile": el["profile"],
                "force": force,
                "length": length,
            })
            results.append(check)
        return results
