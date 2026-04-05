"""
TrussModel — pure data layer, no GUI dependency.
Holds nodes, elements, loads, project metadata, and undo/redo history.
"""
from __future__ import annotations

import copy
import datetime


class TrussModel:
    """Structural data + undo/redo history. No tkinter dependency."""

    def __init__(self) -> None:
        self.nodes_data: list[dict] = [
            {"x": 0.0, "y": 0.0, "support": "Pinned"},
            {"x": 6.0, "y": 0.0, "support": "Roller"},
            {"x": 3.0, "y": 4.0, "support": "Free"},
        ]
        self.elements_data: list[dict] = [
            {"node_a": 1, "node_b": 2, "profile": "Box 50x50x2.3"},
            {"node_a": 2, "node_b": 3, "profile": "Box 50x50x2.3"},
            {"node_a": 3, "node_b": 1, "profile": "Box 50x50x2.3"},
        ]
        self.loads_data: list[dict] = [
            {"node_id": 3, "fx": 0.0, "fy": -50.0, "case": "LL"},
            {"node_id": 2, "fx": 0.0, "fy": -25.0, "case": "DL"},
        ]
        self.project_data: dict = {
            "name": "Advanced Truss Structure",
            "engineer": "Structural Engineer",
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "client": "Engineering Firm",
            "location": "Project Site",
            "code": "AISC 360-16",
        }

        # Design settings
        self.design_method: str = "LRFD"
        self.selected_combo: str = "1.2D + 1.6L"
        self.unit_force: str = "kN"
        self.unit_length: str = "m"

        # User-defined custom load combinations: {"LRFD": {"My Combo": {"DL":1.0,...}}, "ASD": {...}}
        self.custom_combinations: dict = {"LRFD": {}, "ASD": {}}

        # Template state
        self.selected_template: str = "Warren"
        self.template_params: dict = {
            "span": 12.0,
            "height": 3.0,
            "bays": 6,
            "bottom_height": 1.0,
            "rise": 2.0,
            "cantilever_len": 3.0,
            "stub_height": 0.5,
        }

        # Optional features
        self.self_weight_enabled: bool = False

        self._history: list[dict] = []
        self._history_index: int = -1

    # ── Undo / Redo ──────────────────────────────────────────────────────────

    def save_state(self) -> None:
        """Snapshot current structural data onto the undo stack."""
        state = {
            "nodes": copy.deepcopy(self.nodes_data),
            "elements": copy.deepcopy(self.elements_data),
            "loads": copy.deepcopy(self.loads_data),
            "project": copy.deepcopy(self.project_data),
        }
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(state)
        if len(self._history) > 50:
            self._history.pop(0)
        self._history_index = len(self._history) - 1

    def undo(self) -> bool:
        if self._history_index <= 0:
            return False
        self._history_index -= 1
        self._apply(self._history[self._history_index])
        return True

    def redo(self) -> bool:
        if self._history_index >= len(self._history) - 1:
            return False
        self._history_index += 1
        self._apply(self._history[self._history_index])
        return True

    def _apply(self, state: dict) -> None:
        self.nodes_data = copy.deepcopy(state["nodes"])
        self.elements_data = copy.deepcopy(state["elements"])
        self.loads_data = copy.deepcopy(state["loads"])
        self.project_data = copy.deepcopy(state["project"])

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes_data,
            "elems": self.elements_data,
            "loads": self.loads_data,
            "project": self.project_data,
            "custom_combinations": self.custom_combinations,
            "settings": {
                "design_method":    self.design_method,
                "selected_combo":   self.selected_combo,
                "unit_force":       self.unit_force,
                "unit_length":      self.unit_length,
                "selected_template": self.selected_template,
                "template_params":  self.template_params,
                "self_weight":      getattr(self, "self_weight_enabled", False),
            },
        }

    def from_dict(self, d: dict) -> None:
        self.nodes_data    = d["nodes"]
        self.elements_data = d["elems"]
        self.loads_data    = d["loads"]
        if "project" in d:
            self.project_data.update(d["project"])
        if "custom_combinations" in d:
            self.custom_combinations = d["custom_combinations"]
        if "settings" in d:
            s = d["settings"]
            self.design_method       = s.get("design_method",    self.design_method)
            self.selected_combo      = s.get("selected_combo",   self.selected_combo)
            self.unit_force          = s.get("unit_force",        self.unit_force)
            self.unit_length         = s.get("unit_length",       self.unit_length)
            self.selected_template   = s.get("selected_template", self.selected_template)
            self.template_params.update(s.get("template_params", {}))
            self.self_weight_enabled = s.get("self_weight", False)
