"""
steel_database.py — Pre-computed steel section data organised by standard and type.

Each entry has the keys:
  Area (cm²), Ix (cm⁴), Iy (cm⁴), rx (cm), ry (cm),
  Grade (str), standard (str), section_type (str)

Compatible with the legacy STEEL_PROFILES dict via ALL_PROFILES at the bottom.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Master section database
# ---------------------------------------------------------------------------
SECTION_DB: dict[str, dict] = {}

# ── TIS (Thai Industrial Standard) — Grade SS400 ───────────────────────────

# RHS (Rectangular / Square Hollow Section)
_TIS_RHS = {
    "RHS 40x40x2.3":   {"Area": 3.27,  "Ix": 4.89,  "Iy": 4.89,  "rx": 1.22, "ry": 1.22},
    "RHS 50x50x2.3":   {"Area": 3.71,  "Ix": 8.25,  "Iy": 8.25,  "rx": 1.49, "ry": 1.49},
    "RHS 60x60x3.2":   {"Area": 6.99,  "Ix": 18.7,  "Iy": 18.7,  "rx": 1.64, "ry": 1.64},
    "RHS 75x75x3.2":   {"Area": 8.93,  "Ix": 37.4,  "Iy": 37.4,  "rx": 2.05, "ry": 2.05},
    "RHS 100x100x3.2": {"Area": 12.1,  "Ix": 82.4,  "Iy": 82.4,  "rx": 2.61, "ry": 2.61},
    "RHS 100x100x4.5": {"Area": 16.8,  "Ix": 111,   "Iy": 111,   "rx": 2.57, "ry": 2.57},
    "RHS 125x125x4.5": {"Area": 21.3,  "Ix": 218,   "Iy": 218,   "rx": 3.20, "ry": 3.20},
    "RHS 150x150x4.5": {"Area": 25.8,  "Ix": 382,   "Iy": 382,   "rx": 3.85, "ry": 3.85},
    "RHS 150x150x6.0": {"Area": 33.9,  "Ix": 491,   "Iy": 491,   "rx": 3.80, "ry": 3.80},
    "RHS 200x200x6.0": {"Area": 45.9,  "Ix": 1160,  "Iy": 1160,  "rx": 5.03, "ry": 5.03},
    "RHS 100x50x3.2":  {"Area": 8.93,  "Ix": 56.8,  "Iy": 19.1,  "rx": 2.52, "ry": 1.46},
    "RHS 150x100x4.5": {"Area": 21.3,  "Ix": 264,   "Iy": 101,   "rx": 3.52, "ry": 2.18},
}
for _name, _props in _TIS_RHS.items():
    SECTION_DB[_name] = {**_props, "Grade": "SS400", "standard": "TIS", "section_type": "RHS"}

# CHS (Circular Hollow Section / Pipe)
_TIS_CHS = {
    "CHS 42.4x2.6":  {"Area": 3.27,  "Ix": 6.59,  "Iy": 6.59,  "rx": 1.42, "ry": 1.42},
    "CHS 48.3x3.2":  {"Area": 4.53,  "Ix": 10.9,  "Iy": 10.9,  "rx": 1.55, "ry": 1.55},
    "CHS 60.3x3.2":  {"Area": 5.74,  "Ix": 21.4,  "Iy": 21.4,  "rx": 1.93, "ry": 1.93},
    "CHS 76.1x3.2":  {"Area": 7.33,  "Ix": 43.9,  "Iy": 43.9,  "rx": 2.45, "ry": 2.45},
    "CHS 88.9x4.0":  {"Area": 10.7,  "Ix": 83.3,  "Iy": 83.3,  "rx": 2.79, "ry": 2.79},
    "CHS 101.6x4.0": {"Area": 12.3,  "Ix": 125,   "Iy": 125,   "rx": 3.19, "ry": 3.19},
    "CHS 114.3x4.5": {"Area": 15.5,  "Ix": 196,   "Iy": 196,   "rx": 3.56, "ry": 3.56},
    "CHS 139.7x5.0": {"Area": 21.2,  "Ix": 441,   "Iy": 441,   "rx": 4.56, "ry": 4.56},
    "CHS 168.3x5.0": {"Area": 25.7,  "Ix": 779,   "Iy": 779,   "rx": 5.50, "ry": 5.50},
}
for _name, _props in _TIS_CHS.items():
    SECTION_DB[_name] = {**_props, "Grade": "SS400", "standard": "TIS", "section_type": "CHS"}

# Angle
_TIS_ANGLE = {
    "Angle L50x50x5":   {"Area": 4.80,  "Ix": 11.4, "Iy": 11.4, "rx": 1.54, "ry": 1.54},
    "Angle L65x65x6":   {"Area": 7.53,  "Ix": 24.7, "Iy": 24.7, "rx": 1.81, "ry": 1.81},
    "Angle L75x75x6":   {"Area": 8.78,  "Ix": 38.9, "Iy": 38.9, "rx": 2.10, "ry": 2.10},
    "Angle L90x90x7":   {"Area": 12.2,  "Ix": 74.4, "Iy": 74.4, "rx": 2.47, "ry": 2.47},
    "Angle L100x100x8": {"Area": 15.5,  "Ix": 115,  "Iy": 115,  "rx": 2.73, "ry": 2.73},
}
for _name, _props in _TIS_ANGLE.items():
    SECTION_DB[_name] = {**_props, "Grade": "SS400", "standard": "TIS", "section_type": "Angle"}

# ── JIS (Japanese Industrial Standard) — Grade SS400 ───────────────────────

# H-Beam (HN series)
_JIS_HBEAM = {
    "H-Beam HN 100x50":  {"Area": 11.85, "Ix": 187,   "Iy": 14.8, "rx": 3.97, "ry": 1.12},
    "H-Beam HN 125x60":  {"Area": 16.98, "Ix": 413,   "Iy": 29.2, "rx": 4.93, "ry": 1.31},
    "H-Beam HN 150x75":  {"Area": 17.85, "Ix": 666,   "Iy": 49.5, "rx": 6.11, "ry": 1.66},
    "H-Beam HN 175x90":  {"Area": 24.05, "Ix": 1210,  "Iy": 97.5, "rx": 7.10, "ry": 2.01},
    "H-Beam HN 200x100": {"Area": 26.67, "Ix": 1840,  "Iy": 134,  "rx": 8.30, "ry": 2.24},
    "H-Beam HN 250x125": {"Area": 36.97, "Ix": 4050,  "Iy": 294,  "rx": 10.5, "ry": 2.82},
    "H-Beam HN 300x150": {"Area": 46.78, "Ix": 7210,  "Iy": 508,  "rx": 12.4, "ry": 3.30},
    "H-Beam HN 350x175": {"Area": 63.14, "Ix": 13600, "Iy": 984,  "rx": 14.7, "ry": 3.95},
    "H-Beam HN 400x200": {"Area": 84.12, "Ix": 23700, "Iy": 1740, "rx": 16.8, "ry": 4.55},
}
for _name, _props in _JIS_HBEAM.items():
    SECTION_DB[_name] = {**_props, "Grade": "SS400", "standard": "JIS", "section_type": "H-Beam"}

# Channel (C series)
_JIS_CHANNEL = {
    "Channel C100": {"Area": 10.6, "Ix": 187,  "Iy": 15.0, "rx": 4.20, "ry": 1.19},
    "Channel C150": {"Area": 15.6, "Ix": 861,  "Iy": 37.6, "rx": 7.44, "ry": 1.55},
    "Channel C200": {"Area": 20.9, "Ix": 1950, "Iy": 70.0, "rx": 9.66, "ry": 1.83},
}
for _name, _props in _JIS_CHANNEL.items():
    SECTION_DB[_name] = {**_props, "Grade": "SS400", "standard": "JIS", "section_type": "Channel"}

# ── EN (European Standard) — Grade S275 ────────────────────────────────────

# IPE sections
_EN_IPE = {
    "IPE 80":  {"Area": 7.64,  "Ix": 80.1,  "Iy": 8.49, "rx": 3.24, "ry": 1.05},
    "IPE 100": {"Area": 10.3,  "Ix": 171,   "Iy": 15.9, "rx": 4.07, "ry": 1.24},
    "IPE 120": {"Area": 13.2,  "Ix": 318,   "Iy": 27.7, "rx": 4.90, "ry": 1.45},
    "IPE 140": {"Area": 16.4,  "Ix": 541,   "Iy": 44.9, "rx": 5.74, "ry": 1.65},
    "IPE 160": {"Area": 20.1,  "Ix": 869,   "Iy": 68.3, "rx": 6.58, "ry": 1.84},
    "IPE 180": {"Area": 23.9,  "Ix": 1320,  "Iy": 101,  "rx": 7.42, "ry": 2.05},
    "IPE 200": {"Area": 28.5,  "Ix": 1940,  "Iy": 142,  "rx": 8.26, "ry": 2.24},
    "IPE 220": {"Area": 33.4,  "Ix": 2770,  "Iy": 205,  "rx": 9.11, "ry": 2.48},
    "IPE 240": {"Area": 39.1,  "Ix": 3890,  "Iy": 284,  "rx": 9.97, "ry": 2.69},
    "IPE 270": {"Area": 45.9,  "Ix": 5790,  "Iy": 420,  "rx": 11.2, "ry": 3.02},
    "IPE 300": {"Area": 53.8,  "Ix": 8360,  "Iy": 604,  "rx": 12.5, "ry": 3.35},
    "IPE 330": {"Area": 62.6,  "Ix": 11770, "Iy": 788,  "rx": 13.7, "ry": 3.55},
    "IPE 360": {"Area": 72.7,  "Ix": 16270, "Iy": 1040, "rx": 15.0, "ry": 3.79},
    "IPE 400": {"Area": 84.5,  "Ix": 23130, "Iy": 1320, "rx": 16.5, "ry": 3.95},
}
for _name, _props in _EN_IPE.items():
    SECTION_DB[_name] = {**_props, "Grade": "S275", "standard": "EN", "section_type": "I-Beam"}

# HEA sections
_EN_HEA = {
    "HEA 100": {"Area": 21.2,  "Ix": 349,   "Iy": 134,  "rx": 4.06, "ry": 2.51},
    "HEA 120": {"Area": 25.3,  "Ix": 606,   "Iy": 231,  "rx": 4.89, "ry": 3.02},
    "HEA 140": {"Area": 31.4,  "Ix": 1033,  "Iy": 389,  "rx": 5.73, "ry": 3.52},
    "HEA 160": {"Area": 38.8,  "Ix": 1673,  "Iy": 616,  "rx": 6.57, "ry": 3.98},
    "HEA 200": {"Area": 53.8,  "Ix": 3692,  "Iy": 1336, "rx": 8.28, "ry": 4.98},
    "HEA 240": {"Area": 76.8,  "Ix": 7763,  "Iy": 2769, "rx": 10.1, "ry": 6.00},
    "HEA 300": {"Area": 112.5, "Ix": 18263, "Iy": 6312, "rx": 12.7, "ry": 7.49},
}
for _name, _props in _EN_HEA.items():
    SECTION_DB[_name] = {**_props, "Grade": "S275", "standard": "EN", "section_type": "H-Beam"}

# ── AISC (US Standard) — Grade A36 unless noted ────────────────────────────

# W-shapes (Grade A36)
_AISC_W = {
    "W4X13":  {"Area": 24.5,  "Ix": 346,   "Iy": 47.4, "rx": 3.76, "ry": 1.39},
    "W6X9":   {"Area": 17.0,  "Ix": 273,   "Iy": 22.1, "rx": 4.01, "ry": 1.14},
    "W6X15":  {"Area": 28.4,  "Ix": 491,   "Iy": 82.3, "rx": 4.16, "ry": 1.70},
    "W8X18":  {"Area": 34.2,  "Ix": 1030,  "Iy": 104,  "rx": 5.49, "ry": 1.74},
    "W8X31":  {"Area": 58.7,  "Ix": 1730,  "Iy": 273,  "rx": 5.44, "ry": 2.16},
    "W10X26": {"Area": 49.0,  "Ix": 2240,  "Iy": 141,  "rx": 6.75, "ry": 1.69},
    "W10X45": {"Area": 85.2,  "Ix": 3890,  "Iy": 374,  "rx": 6.76, "ry": 2.10},
    "W12X26": {"Area": 49.7,  "Ix": 3150,  "Iy": 128,  "rx": 7.96, "ry": 1.61},
    "W12X50": {"Area": 95.2,  "Ix": 6480,  "Iy": 411,  "rx": 8.25, "ry": 2.08},
    "W14X30": {"Area": 56.8,  "Ix": 5370,  "Iy": 185,  "rx": 9.73, "ry": 1.81},
    "W14X48": {"Area": 91.0,  "Ix": 8730,  "Iy": 424,  "rx": 9.80, "ry": 2.16},
    "W16X31": {"Area": 58.7,  "Ix": 7740,  "Iy": 150,  "rx": 11.5, "ry": 1.60},
    "W18X35": {"Area": 66.5,  "Ix": 10200, "Iy": 175,  "rx": 12.4, "ry": 1.62},
    "W18X50": {"Area": 94.8,  "Ix": 14200, "Iy": 362,  "rx": 12.2, "ry": 1.95},
}
for _name, _props in _AISC_W.items():
    SECTION_DB[_name] = {**_props, "Grade": "A36", "standard": "AISC", "section_type": "I-Beam"}

# HSS (Square/Rect) — Grade A500
_AISC_HSS = {
    "HSS4X4X1/4":   {"Area": 18.1, "Ix": 130,  "Iy": 130,  "rx": 2.68, "ry": 2.68},
    "HSS6X6X1/4":   {"Area": 27.7, "Ix": 456,  "Iy": 456,  "rx": 4.06, "ry": 4.06},
    "HSS8X8X3/8":   {"Area": 57.4, "Ix": 1750, "Iy": 1750, "rx": 5.52, "ry": 5.52},
    "HSS5X3X3/16":  {"Area": 14.6, "Ix": 195,  "Iy": 80.4, "rx": 3.66, "ry": 2.35},
}
for _name, _props in _AISC_HSS.items():
    SECTION_DB[_name] = {**_props, "Grade": "A500", "standard": "AISC", "section_type": "RHS"}

# ── Custom ──────────────────────────────────────────────────────────────────
_CUSTOM = {
    "Custom Light":  {"Area": 5.0,  "Ix": 10.0, "Iy": 10.0, "rx": 1.41, "ry": 1.41},
    "Custom Medium": {"Area": 20.0, "Ix": 100,  "Iy": 100,  "rx": 2.24, "ry": 2.24},
    "Custom Heavy":  {"Area": 50.0, "Ix": 500,  "Iy": 500,  "rx": 3.16, "ry": 3.16},
}
for _name, _props in _CUSTOM.items():
    SECTION_DB[_name] = {**_props, "Grade": "A36", "standard": "Custom", "section_type": "Custom"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_profiles(standard: str | None = None, section_type: str | None = None) -> dict:
    """Return a filtered subset of SECTION_DB as a dict.

    Parameters
    ----------
    standard:     "TIS", "JIS", "EN", "AISC", "Custom" — or None for all.
    section_type: "RHS", "CHS", "Angle", "I-Beam", "H-Beam", "Channel",
                  "Custom" — or None for all.
    """
    result = {}
    for name, props in SECTION_DB.items():
        if standard and props.get("standard") != standard:
            continue
        if section_type and props.get("section_type") != section_type:
            continue
        result[name] = props
    return result


def try_enrich_from_steelpy() -> None:
    """If steelpy is installed, add / update AISC sections in SECTION_DB."""
    try:
        from steelpy import sections as _sp  # type: ignore
        for _sec_name in dir(_sp):
            if _sec_name.startswith("_"):
                continue
            try:
                _sec = getattr(_sp, _sec_name)
                if hasattr(_sec, "area") and hasattr(_sec, "Ix") and hasattr(_sec, "Iy"):
                    _area = float(_sec.area) * 1e4   # m² → cm²
                    _ix   = float(_sec.Ix)   * 1e8   # m⁴ → cm⁴
                    _iy   = float(_sec.Iy)   * 1e8
                    _rx   = (_ix / _area) ** 0.5
                    _ry   = (_iy / _area) ** 0.5
                    SECTION_DB[_sec_name] = {
                        "Area": round(_area, 2),
                        "Ix":   round(_ix, 1),
                        "Iy":   round(_iy, 1),
                        "rx":   round(_rx, 2),
                        "ry":   round(_ry, 2),
                        "Grade":        "A36",
                        "standard":     "AISC",
                        "section_type": "I-Beam",
                    }
            except Exception:
                continue
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Backward-compatible dict (matches legacy STEEL_PROFILES key set)
# Only the six keys consumed by the GUI/analysis engine are included.
# ---------------------------------------------------------------------------
ALL_PROFILES: dict[str, dict] = {
    name: {k: v for k, v in props.items()
           if k in ("Area", "Ix", "Iy", "rx", "ry", "Grade")}
    for name, props in SECTION_DB.items()
}
