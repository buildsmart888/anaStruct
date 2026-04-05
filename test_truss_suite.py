"""
Unit tests for the refactored truss analyser modules.

Run with:  python -m pytest test_truss_suite.py -v
"""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

# Make sure the project directory is on the path
sys.path.insert(0, os.path.dirname(__file__))

from truss_model import TrussModel
from truss_generators import TrussGenerators
from truss_analysis import (
    TrussAnalysisEngine,
    calculate_buckling_stress,
    check_member_stability,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Shared test fixtures / helpers
# ═══════════════════════════════════════════════════════════════════════════════

PROFILES = {
    "Box 50x50x2.3": {"Area": 3.71, "Ix": 8.25, "Iy": 8.25, "rx": 1.49, "ry": 1.49, "Grade": "A36"},
    "I-Beam IPE160":  {"Area": 20.1, "Ix": 869,  "Iy": 68.3, "rx": 6.58, "ry": 1.84, "Grade": "A572-50"},
}
GRADES = {
    "A36":    {"Fy": 250, "Fu": 400, "E": 200000},
    "A572-50":{"Fy": 345, "Fu": 450, "E": 200000},
}
COMBINATIONS = {
    "LRFD": {
        "1.2D + 1.6L": {"DL": 1.2, "LL": 1.6, "WL": 0.0, "SL": 0.0},
        "1.4D":         {"DL": 1.4, "LL": 0.0, "WL": 0.0, "SL": 0.0},
    },
    "ASD": {
        "1.0D + 1.0L": {"DL": 1.0, "LL": 1.0, "WL": 0.0, "SL": 0.0},
    },
}

DEFAULT_PROFILES = {
    "top_chord":    "Box 50x50x2.3",
    "bottom_chord": "Box 50x50x2.3",
    "vertical":     "Box 50x50x2.3",
    "diagonal":     "Box 50x50x2.3",
}
DEFAULT_PARAMS = {"span": 12.0, "height": 3.0, "bays": 6,
                  "bottom_height": 1.0, "rise": 2.0,
                  "cantilever_len": 3.0, "stub_height": 0.5}


def _fresh_model() -> TrussModel:
    """Return a TrussModel with simple triangle geometry."""
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
    m.loads_data = [{"node_id": 3, "fx": 0.0, "fy": -50.0, "case": "LL"}]
    m.design_method = "LRFD"
    m.selected_combo = "1.2D + 1.6L"
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# TrussModel tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrussModelDefaults(unittest.TestCase):
    def setUp(self):
        self.m = TrussModel()

    def test_initial_nodes_count(self):
        self.assertEqual(len(self.m.nodes_data), 3)

    def test_initial_elements_count(self):
        self.assertEqual(len(self.m.elements_data), 3)

    def test_initial_loads_count(self):
        self.assertEqual(len(self.m.loads_data), 2)

    def test_design_method_default(self):
        self.assertEqual(self.m.design_method, "LRFD")

    def test_unit_defaults(self):
        self.assertEqual(self.m.unit_force, "kN")
        self.assertEqual(self.m.unit_length, "m")

    def test_history_starts_empty(self):
        self.assertEqual(self.m._history_index, -1)
        self.assertEqual(len(self.m._history), 0)


class TestTrussModelUndoRedo(unittest.TestCase):
    def setUp(self):
        self.m = _fresh_model()

    # ── save_state ────────────────────────────────────────────────────────────

    def test_save_state_increments_index(self):
        self.m.save_state()
        self.assertEqual(self.m._history_index, 0)
        self.m.save_state()
        self.assertEqual(self.m._history_index, 1)

    def test_save_state_stores_deepcopy(self):
        self.m.save_state()
        orig_x = self.m.nodes_data[0]["x"]
        self.m.nodes_data[0]["x"] = 999.0
        # History snapshot should not be mutated
        self.assertEqual(self.m._history[0]["nodes"][0]["x"], orig_x)

    def test_save_state_trims_future_on_branch(self):
        self.m.save_state()   # idx=0
        self.m.save_state()   # idx=1
        self.m.undo()         # idx=0
        self.m.save_state()   # idx=1 — future (old idx=1) trimmed
        self.assertEqual(len(self.m._history), 2)
        self.assertEqual(self.m._history_index, 1)

    def test_history_capped_at_50(self):
        for _ in range(60):
            self.m.save_state()
        self.assertLessEqual(len(self.m._history), 50)

    # ── undo ──────────────────────────────────────────────────────────────────

    def test_undo_restores_nodes(self):
        self.m.save_state()
        original_nodes = copy.deepcopy(self.m.nodes_data)
        self.m.nodes_data.append({"x": 99, "y": 99, "support": "Free"})
        self.m.save_state()
        self.assertTrue(self.m.undo())
        self.assertEqual(self.m.nodes_data, original_nodes)

    def test_undo_restores_elements(self):
        self.m.save_state()
        self.m.elements_data.append({"node_a": 1, "node_b": 3, "profile": "Box 50x50x2.3"})
        self.m.save_state()
        self.m.undo()
        self.assertEqual(len(self.m.elements_data), 3)

    def test_undo_restores_loads(self):
        self.m.save_state()
        self.m.loads_data[0]["fy"] = -999.0
        self.m.save_state()
        self.m.undo()
        self.assertEqual(self.m.loads_data[0]["fy"], -50.0)

    def test_undo_returns_false_at_start(self):
        self.m.save_state()          # only one state, can't undo
        self.assertFalse(self.m.undo())

    def test_undo_returns_false_with_no_history(self):
        self.assertFalse(self.m.undo())

    def test_undo_does_not_mutate_restored_state(self):
        """Restored state should be a deepcopy, not a reference to history."""
        self.m.save_state()
        self.m.nodes_data.append({"x": 1, "y": 1, "support": "Free"})
        self.m.save_state()
        self.m.undo()
        # Mutate current nodes — history should stay clean
        self.m.nodes_data[0]["x"] = 777.0
        self.assertNotEqual(self.m._history[0]["nodes"][0]["x"], 777.0)

    # ── redo ──────────────────────────────────────────────────────────────────

    def test_redo_reapplies_state(self):
        self.m.save_state()
        self.m.nodes_data.append({"x": 10, "y": 10, "support": "Free"})
        self.m.save_state()
        self.m.undo()
        self.assertEqual(len(self.m.nodes_data), 3)
        self.assertTrue(self.m.redo())
        self.assertEqual(len(self.m.nodes_data), 4)

    def test_redo_returns_false_at_end(self):
        self.m.save_state()
        self.assertFalse(self.m.redo())

    def test_undo_redo_sequence(self):
        self.m.nodes_data[0]["x"] = 1.0; self.m.save_state()
        self.m.nodes_data[0]["x"] = 2.0; self.m.save_state()
        self.m.nodes_data[0]["x"] = 3.0; self.m.save_state()
        self.m.undo(); self.assertEqual(self.m.nodes_data[0]["x"], 2.0)
        self.m.undo(); self.assertEqual(self.m.nodes_data[0]["x"], 1.0)
        self.m.redo(); self.assertEqual(self.m.nodes_data[0]["x"], 2.0)


class TestTrussModelSerialisation(unittest.TestCase):
    def setUp(self):
        self.m = _fresh_model()

    def test_to_dict_keys(self):
        d = self.m.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("elems", d)
        self.assertIn("loads", d)
        self.assertIn("project", d)

    def test_to_dict_nodes_match(self):
        d = self.m.to_dict()
        self.assertEqual(d["nodes"], self.m.nodes_data)

    def test_roundtrip(self):
        original = self.m.to_dict()
        m2 = TrussModel()
        m2.from_dict(original)
        self.assertEqual(m2.nodes_data, self.m.nodes_data)
        self.assertEqual(m2.elements_data, self.m.elements_data)
        self.assertEqual(m2.loads_data, self.m.loads_data)

    def test_from_dict_updates_project(self):
        d = self.m.to_dict()
        d["project"]["name"] = "Test Project"
        m2 = TrussModel()
        m2.from_dict(d)
        self.assertEqual(m2.project_data["name"], "Test Project")

    def test_from_dict_without_project_key_leaves_defaults(self):
        d = {"nodes": [], "elems": [], "loads": []}
        m2 = TrussModel()
        original_name = m2.project_data["name"]
        m2.from_dict(d)
        self.assertEqual(m2.project_data["name"], original_name)

    def test_json_roundtrip(self):
        """to_dict result should survive JSON encode/decode."""
        d = self.m.to_dict()
        reloaded = json.loads(json.dumps(d))
        m2 = TrussModel()
        m2.from_dict(reloaded)
        self.assertEqual(m2.nodes_data[0]["x"], self.m.nodes_data[0]["x"])


# ═══════════════════════════════════════════════════════════════════════════════
# TrussGenerators tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrussGeneratorsCommon(unittest.TestCase):
    """Common structural rules that every generator must satisfy."""

    ALL_TYPES = list(TrussGenerators._DISPATCH.keys())

    def _check(self, truss_type, params=None, profiles=None):
        p = params or DEFAULT_PARAMS
        pr = profiles or DEFAULT_PROFILES
        nodes, elements = TrussGenerators.generate(truss_type, p, pr)
        return nodes, elements

    # ── Basic output sanity ───────────────────────────────────────────────────

    def test_returns_two_lists(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                nodes, elements = self._check(tt)
                self.assertIsInstance(nodes, list, tt)
                self.assertIsInstance(elements, list, tt)

    def test_non_empty_output(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                nodes, elements = self._check(tt)
                self.assertGreater(len(nodes), 0, f"{tt}: no nodes")
                self.assertGreater(len(elements), 0, f"{tt}: no elements")

    def test_node_keys_present(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                nodes, _ = self._check(tt)
                for i, n in enumerate(nodes):
                    self.assertIn("x", n, f"{tt} node {i}")
                    self.assertIn("y", n, f"{tt} node {i}")
                    self.assertIn("support", n, f"{tt} node {i}")

    def test_element_keys_present(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                _, elements = self._check(tt)
                for i, e in enumerate(elements):
                    self.assertIn("node_a", e, f"{tt} elem {i}")
                    self.assertIn("node_b", e, f"{tt} elem {i}")
                    self.assertIn("profile", e, f"{tt} elem {i}")

    def test_no_self_connected_elements(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                _, elements = self._check(tt)
                for e in elements:
                    self.assertNotEqual(e["node_a"], e["node_b"],
                                        f"{tt}: element connects node to itself")

    def test_node_references_in_range(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                nodes, elements = self._check(tt)
                n = len(nodes)
                for e in elements:
                    self.assertGreaterEqual(e["node_a"], 1, tt)
                    self.assertGreaterEqual(e["node_b"], 1, tt)
                    self.assertLessEqual(e["node_a"], n, tt)
                    self.assertLessEqual(e["node_b"], n, tt)

    def test_exactly_one_pinned_and_one_roller(self):
        """All generators should produce exactly 1 Pinned + 1 Roller support."""
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                nodes, _ = self._check(tt)
                supports = [n["support"] for n in nodes]
                self.assertEqual(supports.count("Pinned"), 1,
                                 f"{tt}: expected 1 Pinned, got {supports.count('Pinned')}")
                self.assertEqual(supports.count("Roller"), 1,
                                 f"{tt}: expected 1 Roller, got {supports.count('Roller')}")

    def test_profile_values_come_from_input(self):
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                _, elements = self._check(tt)
                allowed = set(DEFAULT_PROFILES.values())
                for e in elements:
                    self.assertIn(e["profile"], allowed, f"{tt}: unknown profile {e['profile']}")

    # ── Geometry constraints ──────────────────────────────────────────────────

    def test_span_respected(self):
        """Rightmost node x should equal the requested span (±1%)."""
        for tt in self.ALL_TYPES:
            with self.subTest(truss_type=tt):
                if tt in ("Single Cantilever",):
                    continue   # cantilever extends beyond span by design
                nodes, _ = self._check(tt)
                max_x = max(n["x"] for n in nodes)
                self.assertAlmostEqual(max_x, DEFAULT_PARAMS["span"], delta=DEFAULT_PARAMS["span"] * 0.01,
                                       msg=tt)

    def test_unknown_type_falls_back_to_warren(self):
        nodes_w, elems_w = TrussGenerators.generate("Warren", DEFAULT_PARAMS, DEFAULT_PROFILES)
        nodes_u, elems_u = TrussGenerators.generate("__nonexistent__", DEFAULT_PARAMS, DEFAULT_PROFILES)
        self.assertEqual(len(nodes_w), len(nodes_u))
        self.assertEqual(len(elems_w), len(elems_u))


class TestTrussGeneratorsSpecific(unittest.TestCase):
    """Type-specific structural checks."""

    def _gen(self, tt, params=None):
        return TrussGenerators.generate(tt, params or DEFAULT_PARAMS, DEFAULT_PROFILES)

    def test_warren_node_count(self):
        bays = DEFAULT_PARAMS["bays"]
        nodes, _ = self._gen("Warren")
        self.assertEqual(len(nodes), (bays + 1) * 2)

    def test_howe_even_bays_enforced(self):
        p = {**DEFAULT_PARAMS, "bays": 5}   # odd
        nodes, _ = TrussGenerators.generate("Howe", p, DEFAULT_PROFILES)
        # Should auto-correct to 6 bays → 14 nodes
        self.assertEqual(len(nodes), 14)

    def test_king_post_exactly_4_nodes(self):
        nodes, _ = self._gen("King Post")
        self.assertEqual(len(nodes), 4)

    def test_king_post_exactly_5_elements(self):
        _, elements = self._gen("King Post")
        self.assertEqual(len(elements), 5)

    def test_fink_minimum_bays(self):
        p = {**DEFAULT_PARAMS, "bays": 2}   # below minimum of 4
        nodes, elements = TrussGenerators.generate("Fink", p, DEFAULT_PROFILES)
        self.assertGreater(len(nodes), 0)
        self.assertGreater(len(elements), 0)

    def test_bowstring_bottom_chord_y_is_zero(self):
        nodes, _ = self._gen("Bowstring")
        bottom = [n for i, n in enumerate(nodes) if i % 2 == 0]
        for n in bottom:
            self.assertAlmostEqual(n["y"], 0.0, places=6)

    def test_scissors_has_raised_bottom_chord(self):
        """Scissors bottom chord should be above y=0 (except at ends)."""
        nodes, _ = self._gen("Scissors")
        interior_bottom = [
            n for i, n in enumerate(nodes)
            if i % 2 == 0 and n["support"] == "Free"
        ]
        for n in interior_bottom:
            self.assertGreater(n["y"], 0.0)

    def test_cantilever_extends_beyond_span(self):
        p = {**DEFAULT_PARAMS, "span": 10.0, "cantilever_len": 3.0}
        nodes, _ = TrussGenerators.generate("Single Cantilever", p, DEFAULT_PROFILES)
        max_x = max(n["x"] for n in nodes)
        self.assertGreater(max_x, p["span"])

    def test_half_howe_monotonic_top_chord(self):
        """Mono truss top chord should rise from left to right."""
        nodes, _ = self._gen("Half Howe")
        top_nodes = [n for i, n in enumerate(nodes) if i % 2 == 1]
        ys = [n["y"] for n in top_nodes]
        self.assertEqual(ys, sorted(ys))


class TestDefaultLoads(unittest.TestCase):
    def test_returns_two_loads(self):
        nodes = [{"x": i, "y": 0} for i in range(10)]
        loads = TrussGenerators.default_loads(nodes)
        self.assertEqual(len(loads), 2)

    def test_load_cases(self):
        nodes = [{"x": i, "y": 0} for i in range(10)]
        loads = TrussGenerators.default_loads(nodes)
        cases = {l["case"] for l in loads}
        self.assertIn("DL", cases)
        self.assertIn("LL", cases)

    def test_node_id_is_midspan(self):
        nodes = [{"x": i, "y": 0} for i in range(10)]
        loads = TrussGenerators.default_loads(nodes)
        for ld in loads:
            self.assertEqual(ld["node_id"], 5)

    def test_single_node_does_not_crash(self):
        nodes = [{"x": 0, "y": 0}]
        loads = TrussGenerators.default_loads(nodes)
        self.assertEqual(loads[0]["node_id"], 1)

    def test_empty_list_does_not_crash(self):
        loads = TrussGenerators.default_loads([])
        self.assertEqual(loads[0]["node_id"], 1)


# ═══════════════════════════════════════════════════════════════════════════════
# truss_analysis.py — standalone functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateBucklingStress(unittest.TestCase):
    """AISC 360-16 buckling stress formula."""

    def test_returns_tuple_of_two(self):
        Fcr, sr = calculate_buckling_stress(3000, 15, 200000, 250)
        self.assertIsInstance(Fcr, float)
        self.assertIsInstance(sr, float)

    def test_slenderness_ratio_correct(self):
        _, sr = calculate_buckling_stress(3000, 15, 200000, 250)
        self.assertAlmostEqual(sr, 3000 / 15, places=6)

    def test_inelastic_regime_gives_higher_Fcr(self):
        """Short column (small L/r) → inelastic → Fcr closer to Fy."""
        Fcr_short, _ = calculate_buckling_stress(500,  20, 200000, 250)
        Fcr_long,  _ = calculate_buckling_stress(5000, 20, 200000, 250)
        self.assertGreater(Fcr_short, Fcr_long)

    def test_elastic_regime_fcr_below_fy(self):
        """Slender column (high L/r) → elastic buckling → Fcr << Fy."""
        Fy = 250
        Fcr, _ = calculate_buckling_stress(10000, 15, 200000, Fy)
        self.assertLess(Fcr, Fy)

    def test_transition_threshold(self):
        """L/r = 4.71√(E/Fy) is the inelastic/elastic boundary."""
        E, Fy = 200000, 250
        threshold_sr = 4.71 * math.sqrt(E / Fy)
        # Just below threshold → inelastic branch
        L_in  = (threshold_sr - 1) * 15
        L_el  = (threshold_sr + 1) * 15
        Fcr_in, _  = calculate_buckling_stress(L_in,  15, E, Fy)
        Fcr_el, _  = calculate_buckling_stress(L_el,  15, E, Fy)
        self.assertGreater(Fcr_in, Fcr_el)

    def test_Fcr_positive(self):
        Fcr, _ = calculate_buckling_stress(3000, 15, 200000, 250)
        self.assertGreater(Fcr, 0)


class TestCheckMemberStability(unittest.TestCase):
    PROFILE = {"Area": 10.0, "rx": 2.0, "ry": 2.0}
    GRADE   = {"Fy": 250, "Fu": 400, "E": 200000}

    def _check(self, force, length=3.0):
        return check_member_stability(force, self.PROFILE["Area"], length, self.PROFILE, self.GRADE)

    # ── No-load case ──────────────────────────────────────────────────────────

    def test_zero_force_is_ok(self):
        r = self._check(0.0)
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["utilization"], 0.0)
        self.assertEqual(r["type"], "No Load")

    def test_tiny_force_treated_as_zero(self):
        r = self._check(0.0009)
        self.assertEqual(r["type"], "No Load")

    # ── Tension ───────────────────────────────────────────────────────────────

    def test_tension_type_label(self):
        r = self._check(10.0)
        self.assertEqual(r["type"], "Tension")

    def test_tension_stress_formula(self):
        force = 20.0   # kN
        area  = 10.0   # cm²
        r = check_member_stability(force, area, 3.0, self.PROFILE, self.GRADE)
        expected_stress = force * 10.0 / area   # MPa
        self.assertAlmostEqual(r["stress"], expected_stress, places=4)

    def test_tension_ok_below_fy(self):
        # stress = 10 * 10 / 10 = 10 MPa << Fy=250
        r = self._check(10.0)
        self.assertEqual(r["status"], "OK")
        self.assertLess(r["utilization"], 1.0)

    def test_tension_fail_above_fy(self):
        # stress = 10 * 500 / 10 = 500 MPa > Fy=250
        r = self._check(500.0)
        self.assertEqual(r["status"], "FAIL")
        self.assertGreater(r["utilization"], 1.0)

    def test_tension_utilization_proportional(self):
        r1 = self._check(10.0)
        r2 = self._check(20.0)
        self.assertAlmostEqual(r2["utilization"], 2 * r1["utilization"], places=6)

    def test_tension_uses_fy_not_fu(self):
        """Utilization should be stress/Fy, not stress/Fu."""
        force = 25.0  # kN
        area  = 10.0  # cm²  → stress = 25 MPa
        grade = {"Fy": 250, "Fu": 400, "E": 200000}
        r = check_member_stability(force, area, 3.0, self.PROFILE, grade)
        expected = (force * 10.0 / area) / grade["Fy"]
        self.assertAlmostEqual(r["utilization"], expected, places=6)

    # ── Compression ───────────────────────────────────────────────────────────

    def test_compression_type_label(self):
        r = self._check(-10.0)
        self.assertEqual(r["type"], "Compression")

    def test_compression_has_slenderness(self):
        r = self._check(-10.0)
        self.assertIn("slenderness", r)
        self.assertIn("critical_stress", r)

    def test_compression_ok_for_light_load(self):
        r = self._check(-1.0, length=1.0)
        self.assertEqual(r["status"], "OK")

    def test_compression_fail_for_heavy_load(self):
        # Very large compression force on small profile
        profile = {"Area": 1.0, "rx": 0.5, "ry": 0.5}
        r = check_member_stability(-500.0, 1.0, 10.0, profile, self.GRADE)
        self.assertEqual(r["status"], "FAIL")

    def test_compression_slenderness_scales_with_length(self):
        r1 = self._check(-10.0, length=1.0)
        r2 = self._check(-10.0, length=2.0)
        self.assertAlmostEqual(r2["slenderness"], 2 * r1["slenderness"], places=4)

    def test_compression_critical_stress_positive(self):
        r = self._check(-10.0)
        self.assertGreater(r["critical_stress"], 0)

    def test_compression_uses_min_radius_of_gyration(self):
        """r_min should be the smaller of rx, ry."""
        profile_asym = {"Area": 10.0, "rx": 5.0, "ry": 1.0}
        r = check_member_stability(-10.0, 10.0, 3.0, profile_asym, self.GRADE)
        # slenderness = L*1000 / (ry*10) = 3000/10 = 300
        self.assertAlmostEqual(r["slenderness"], 300.0, places=2)

    # ── Return dict keys ──────────────────────────────────────────────────────

    def test_result_has_required_keys_tension(self):
        r = self._check(10.0)
        for k in ("status", "utilization", "type", "stress"):
            self.assertIn(k, r)

    def test_result_has_required_keys_compression(self):
        r = self._check(-10.0)
        for k in ("status", "utilization", "type", "stress", "slenderness", "critical_stress"):
            self.assertIn(k, r)

    def test_status_is_ok_or_fail(self):
        for force in [-500, -10, 0, 10, 500]:
            with self.subTest(force=force):
                r = self._check(float(force))
                self.assertIn(r["status"], ("OK", "FAIL"))


# ═══════════════════════════════════════════════════════════════════════════════
# TrussAnalysisEngine tests  (using mocks — no anastruct required)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_mock_ss():
    """Return a mock SystemElements that records calls."""
    ss = MagicMock()
    ss.solve.return_value = None
    ss.get_element_results.return_value = {"Nmin": -10.0, "Nmax": 0.0, "N": -10.0}
    return ss


def _make_ss_class(ss_instance):
    """Wrap a mock ss in a callable factory."""
    return lambda: ss_instance


class TestTrussAnalysisEngineBuildAndSolve(unittest.TestCase):
    def setUp(self):
        self.engine = TrussAnalysisEngine()
        self.model = _fresh_model()
        self.ss_mock = _make_mock_ss()
        self.SS = _make_ss_class(self.ss_mock)

    def _solve(self):
        return self.engine.build_and_solve(
            self.model, self.SS, GRADES, PROFILES, COMBINATIONS
        )

    def test_returns_ss_object(self):
        result = self._solve()
        self.assertIs(result, self.ss_mock)

    def test_solve_is_called(self):
        self._solve()
        self.ss_mock.solve.assert_called_once()

    def test_elements_added_for_each_member(self):
        self._solve()
        self.assertEqual(self.ss_mock.add_truss_element.call_count,
                         len(self.model.elements_data))

    def test_pinned_support_added(self):
        self._solve()
        self.ss_mock.add_support_hinged.assert_called()

    def test_roller_support_added(self):
        self._solve()
        self.ss_mock.add_support_roll.assert_called()

    def test_load_applied_with_combo_factor(self):
        """LL load with factor 1.6 → Fy should be scaled."""
        self._solve()
        calls = self.ss_mock.point_load.call_args_list
        # model has one LL load: fy=-50, factor=1.6 → -80
        fy_values = [c.kwargs.get("Fy", c[1].get("Fy")) for c in calls
                     if "Fy" in (c.kwargs or c[1])]
        self.assertTrue(any(abs(fy - (-80.0)) < 0.01 for fy in fy_values),
                        f"Expected -80.0 in {fy_values}")

    def test_ea_computed_correctly(self):
        """EA = E × Area × 0.1 for Box 50x50x2.3."""
        self._solve()
        expected_ea = GRADES["A36"]["E"] * PROFILES["Box 50x50x2.3"]["Area"] * 0.1
        calls = self.ss_mock.add_truss_element.call_args_list
        for c in calls:
            ea = c.kwargs.get("EA", c[1].get("EA"))
            self.assertAlmostEqual(ea, expected_ea, places=2)

    def test_invalid_node_reference_raises(self):
        self.model.elements_data.append({"node_a": 1, "node_b": 99, "profile": "Box 50x50x2.3"})
        with self.assertRaises(ValueError):
            self._solve()

    def test_invalid_load_node_raises(self):
        self.model.loads_data.append({"node_id": 99, "fx": 0, "fy": -10, "case": "LL"})
        with self.assertRaises(ValueError):
            self._solve()

    def test_zero_factor_load_not_applied(self):
        """DL load with 1.2D+1.6L combo: factor=1.2 — NOT zero, should be applied.
           Use a case not in the combo (e.g. WL factor=0) to test skipping."""
        self.model.loads_data = [{"node_id": 1, "fx": 0, "fy": -50, "case": "WL"}]
        ss2 = _make_mock_ss()
        self.engine.build_and_solve(self.model, _make_ss_class(ss2), GRADES, PROFILES, COMBINATIONS)
        ss2.point_load.assert_not_called()

    def test_no_free_nodes_get_supports(self):
        """Free nodes should NOT have any support added."""
        self._solve()
        hinged_calls = [c[1].get("node_id") or c.kwargs.get("node_id")
                        for c in self.ss_mock.add_support_hinged.call_args_list]
        roll_calls   = [c[1].get("node_id") or c.kwargs.get("node_id")
                        for c in self.ss_mock.add_support_roll.call_args_list]
        # Node 3 is Free — should not appear
        self.assertNotIn(3, hinged_calls)
        self.assertNotIn(3, roll_calls)


class TestTrussAnalysisEngineMemberChecks(unittest.TestCase):
    def setUp(self):
        self.engine = TrussAnalysisEngine()
        self.model = _fresh_model()
        self.ss_mock = _make_mock_ss()

    def _checks(self, force=-10.0):
        self.ss_mock.get_element_results.return_value = {
            "Nmin": force, "Nmax": 0.0, "N": force
        }
        return self.engine.member_checks(self.model, self.ss_mock, GRADES, PROFILES)

    def test_returns_one_result_per_element(self):
        results = self._checks()
        self.assertEqual(len(results), len(self.model.elements_data))

    def test_result_has_member_id(self):
        results = self._checks()
        for i, r in enumerate(results):
            self.assertEqual(r["member_id"], f"E{i+1}")

    def test_result_has_force(self):
        results = self._checks(force=-25.0)
        for r in results:
            self.assertEqual(r["force"], -25.0)

    def test_result_has_profile_name(self):
        results = self._checks()
        for r, el in zip(results, self.model.elements_data):
            self.assertEqual(r["profile"], el["profile"])

    def test_result_has_length(self):
        results = self._checks()
        for r in results:
            self.assertGreater(r["length"], 0)

    def test_length_computed_correctly(self):
        """E1: node1(0,0)→node2(6,0) length = 6.0"""
        results = self._checks()
        self.assertAlmostEqual(results[0]["length"], 6.0, places=4)

    def test_compression_type_for_negative_force(self):
        results = self._checks(force=-10.0)
        for r in results:
            self.assertEqual(r["type"], "Compression")

    def test_tension_type_for_positive_force(self):
        results = self._checks(force=10.0)
        for r in results:
            self.assertEqual(r["type"], "Tension")

    def test_get_element_results_called_for_each(self):
        self._checks()
        self.assertEqual(
            self.ss_mock.get_element_results.call_count,
            len(self.model.elements_data)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TrussExporter.export_csv tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrussExporterCSV(unittest.TestCase):
    def _mock_ss(self):
        ss = MagicMock()
        ss.elements = {1: {}, 2: {}, 3: {}}
        def _get_result(element_id):
            forces = {1: 10.0, 2: -20.0, 3: 0.5}
            return {"N": forces[element_id]}
        ss.get_element_results.side_effect = _get_result
        return ss

    def test_creates_file(self):
        from truss_exporter import TrussExporter
        ss = self._mock_ss()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            TrussExporter.export_csv(ss, path)
            self.assertTrue(os.path.exists(path))
        finally:
            os.unlink(path)

    def test_header_row(self):
        from truss_exporter import TrussExporter
        ss = self._mock_ss()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        try:
            TrussExporter.export_csv(ss, path)
            with open(path, encoding="utf-8") as f:
                first = f.readline()
            self.assertIn("Member", first)
            self.assertIn("Force", first)
        finally:
            os.unlink(path)

    def test_correct_row_count(self):
        from truss_exporter import TrussExporter
        ss = self._mock_ss()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            TrussExporter.export_csv(ss, path)
            with open(path, encoding="utf-8") as f:
                rows = f.readlines()
            # header + 3 data rows
            self.assertEqual(len(rows), 4)
        finally:
            os.unlink(path)

    def test_tension_compression_labels(self):
        from truss_exporter import TrussExporter
        ss = self._mock_ss()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            TrussExporter.export_csv(ss, path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Tension", content)
            self.assertIn("Compression", content)
        finally:
            os.unlink(path)

    def test_member_ids_in_output(self):
        from truss_exporter import TrussExporter
        ss = self._mock_ss()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            TrussExporter.export_csv(ss, path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for eid in ("E1", "E2", "E3"):
                self.assertIn(eid, content)
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests — Generators → Model → Engine (mock solver)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationGeneratorToEngine(unittest.TestCase):
    """Verify that generator output is valid input for the engine."""

    TRUSS_TYPES = ["Warren", "Howe", "Pratt", "Parallel Chord", "King Post"]

    def test_generated_geometry_accepted_by_engine(self):
        engine = TrussAnalysisEngine()
        for tt in self.TRUSS_TYPES:
            with self.subTest(truss_type=tt):
                nodes, elements = TrussGenerators.generate(tt, DEFAULT_PARAMS, DEFAULT_PROFILES)
                loads = TrussGenerators.default_loads(nodes)

                m = TrussModel()
                m.nodes_data = nodes
                m.elements_data = elements
                m.loads_data = loads
                m.design_method = "LRFD"
                m.selected_combo = "1.2D + 1.6L"

                ss_mock = _make_mock_ss()
                ss_mock.get_element_results.return_value = {"Nmin": -5.0, "Nmax": 0.0, "N": -5.0}
                SS = _make_ss_class(ss_mock)

                result_ss = engine.build_and_solve(m, SS, GRADES, PROFILES, COMBINATIONS)
                results = engine.member_checks(m, result_ss, GRADES, PROFILES)

                self.assertEqual(len(results), len(elements), tt)
                for r in results:
                    self.assertIn(r["status"], ("OK", "FAIL"), tt)

    def test_model_serialisation_preserves_generated_geometry(self):
        nodes, elements = TrussGenerators.generate("Howe", DEFAULT_PARAMS, DEFAULT_PROFILES)
        m = TrussModel()
        m.nodes_data = nodes
        m.elements_data = elements
        m.loads_data = TrussGenerators.default_loads(nodes)

        d = m.to_dict()
        m2 = TrussModel()
        m2.from_dict(d)

        self.assertEqual(len(m2.nodes_data), len(nodes))
        self.assertEqual(len(m2.elements_data), len(elements))

    def test_undo_after_generate_restores_previous(self):
        m = TrussModel()
        original_count = len(m.nodes_data)
        m.save_state()

        nodes, elements = TrussGenerators.generate("King Post", DEFAULT_PARAMS, DEFAULT_PROFILES)
        m.nodes_data = nodes
        m.elements_data = elements
        m.save_state()

        self.assertEqual(len(m.nodes_data), 4)
        m.undo()
        self.assertEqual(len(m.nodes_data), original_count)


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main(verbosity=2)
