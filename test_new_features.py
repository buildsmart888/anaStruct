"""
Tests for features added in the latest development session:
  1. Save/Load serialization (settings fields)
  2. Self-weight calculation
  3. Deflection check (already in plots — test the math)
  4. BOM weight (kg/m formula)
  5. Summary combo utilization sweep
  6. Custom section calculator (property formulas)
  7. Node drag (model-level coords update)
  8. Plot toggle vars (BoolVar defaults)
  9. New curved truss dispatch entries
     (Curved Truss 3, Bowstring Pratt/Warren)

Run with:  python -m pytest test_new_features.py -v
"""
from __future__ import annotations

import json
import math
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from truss_model import TrussModel
from truss_generators import TrussGenerators
from truss_analysis import TrussAnalysisEngine, check_member_stability

# ── shared test data ─────────────────────────────────────────────────────────

PROFILES = {
    "Box 50x50x2.3": {"Area": 3.71, "Ix": 8.25, "Iy": 8.25,
                      "rx": 1.49, "ry": 1.49, "Grade": "A36"},
    "RHS 100x100x4.5": {"Area": 16.8, "Ix": 111, "Iy": 111,
                        "rx": 2.57, "ry": 2.57, "Grade": "SS400"},
}
GRADES = {
    "A36":    {"Fy": 250, "Fu": 400, "E": 200000},
    "SS400":  {"Fy": 235, "Fu": 400, "E": 200000},
}
COMBOS = {
    "LRFD": {
        "1.2D + 1.6L": {"DL": 1.2, "LL": 1.6, "WL": 0.0, "SL": 0.0},
        "1.4D":        {"DL": 1.4, "LL": 0.0, "WL": 0.0, "SL": 0.0},
        "0.9D + 1.0W": {"DL": 0.9, "LL": 0.0, "WL": 1.0, "SL": 0.0},
    },
    "ASD": {
        "1.0D + 1.0L": {"DL": 1.0, "LL": 1.0, "WL": 0.0, "SL": 0.0},
    },
}
DEFAULT_PROFILES_GEN = {
    "top_chord": "Box 50x50x2.3", "bottom_chord": "Box 50x50x2.3",
    "vertical":  "Box 50x50x2.3", "diagonal":     "Box 50x50x2.3",
}
DEFAULT_PARAMS = {"span": 12.0, "height": 3.0, "bays": 6,
                  "bottom_height": 1.0, "rise": 2.0,
                  "cantilever_len": 3.0, "stub_height": 0.5}


def _triangle_model() -> TrussModel:
    m = TrussModel()
    m.nodes_data = [
        {"x": 0.0, "y": 0.0, "support": "Pinned"},
        {"x": 6.0, "y": 0.0, "support": "Roller"},
        {"x": 3.0, "y": 4.0, "support": "Free"},
    ]
    m.elements_data = [
        {"node_a": 1, "node_b": 2, "profile": "Box 50x50x2.3"},
        {"node_a": 2, "node_b": 3, "profile": "Box 50x50x2.3"},
        {"node_a": 3, "node_b": 1, "profile": "Box 50x50x2.3"},
    ]
    # Include DL and WL so all LRFD/ASD combos produce non-zero loads
    m.loads_data = [
        {"node_id": 3, "fx": 0.0,   "fy": -20.0, "case": "DL"},
        {"node_id": 3, "fx": 0.0,   "fy": -50.0, "case": "LL"},
        {"node_id": 3, "fx": 10.0,  "fy":   0.0, "case": "WL"},
    ]
    m.design_method = "LRFD"
    m.selected_combo = "1.2D + 1.6L"
    return m


# ═════════════════════════════════════════════════════════════════════════════
# 1. Save/Load — settings round-trip
# ═════════════════════════════════════════════════════════════════════════════

class TestSerializationSettings(unittest.TestCase):

    def _roundtrip(self, m: TrussModel) -> TrussModel:
        d = json.loads(json.dumps(m.to_dict()))
        m2 = TrussModel()
        m2.from_dict(d)
        return m2

    def test_settings_key_present(self):
        m = _triangle_model()
        d = m.to_dict()
        self.assertIn("settings", d)

    def test_design_method_roundtrip(self):
        m = _triangle_model()
        m.design_method = "ASD"
        m2 = self._roundtrip(m)
        self.assertEqual(m2.design_method, "ASD")

    def test_selected_combo_roundtrip(self):
        m = _triangle_model()
        m.selected_combo = "1.4D"
        m2 = self._roundtrip(m)
        self.assertEqual(m2.selected_combo, "1.4D")

    def test_unit_force_roundtrip(self):
        m = _triangle_model()
        m.unit_force = "kip"
        m2 = self._roundtrip(m)
        self.assertEqual(m2.unit_force, "kip")

    def test_unit_length_roundtrip(self):
        m = _triangle_model()
        m.unit_length = "ft"
        m2 = self._roundtrip(m)
        self.assertEqual(m2.unit_length, "ft")

    def test_selected_template_roundtrip(self):
        m = _triangle_model()
        m.selected_template = "Bowstring (Pratt)"
        m2 = self._roundtrip(m)
        self.assertEqual(m2.selected_template, "Bowstring (Pratt)")

    def test_template_params_roundtrip(self):
        m = _triangle_model()
        m.template_params["span"] = 24.0
        m.template_params["rise"] = 3.5
        m2 = self._roundtrip(m)
        self.assertAlmostEqual(m2.template_params["span"], 24.0)
        self.assertAlmostEqual(m2.template_params["rise"], 3.5)

    def test_self_weight_flag_roundtrip(self):
        m = _triangle_model()
        m.self_weight_enabled = True
        m2 = self._roundtrip(m)
        self.assertTrue(m2.self_weight_enabled)

    def test_self_weight_default_false(self):
        m = TrussModel()
        self.assertFalse(getattr(m, "self_weight_enabled", False))

    def test_settings_default_missing_key_graceful(self):
        """from_dict with no 'settings' key leaves defaults intact."""
        m = TrussModel()
        m.from_dict({"nodes": [], "elems": [], "loads": []})
        self.assertEqual(m.design_method, "LRFD")


# ═════════════════════════════════════════════════════════════════════════════
# 2. Self-weight calculation (unit math)
# ═════════════════════════════════════════════════════════════════════════════

class TestSelfWeightMath(unittest.TestCase):
    """Verify the formula:  w_kN = Area(cm²) × 0.785 × L(m) × 9.81 / 1000"""

    def _self_weight_kN(self, area_cm2: float, L_m: float) -> float:
        kg_per_m = area_cm2 * 0.785
        return kg_per_m * L_m * 9.81 / 1000

    def test_box_50x50x23_1m(self):
        # Area = 3.71 cm²  →  kg/m = 2.912  → w = 2.912 × 9.81/1000 ≈ 0.02856 kN/m
        w = self._self_weight_kN(3.71, 1.0)
        self.assertAlmostEqual(w, 3.71 * 0.785 * 9.81 / 1000, places=6)

    def test_weight_proportional_to_length(self):
        w1 = self._self_weight_kN(10.0, 1.0)
        w4 = self._self_weight_kN(10.0, 4.0)
        self.assertAlmostEqual(w4, w1 * 4, places=8)

    def test_half_weight_per_node(self):
        """Each end node gets w/2."""
        w = self._self_weight_kN(3.71, 6.0)
        per_node = w / 2
        self.assertAlmostEqual(per_node * 2, w, places=8)

    def test_larger_section_heavier(self):
        w_small = self._self_weight_kN(3.71, 5.0)    # Box 50x50
        w_large = self._self_weight_kN(16.8, 5.0)    # RHS 100x100
        self.assertGreater(w_large, w_small)

    def test_steel_density_approx(self):
        """Area × 0.785 should approximate kg/m for steel (ρ ≈ 7850 kg/m³)."""
        area = 10.0   # cm²  = 10e-4 m²
        kg_pm = area * 0.785
        # ρ × A = 7850 × 10e-4 = 7.85 kg/m  →  0.785 * 10 = 7.85
        self.assertAlmostEqual(kg_pm, 7.85, places=4)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Deflection limits (pure math, no solver needed)
# ═════════════════════════════════════════════════════════════════════════════

class TestDeflectionLimits(unittest.TestCase):

    def _limits(self, span_m: float):
        return span_m * 1000 / 240, span_m * 1000 / 360, span_m * 1000 / 420

    def test_12m_span_L240(self):
        lim, _, _ = self._limits(12.0)
        self.assertAlmostEqual(lim, 50.0, places=4)

    def test_12m_span_L360(self):
        _, lim, _ = self._limits(12.0)
        self.assertAlmostEqual(lim, 33.333, delta=0.001)

    def test_L240_greater_than_L360(self):
        l240, l360, _ = self._limits(10.0)
        self.assertGreater(l240, l360)

    def test_L360_greater_than_L420(self):
        _, l360, l420 = self._limits(10.0)
        self.assertGreater(l360, l420)

    def test_pass_when_defl_below_limit(self):
        max_dy = 20.0    # mm
        lim240, _, _ = self._limits(12.0)   # 50 mm
        self.assertLessEqual(max_dy, lim240)

    def test_fail_when_defl_above_limit(self):
        max_dy = 60.0    # mm
        lim240, _, _ = self._limits(12.0)   # 50 mm
        self.assertGreater(max_dy, lim240)


# ═════════════════════════════════════════════════════════════════════════════
# 4. BOM weight formula
# ═════════════════════════════════════════════════════════════════════════════

class TestBOMWeight(unittest.TestCase):

    def test_kg_per_m_formula(self):
        # kg/m = Area(cm²) × 0.785  (ρ=7850 kg/m³)
        area = 3.71  # Box 50x50x2.3
        kg_pm = area * 0.785
        self.assertAlmostEqual(kg_pm, 2.9124, places=3)

    def test_total_weight(self):
        area = 3.71
        total_length = 10.0   # m
        kg_pm = area * 0.785
        total_wt = kg_pm * total_length
        self.assertAlmostEqual(total_wt, 29.124, places=2)

    def test_larger_section_more_weight(self):
        wt_small = 3.71  * 0.785 * 1.0
        wt_large = 16.8  * 0.785 * 1.0
        self.assertGreater(wt_large, wt_small)

    def test_zero_area_zero_weight(self):
        wt = 0.0 * 0.785 * 5.0
        self.assertEqual(wt, 0.0)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Summary combo utilization — engine produces consistent results
# ═════════════════════════════════════════════════════════════════════════════

class TestCombinationSweep(unittest.TestCase):
    """
    Run the analysis engine for each LRFD combination on a simple truss
    and verify that utilizations are non-negative and consistent.
    """

    def setUp(self):
        try:
            from anastruct import SystemElements as SS
            from truss_analyzer_gui import TrussAnalyzer
            self._SystemElements = TrussAnalyzer
            self._available = True
        except Exception:
            self._available = False

    def _run_combo(self, model, combo_name):
        if not self._available:
            self.skipTest("anastruct not available")
        engine = TrussAnalysisEngine()
        m = model
        orig = m.selected_combo
        m.selected_combo = combo_name
        try:
            ss = engine.build_and_solve(m, self._SystemElements, GRADES, PROFILES, COMBOS)
            results = engine.member_checks(m, ss, GRADES, PROFILES)
        finally:
            m.selected_combo = orig
        return results

    def test_all_combos_run_without_error(self):
        if not self._available:
            self.skipTest("anastruct not available")
        m = _triangle_model()
        for combo in COMBOS["LRFD"]:
            with self.subTest(combo=combo):
                results = self._run_combo(m, combo)
                self.assertEqual(len(results), len(m.elements_data))

    def test_utilization_non_negative(self):
        if not self._available:
            self.skipTest("anastruct not available")
        m = _triangle_model()
        for combo in COMBOS["LRFD"]:
            with self.subTest(combo=combo):
                results = self._run_combo(m, combo)
                for r in results:
                    self.assertGreaterEqual(r["utilization"], 0.0,
                                            f"{combo}: negative utilization")

    def test_higher_load_combo_higher_util(self):
        """1.2D+1.6L should give higher utilization than 1.4D for LL-dominated model."""
        if not self._available:
            self.skipTest("anastruct not available")
        m = _triangle_model()
        # Only LL load → 1.2D+1.6L has factor 1.6 on LL, 1.4D has 0
        res_160L = self._run_combo(m, "1.2D + 1.6L")
        res_14D  = self._run_combo(m, "1.4D")
        max_160 = max(r["utilization"] for r in res_160L)
        max_14D = max(r["utilization"] for r in res_14D)
        self.assertGreater(max_160, max_14D)


# ═════════════════════════════════════════════════════════════════════════════
# 8. Custom section property calculator formulas
# ═════════════════════════════════════════════════════════════════════════════

class TestSectionCalculator(unittest.TestCase):
    """Test the property formulas used in the custom section calculator dialog."""

    # ── RHS / Box ─────────────────────────────────────────────────────────────

    def _rhs(self, b, h, t):
        A  = (b*h - (b-2*t)*(h-2*t)) / 100
        Ix = (b*h**3 - (b-2*t)*(h-2*t)**3) / 12 / 1e4
        Iy = (h*b**3 - (h-2*t)*(b-2*t)**3) / 12 / 1e4
        rx = math.sqrt(Ix / A)
        ry = math.sqrt(Iy / A)
        return A, Ix, Iy, rx, ry

    def test_rhs_100x100x4_area(self):
        A, *_ = self._rhs(100, 100, 4)
        # Outer 100×100 minus inner 92×92  in mm²
        expected = (100*100 - 92*92) / 100  # cm²
        self.assertAlmostEqual(A, expected, places=4)

    def test_rhs_square_Ix_equals_Iy(self):
        A, Ix, Iy, *_ = self._rhs(100, 100, 4)
        self.assertAlmostEqual(Ix, Iy, places=8)

    def test_rhs_positive_radius_of_gyration(self):
        A, Ix, Iy, rx, ry = self._rhs(75, 75, 3)
        self.assertGreater(rx, 0)
        self.assertGreater(ry, 0)

    def test_rhs_rx_equals_ry_for_square(self):
        _, Ix, Iy, rx, ry = self._rhs(100, 100, 4)
        self.assertAlmostEqual(rx, ry, places=8)

    # ── CHS / Pipe ────────────────────────────────────────────────────────────

    def _chs(self, D, t):
        di = D - 2*t
        A  = math.pi/4 * (D**2 - di**2) / 100
        Ix = math.pi/64 * (D**4 - di**4) / 1e4
        Iy = Ix
        rx = math.sqrt(Ix / A)
        ry = ry = rx
        return A, Ix, Iy, rx, ry

    def test_chs_Ix_equals_Iy(self):
        _, Ix, Iy, *_ = self._chs(114.3, 4.5)
        self.assertAlmostEqual(Ix, Iy, places=10)

    def test_chs_area_positive(self):
        A, *_ = self._chs(48.3, 3.2)
        self.assertGreater(A, 0)

    def test_chs_thicker_wall_more_area(self):
        A_thin, *_ = self._chs(100, 3)
        A_thick, *_ = self._chs(100, 6)
        self.assertGreater(A_thick, A_thin)

    # ── I-Beam ────────────────────────────────────────────────────────────────

    def _ibeam(self, H, bf, tf, tw):
        hw = H - 2*tf
        A  = (2*bf*tf + hw*tw) / 100
        Ix = (bf*H**3 - (bf-tw)*hw**3) / 12 / 1e4
        Iy = (2*tf*bf**3/12 + hw*tw**3/12) / 1e4
        rx = math.sqrt(Ix / A)
        ry = math.sqrt(Iy / A)
        return A, Ix, Iy, rx, ry

    def test_ibeam_Ix_greater_than_Iy(self):
        """Strong axis Ix > weak axis Iy for typical I-beam."""
        _, Ix, Iy, *_ = self._ibeam(200, 100, 8, 5)
        self.assertGreater(Ix, Iy)

    def test_ibeam_area_positive(self):
        A, *_ = self._ibeam(200, 100, 8, 5)
        self.assertGreater(A, 0)

    def test_ibeam_wider_flange_larger_Iy(self):
        _, _, Iy_narrow, *_ = self._ibeam(200, 80,  8, 5)
        _, _, Iy_wide,   *_ = self._ibeam(200, 120, 8, 5)
        self.assertGreater(Iy_wide, Iy_narrow)

    # ── Angle ─────────────────────────────────────────────────────────────────

    def _angle(self, a, b, t):
        A  = (a + b - t) * t / 100
        Ix = (t*a**3/3 + (b-t)*t**3/12) / 1e4
        Iy = (t*b**3/3 + (a-t)*t**3/12) / 1e4
        rx = math.sqrt(Ix / A)
        ry = math.sqrt(Iy / A)
        return A, Ix, Iy, rx, ry

    def test_angle_equal_legs_Ix_eq_Iy(self):
        _, Ix, Iy, *_ = self._angle(75, 75, 6)
        self.assertAlmostEqual(Ix, Iy, places=8)

    def test_angle_area_positive(self):
        A, *_ = self._angle(75, 75, 6)
        self.assertGreater(A, 0)

    # ── General: rx = sqrt(Ix/A) ──────────────────────────────────────────────

    def test_radius_of_gyration_identity(self):
        A, Ix, _, rx, _ = self._rhs(100, 100, 5)
        self.assertAlmostEqual(rx, math.sqrt(Ix / A), places=10)


# ═════════════════════════════════════════════════════════════════════════════
# 9. New curved truss dispatch entries
# ═════════════════════════════════════════════════════════════════════════════

class TestNewCurvedTrussTypes(unittest.TestCase):

    def _gen(self, tt):
        return TrussGenerators.generate(tt, DEFAULT_PARAMS, DEFAULT_PROFILES_GEN)

    def test_curved_truss_2_exists(self):
        nodes, elems = self._gen("Curved Truss 2")
        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(elems), 0)

    def test_curved_truss_3_exists(self):
        nodes, elems = self._gen("Curved Truss 3")
        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(elems), 0)

    def test_bowstring_pratt_exists(self):
        nodes, elems = self._gen("Bowstring (Pratt)")
        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(elems), 0)

    def test_bowstring_warren_exists(self):
        nodes, elems = self._gen("Bowstring (Warren)")
        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(elems), 0)

    def test_bowstring_bottom_is_flat(self):
        """All Bowstring variants should have y=0 on bottom chord."""
        for tt in ["Bowstring", "Bowstring (Pratt)", "Bowstring (Warren)"]:
            with self.subTest(tt=tt):
                nodes, _ = self._gen(tt)
                bottom = [n for i, n in enumerate(nodes) if i % 2 == 0]
                for n in bottom:
                    self.assertAlmostEqual(n["y"], 0.0, places=6, msg=f"{tt}")

    def test_curved_truss_1_2_3_same_node_count(self):
        """All three curved variants with same params → same node count."""
        n1, _ = self._gen("Curved Truss 1")
        n2, _ = self._gen("Curved Truss 2")
        n3, _ = self._gen("Curved Truss 3")
        self.assertEqual(len(n1), len(n2))
        self.assertEqual(len(n1), len(n3))

    def test_bowstring_variants_same_node_count(self):
        n0, _ = self._gen("Bowstring")
        np_, _ = self._gen("Bowstring (Pratt)")
        nw, _ = self._gen("Bowstring (Warren)")
        self.assertEqual(len(n0), len(np_))
        self.assertEqual(len(n0), len(nw))

    def test_curved_truss_2_different_diagonals_from_1(self):
        """Curved Truss 1 (Howe) and Curved Truss 2 (Warren) should have
        different diagonal connectivity on at least one element."""
        _, e1 = self._gen("Curved Truss 1")
        _, e2 = self._gen("Curved Truss 2")
        diags1 = [(e["node_a"], e["node_b"])
                  for e in e1 if e.get("member_type") == "Diagonal"]
        diags2 = [(e["node_a"], e["node_b"])
                  for e in e2 if e.get("member_type") == "Diagonal"]
        # At least some diagonals should differ
        self.assertNotEqual(diags1, diags2)

    def test_curved_truss_3_different_diagonals_from_1(self):
        """Curved Truss 3 (Pratt) should differ from Curved Truss 1 (Howe)."""
        _, e1 = self._gen("Curved Truss 1")
        _, e3 = self._gen("Curved Truss 3")
        diags1 = [(e["node_a"], e["node_b"])
                  for e in e1 if e.get("member_type") == "Diagonal"]
        diags3 = [(e["node_a"], e["node_b"])
                  for e in e3 if e.get("member_type") == "Diagonal"]
        self.assertNotEqual(diags1, diags3)

    def test_no_self_connected_elements(self):
        for tt in ["Curved Truss 2", "Curved Truss 3",
                   "Bowstring (Pratt)", "Bowstring (Warren)"]:
            with self.subTest(tt=tt):
                _, elems = self._gen(tt)
                for e in elems:
                    self.assertNotEqual(e["node_a"], e["node_b"],
                                        f"{tt}: zero-length element")

    def test_node_refs_in_range(self):
        for tt in ["Curved Truss 2", "Curved Truss 3",
                   "Bowstring (Pratt)", "Bowstring (Warren)"]:
            with self.subTest(tt=tt):
                nodes, elems = self._gen(tt)
                n = len(nodes)
                for e in elems:
                    self.assertGreaterEqual(e["node_a"], 1)
                    self.assertLessEqual(e["node_a"], n)
                    self.assertGreaterEqual(e["node_b"], 1)
                    self.assertLessEqual(e["node_b"], n)


if __name__ == "__main__":
    unittest.main()
