"""
TrussGenerators — parametric truss geometry, no GUI dependency.
All generators are static methods; dispatch via class-level dict.
"""
from __future__ import annotations


def _no_zero(nodes, elements, na, nb, profile, member_type=""):
    """Append element only if the two nodes are not coincident."""
    n1, n2 = nodes[na - 1], nodes[nb - 1]
    if abs(n1["x"] - n2["x"]) > 1e-9 or abs(n1["y"] - n2["y"]) > 1e-9:
        el = {"node_a": na, "node_b": nb, "profile": profile}
        if member_type:
            el["member_type"] = member_type
        elements.append(el)


class TrussGenerators:
    """
    Factory for parametric truss geometries.

    Usage::
        nodes, elements = TrussGenerators.generate("Howe", params, profiles)
        loads = TrussGenerators.default_loads(nodes)
    """

    # ── Public API ───────────────────────────────────────────────────────────

    @classmethod
    def generate(
        cls, truss_type: str, params: dict, profiles: dict
    ) -> tuple[list[dict], list[dict]]:
        nodes: list[dict] = []
        elements: list[dict] = []
        fn = cls._DISPATCH.get(truss_type, cls._warren)
        fn(nodes, elements, params, profiles)
        return nodes, elements

    @staticmethod
    def default_loads(nodes_data: list[dict]) -> list[dict]:
        """Standard midspan DL + LL loads for a freshly generated truss."""
        mid = max(1, len(nodes_data) // 2)
        return [
            {"node_id": mid, "fx": 0, "fy": -50,  "case": "DL"},
            {"node_id": mid, "fx": 0, "fy": -100, "case": "LL"},
        ]

    # ── Generators ───────────────────────────────────────────────────────────

    @staticmethod
    def _warren(nodes, elements, p, pr):
        span, height, n = p["span"], p["height"], p["bays"]
        dx = span / n
        for i in range(n + 1):
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": i * dx, "y": 0,      "support": sup})
            nodes.append({"x": i * dx, "y": height, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            diag = (b1, t2) if i % 2 == 0 else (b2, t1)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
            elements.append({"node_a": b1, "node_b": t1, "profile": pr["vertical"], "member_type": "Vertical"})
        elements.append({"node_a": n*2+1, "node_b": n*2+2, "profile": pr["vertical"], "member_type": "Vertical"})

    @staticmethod
    def _howe(nodes, elements, p, pr):
        span, height, n = p["span"], p["height"], p["bays"]
        if n % 2 != 0:
            n += 1
        dx = span / n
        for i in range(n + 1):
            x = i * dx
            yt = (x / (span / 2)) * height if x <= span / 2 else (2 - x / (span / 2)) * height
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": 0,  "support": sup})
            nodes.append({"x": x, "y": yt, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            diag = (b1, t2) if i < n / 2 else (b2, t1)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _pratt(nodes, elements, p, pr):
        span, height, n = p["span"], p["height"], p["bays"]
        if n % 2 != 0:
            n += 1
        dx = span / n
        for i in range(n + 1):
            x = i * dx
            yt = (x / (span / 2)) * height if x <= span / 2 else (2 - x / (span / 2)) * height
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": 0,  "support": sup})
            nodes.append({"x": x, "y": yt, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            diag = (b2, t1) if i < n / 2 else (b1, t2)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _king_post(nodes, elements, p, pr):
        span, height = p["span"], p["height"]
        nodes += [
            {"x": 0,        "y": 0,      "support": "Pinned"},
            {"x": span,     "y": 0,      "support": "Roller"},
            {"x": span / 2, "y": 0,      "support": "Free"},
            {"x": span / 2, "y": height, "support": "Free"},
        ]
        elements += [
            {"node_a": 1, "node_b": 3, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"},
            {"node_a": 3, "node_b": 2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"},
            {"node_a": 1, "node_b": 4, "profile": pr["top_chord"],    "member_type": "Top Chord"},
            {"node_a": 2, "node_b": 4, "profile": pr["top_chord"],    "member_type": "Top Chord"},
            {"node_a": 3, "node_b": 4, "profile": pr["vertical"],     "member_type": "Vertical"},
        ]

    @staticmethod
    def _fink(nodes, elements, p, pr):
        """Fink (W-truss) — pitched roof with W-pattern web members."""
        span, height, n = p["span"], p["height"], max(4, p["bays"])
        if n % 2 != 0:
            n += 1
        dx = span / n
        for i in range(n + 1):
            x = i * dx
            yt = (x / (span / 2)) * height if x <= span / 2 else (2 - x / (span / 2)) * height
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": 0,  "support": sup})
            nodes.append({"x": x, "y": yt, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            # W-pattern: outer bays diverge toward center, inner bays converge
            half = n // 2
            if i < half:
                diag = (b1, t2)   # bottom-left → top-right
            else:
                diag = (b2, t1)   # bottom-right → top-left
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _fan(nodes, elements, p, pr):
        span, height, n = p["span"], p["height"], p["bays"]
        dx = span / n
        for i in range(n + 1):
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": i * dx, "y": 0, "support": sup})
        nodes.append({"x": span / 2, "y": height, "support": "Free"})
        apex = len(nodes)
        for i in range(n):
            elements.append({"node_a": i + 1, "node_b": i + 2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
        for i in range(n + 1):
            elements.append({"node_a": i + 1, "node_b": apex, "profile": pr["diagonal"], "member_type": "Diagonal"})

    @staticmethod
    def _scissors(nodes, elements, p, pr):
        span, height, n = p["span"], p["height"], p["bays"]
        bh = p.get("bottom_height", 1.0)
        if n % 2 != 0:
            n += 1
        dx = span / n
        for i in range(n + 1):
            x = i * dx
            yt = (x / (span / 2)) * height if x <= span / 2 else (2 - x / (span / 2)) * height
            yb = (x / (span / 2)) * bh     if x <= span / 2 else (2 - x / (span / 2)) * bh
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": yb, "support": sup})
            nodes.append({"x": x, "y": yt, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            diag = (b1, t2) if i < n / 2 else (b2, t1)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _mono(nodes, elements, p, pr, pattern="Howe"):
        """Mono-pitch (lean-to) truss — single slope."""
        span, height, n = p["span"], p["height"], p["bays"]
        dx = span / n
        for i in range(n + 1):
            x = i * dx
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": 0,               "support": sup})
            nodes.append({"x": x, "y": (x / span) * height, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            if pattern == "Howe":
                diag = (b1, t2)
            elif pattern == "Pratt":
                diag = (b2, t1)
            else:   # Warren
                diag = (b1, t2) if i % 2 == 0 else (b2, t1)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _parallel(nodes, elements, p, pr, pattern="Pratt"):
        """Parallel-chord truss — flat top and bottom."""
        span, height, n = p["span"], p["height"], p["bays"]
        dx = span / n
        for i in range(n + 1):
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": i * dx, "y": 0,      "support": sup})
            nodes.append({"x": i * dx, "y": height, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            elements.append({"node_a": b2, "node_b": t2, "profile": pr["vertical"],     "member_type": "Vertical"})
            if pattern == "Warren":
                diag = (b1, t2) if i % 2 == 0 else (b2, t1)
            else:   # Pratt
                diag = (b2, t1) if i < n / 2 else (b1, t2)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        elements.append({"node_a": 1, "node_b": 2, "profile": pr["vertical"], "member_type": "Vertical"})

    @staticmethod
    def _curved(nodes, elements, p, pr, bowstring=False, pattern="Howe"):
        """Curved / Bowstring truss.

        pattern:
          "Howe"   — diagonals converge toward centre (default)
          "Pratt"  — diagonals diverge from centre (V-shape outward)
          "Warren" — diagonals alternate direction (parallel pattern)
        """
        span, height, n = p["span"], p["height"], p["bays"]
        rise = p.get("rise", 2.0)
        dx = span / n
        for i in range(n + 1):
            x = i * dx
            yt = height + 4 * rise * (x / span) * (1 - x / span)
            yb = 0 if bowstring else 4 * height * (x / span) * (1 - x / span)
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": yb, "support": sup})
            nodes.append({"x": x, "y": yt, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            if pattern == "Warren":
                diag = (b1, t2) if i % 2 == 0 else (b2, t1)
            elif pattern == "Pratt":   # diverge from centre (V-shape)
                diag = (b2, t1) if i < n / 2 else (b1, t2)
            else:                      # Howe — converge to centre
                diag = (b1, t2) if i < n / 2 else (b2, t1)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _cantilever(nodes, elements, p, pr):
        """Single-cantilever truss — main span + overhang."""
        span, height, n = p["span"], p["height"], p["bays"]
        canti_l = p.get("cantilever_len", 3.0)
        total_l = span + canti_l
        dx = total_l / n
        for i in range(n + 1):
            x = i * dx
            sup = "Pinned" if x < 1e-9 else ("Roller" if abs(x - span) < dx * 0.5 else "Free")
            nodes.append({"x": x, "y": 0,      "support": sup})
            nodes.append({"x": x, "y": height, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            elements.append({"node_a": b2, "node_b": t2, "profile": pr["vertical"],     "member_type": "Vertical"})
            elements.append({"node_a": b1, "node_b": t2, "profile": pr["diagonal"],     "member_type": "Diagonal"})
        elements.append({"node_a": 1, "node_b": 2, "profile": pr["vertical"], "member_type": "Vertical"})

    @staticmethod
    def _stub(nodes, elements, p, pr):
        """Double stub-end (raised heel) truss."""
        span, height, n = p["span"], p["height"], p["bays"]
        stub_h = p.get("stub_height", 0.5)
        dx = span / n
        for i in range(n + 1):
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": i * dx, "y": 0,             "support": sup})
            nodes.append({"x": i * dx, "y": height + stub_h, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            elements.append({"node_a": b2, "node_b": t2, "profile": pr["vertical"],     "member_type": "Vertical"})
            elements.append({"node_a": b1, "node_b": t2, "profile": pr["diagonal"],     "member_type": "Diagonal"})
        elements.append({"node_a": 1, "node_b": 2, "profile": pr["vertical"], "member_type": "Vertical"})

    @staticmethod
    def _queen_post(nodes, elements, p, pr):
        """Queen Post truss — two vertical queen posts at ~1/3 and ~2/3 span."""
        span, height = p["span"], p["height"]
        x1 = span / 3
        x2 = 2 * span / 3
        # Nodes: 1=left support, 2=bottom 1/3, 3=bottom 2/3, 4=right support
        #        5=top 1/3,       6=top 2/3
        nodes += [
            {"x": 0,    "y": 0,      "support": "Pinned"},   # 1
            {"x": x1,   "y": 0,      "support": "Free"},      # 2
            {"x": x2,   "y": 0,      "support": "Free"},      # 3
            {"x": span, "y": 0,      "support": "Roller"},    # 4
            {"x": x1,   "y": height, "support": "Free"},      # 5
            {"x": x2,   "y": height, "support": "Free"},      # 6
        ]
        elements += [
            # Bottom chord
            {"node_a": 1, "node_b": 2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"},
            {"node_a": 2, "node_b": 3, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"},
            {"node_a": 3, "node_b": 4, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"},
            # Top chord
            {"node_a": 1, "node_b": 5, "profile": pr["top_chord"],    "member_type": "Top Chord"},
            {"node_a": 5, "node_b": 6, "profile": pr["top_chord"],    "member_type": "Top Chord"},
            {"node_a": 6, "node_b": 4, "profile": pr["top_chord"],    "member_type": "Top Chord"},
            # Queen posts (verticals)
            {"node_a": 2, "node_b": 5, "profile": pr["vertical"],     "member_type": "Vertical"},
            {"node_a": 3, "node_b": 6, "profile": pr["vertical"],     "member_type": "Vertical"},
        ]

    @staticmethod
    def _gambrel_y(x, span, height, lower_h_ratio=0.4, break_ratio=0.3):
        """Return the top-chord y-coordinate for the gambrel profile at position x."""
        h_low   = height * lower_h_ratio
        x_break = span * break_ratio
        if x <= x_break:
            return (x / x_break) * h_low if x_break > 0 else 0.0
        elif x <= span / 2:
            return h_low + ((x - x_break) / (span / 2 - x_break)) * (height - h_low)
        else:
            return TrussGenerators._gambrel_y(span - x, span, height, lower_h_ratio, break_ratio)

    @staticmethod
    def _gambrel_gen(nodes, elements, p, pr, lower_h_ratio=0.4, break_ratio=0.3):
        """Shared implementation for Gambrel and Mansard trusses."""
        span, height, n = p["span"], p["height"], max(4, p["bays"])
        if n % 2 != 0:
            n += 1
        dx = span / n
        for i in range(n + 1):
            x   = i * dx
            yt  = TrussGenerators._gambrel_y(x, span, height, lower_h_ratio, break_ratio)
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": x, "y": 0,  "support": sup})
            nodes.append({"x": x, "y": yt, "support": "Free"})
        for i in range(n):
            b1, t1, b2, t2 = i*2+1, i*2+2, (i+1)*2+1, (i+1)*2+2
            elements.append({"node_a": b1, "node_b": b2, "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": t1, "node_b": t2, "profile": pr["top_chord"],    "member_type": "Top Chord"})
            _no_zero(nodes, elements, b2, t2, pr["vertical"], "Vertical")
            diag = (b1, t2) if i < n / 2 else (b2, t1)
            elements.append({"node_a": diag[0], "node_b": diag[1], "profile": pr["diagonal"], "member_type": "Diagonal"})
        _no_zero(nodes, elements, 1, 2, pr["vertical"], "Vertical")

    @staticmethod
    def _gambrel(nodes, elements, p, pr):
        """Gambrel truss — barn-style double-slope roof."""
        lr = p.get("lower_ratio", 0.4)
        br = p.get("break_ratio", 0.3)
        TrussGenerators._gambrel_gen(nodes, elements, p, pr, lower_h_ratio=lr, break_ratio=br)

    @staticmethod
    def _mansard(nodes, elements, p, pr):
        """Mansard truss — steep outer walls (~60° slope) with shallow inner roof."""
        TrussGenerators._gambrel_gen(nodes, elements, p, pr, lower_h_ratio=0.6, break_ratio=0.2)

    @staticmethod
    def _baltimore(nodes, elements, p, pr):
        """Baltimore truss — Pratt with sub-panel nodes at mid-height of each bay."""
        span, height, n = p["span"], p["height"], max(2, p["bays"])
        dx = span / n
        # Layout:
        #   B nodes (bottom chord, y=0):  indices 1 .. n+1
        #   T nodes (top chord, y=h):     indices n+2 .. 2n+2
        #   M nodes (mid-height, y=h/2):  indices 2n+3 .. 3n+2  (one per panel)
        for i in range(n + 1):
            sup = "Pinned" if i == 0 else ("Roller" if i == n else "Free")
            nodes.append({"x": i * dx, "y": 0,      "support": sup})    # B_i  = node i+1
        for i in range(n + 1):
            nodes.append({"x": i * dx, "y": height, "support": "Free"}) # T_i  = node n+2+i
        for i in range(n):
            nodes.append({"x": (i + 0.5) * dx, "y": height / 2, "support": "Free"})  # M_i

        def B(i): return i + 1           # bottom chord node index (1-based)
        def T(i): return n + 2 + i       # top chord node index
        def M(i): return 2 * n + 3 + i  # mid node index

        for i in range(n):
            # Bottom and top chords
            elements.append({"node_a": B(i), "node_b": B(i+1), "profile": pr["bottom_chord"], "member_type": "Bottom Chord"})
            elements.append({"node_a": T(i), "node_b": T(i+1), "profile": pr["top_chord"],    "member_type": "Top Chord"})
            # End verticals
            elements.append({"node_a": B(i), "node_b": T(i),   "profile": pr["vertical"],     "member_type": "Vertical"})
            # Sub-panel web: B_i → M_i, M_i → T_{i+1}, T_i → M_i, M_i → B_{i+1}
            elements.append({"node_a": B(i),   "node_b": M(i),   "profile": pr["diagonal"], "member_type": "Diagonal"})
            elements.append({"node_a": M(i),   "node_b": T(i+1), "profile": pr["diagonal"], "member_type": "Diagonal"})
            elements.append({"node_a": T(i),   "node_b": M(i),   "profile": pr["diagonal"], "member_type": "Diagonal"})
            elements.append({"node_a": M(i),   "node_b": B(i+1), "profile": pr["diagonal"], "member_type": "Diagonal"})
        # Last vertical
        elements.append({"node_a": B(n), "node_b": T(n), "profile": pr["vertical"], "member_type": "Vertical"})


# Dispatch dict — defined after all static methods exist
TrussGenerators._DISPATCH = {
    "Howe":              TrussGenerators._howe,
    "Pratt":             TrussGenerators._pratt,
    "Warren":            TrussGenerators._warren,
    "Fan":               TrussGenerators._fan,
    "Fink":              TrussGenerators._fink,
    "King Post":         TrussGenerators._king_post,
    "Scissors":                 TrussGenerators._scissors,
    "Modified Scissors":        TrussGenerators._scissors,
    "Monopith":                 lambda n, e, p, pr: TrussGenerators._mono(n, e, p, pr, "Howe"),
    "Half Howe":                lambda n, e, p, pr: TrussGenerators._mono(n, e, p, pr, "Howe"),
    "Half Pratt":               lambda n, e, p, pr: TrussGenerators._mono(n, e, p, pr, "Pratt"),
    "Half Warren":              lambda n, e, p, pr: TrussGenerators._mono(n, e, p, pr, "Warren"),
    "Half Scissors":            lambda n, e, p, pr: TrussGenerators._mono(n, e, p, pr, "Warren"),
    "Parallel Chord":           TrussGenerators._parallel,
    "Warren (Flat)":            lambda n, e, p, pr: TrussGenerators._parallel(n, e, p, pr, "Warren"),
    "Modified Warren":          lambda n, e, p, pr: TrussGenerators._parallel(n, e, p, pr, "Warren"),
    "Bowstring":                lambda n, e, p, pr: TrussGenerators._curved(n, e, p, pr, True),
    "Bowstring (Pratt)":        lambda n, e, p, pr: TrussGenerators._curved(n, e, p, pr, True,  "Pratt"),
    "Bowstring (Warren)":       lambda n, e, p, pr: TrussGenerators._curved(n, e, p, pr, True,  "Warren"),
    "Curved Truss 1":           TrussGenerators._curved,
    "Curved Truss 2":           lambda n, e, p, pr: TrussGenerators._curved(n, e, p, pr, False, "Warren"),
    "Curved Truss 3":           lambda n, e, p, pr: TrussGenerators._curved(n, e, p, pr, False, "Pratt"),
    "Single Cantilever":        TrussGenerators._cantilever,
    "Double Stub End":          TrussGenerators._stub,
    # ── New generators ────────────────────────────────────────────────
    "Queen Post":    TrussGenerators._queen_post,
    "Gambrel":       TrussGenerators._gambrel,
    "Mansard":       TrussGenerators._mansard,
    "Baltimore":     TrussGenerators._baltimore,
    "Pony Truss":    lambda n, e, p, pr: TrussGenerators._parallel(n, e, p, pr, "Warren"),
    "Through Truss": lambda n, e, p, pr: TrussGenerators._parallel(n, e, p, pr, "Pratt"),
}
