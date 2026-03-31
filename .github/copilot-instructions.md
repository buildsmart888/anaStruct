# anaStruct Copilot Instructions

**Project:** Finite element analysis (FEA) library for 2D frames and trusses using matrix assembly method

## Architecture

### Core Components
- **SystemElements** (`anastruct/fem/system.py`): main user interface. Users create structures, add elements/supports/loads, call `solve()`. Delegates computation to system_components.
- **Element** (`anastruct/fem/elements.py`): represents beam/truss members. Compiles stiffness, kinematic, and constitutive matrices via Cython for performance.
- **Node** (`anastruct/fem/node.py`): represents vertices with degrees-of-freedom (DOF). Nodes map to rows in global stiffness matrix (3 DOF each: Fx, Fy, Tz).
- **system_components** (`anastruct/fem/system_components/`): Three modules:
  - `assembly.py` — Builds global stiffness matrix and force vectors. Applies loads (point/q-loads/moments), processes supports.
  - `solver.py` — Linear/non-linear solvers. `stiffness_adaptation()` for non-linear springs; `geometrically_non_linear()` for buckling analysis.
  - `util.py` — Helper functions for hinges, checks.

### Workflow: Modelling → Solving → Postprocessing
1. **Modelling**: `SystemElements()` → `add_element()`, `add_support_*()`, load methods
2. **Solving**: `solve()` assembles global K matrix, reduces by supports, solves `K*u = F`, extracts element forces
3. **Postprocessing**: `get_element_results()`, `show_*()` plotting methods via plotter module

### Key Data Structures
- `element_map` (dict): element_id → Element
- `node_map` (dict): node_id → Node
- `system_matrix` (np.ndarray): global stiffness (n_nodes × 3) × (n_nodes × 3)
- `system_displacement_vector` (np.ndarray): solved DOF displacements
- Cython modules in `anastruct/fem/cython/` and `anastruct/cython/` compute `det_axial`, `det_moment`, `det_shear` force extraction

## Build & Test

### Build Process
Requires Cython for performance-critical force extraction. `setup.py` delegates to `build_cython_ext.py`:
- **celements.pyx** — Element-level force extraction (`det_axial`, `det_moment`, `det_shear`)
- **cbasic.pyx** — Basic numerical utilities for matrix operations

```bash
pip install -e .                      # Builds in-place, compiles .pyx files
python setup.py build_ext --inplace   # Manual rebuild after Cython edits
```

⚠️ **Edit .pyx files?** Recompile with: `pip install --no-build-isolation -e .`

### Test Strategy
Uses pytest-describe (BDD-style contexts) and pytest-cov. **Critical:** All tests validate against analytical engineering solutions, not just numerical consistency.

```bash
pytest                             # Full suite with coverage
pytest -k "simply_supported"       # Run specific test context
```

**Test files:**
- `tests/test_analytical.py` — Validates moments, reactions, deflections against engineering formulas
- `tests/test_e2e.py` — Integration tests
- `tests/test_stiffness.py` — Matrix assembly validation

## Conventions & Patterns

### Loading System
- `q_load()` — distributed load; direction: `"element"` (along beam), `"x"`/`"y"` (global), `"parallel"`/`"perpendicular"`, `"angle"`
- `point_load()` — concentrated force; rotation parameter rotates load clockwise (degrees)
- Dead load applies self-weight per element
- `LoadCase`/`LoadCombination` group loads for analysis

### Support Conditions
- Supports map to constraint equations in assembly. `process_supports()` determines which DOFs are fixed.
- Hinged (node ID = 2 DOF constraints), fixed (3 DOF), roll (1 DOF in one direction), spring (stiffness K)
- Roll supports can be inclined via angle specification

### Element Types
- `"general"` — beam (bending + axial stiffness EA, EI)
- `"truss"` — axial only (zero bending)
- Pre-built trusses in `anastruct/preprocess/truss.py`: Howe, Pratt, Warren, etc.

### Non-Linearity
- `non_linear_elements` dict: element_id → {node_no: moment_capacity}
- Solver iterates stiffness, updating springs at plastic hinges until convergence
- Geometrical non-linearity: P-Delta effects; use `geometrical_non_linear=True` parameter

### Type System
- `anastruct/types.py` defines Literals: `ElementType`, `LoadDirection`, `VertexLike`
- `anastruct/vertex.py` contains `Vertex` class for 2D coordinates; flexible input (Vertex obj, list, tuple, np.array)

## Common Tasks

### Modelling Example
```python
from anastruct import SystemElements
ss = SystemElements(EA=15000, EI=5000)  # Global stiffness defaults

# Add element: single line or 2D polygon
ss.add_element(location=[[0, 0], [5, 0]])  # Horizontal beam
ss.add_element([[0, 0], [0, 5]], type_='general', EA=20000)  # Vertical, override EA
ss.add_truss_element([[0, 0], [5, 5]])  # Truss (no bending)

# Supports: node_id is auto-assigned (1-indexed)
ss.add_support_fixed(node_id=1)  # Fix all 3 DOF
ss.add_support_hinged(node_id=2)  # Only rotation free
ss.add_support_roll(node_id=3, direction='y')  # Roll: fixed in y
ss.add_support_spring(node_id=4, translation=1, k=1000)  # Spring K

# Loads
ss.point_load(node_id=2, Fx=10, Fy=-5, rotation=45)  # Clockwise 45°
ss.q_load(element_id=1, q=-10, direction='y')  # -10 kN/m downward
ss.dead_load(element_id=1, g=9.81)  # Self-weight
```

### Solving & Results
```python
ss.solve()  # Returns system_displacement_vector

# Extract results
results = ss.get_element_results(element_id=1)
# Keys: 'Mmax', 'Mmin', 'Qmax', 'Qmin', 'N', 'wtotmax'

rx, ry, tz = ss.get_node_results_system(node_id=1)  # Reactions
ss.system_displacement_vector  # [ux1, uy1, θz1, ux2, uy2, θz2, ...]
ss.element_map[1].element_force_vector  # Element internal forces
ss.validate()  # bool: eigenvalues of K > 1e-9
```

### Plotting
```python
ss.show_structure()  # Undeformed geometry
ss.show_displacement(factor=5)  # Scaled deformations
ss.show_bending_moment()
ss.show_shear_force()
ss.show_axial_force()
ss.show_reaction_force()
```

## GUI Applications
- `continuous_beam_gui.py` — Continuous beam analyzer (customtkinter UI). Exports to PDF.
- `truss_analyzer_gui.py` — Truss analysis GUI.

## Tips for Contributors

### Performance & Optimization
- **Cython bottlenecks:** Force extraction (`det_axial`, `det_moment`, `det_shear`) in `.pyx` files must stay compiled. Never replicate in pure Python.
- **Matrix caching:** Element stiffness uses `@lru_cache(maxsize=32000)` in `elements.py`. Symbolic computation isolated to avoid cache misses.
- **Element loops:** `assemble_system_matrix()` iterates `element_map.values()`. Avoid expensive Python operations in inner loops.

### Testing Pattern
- Use `pytest-describe` contexts in `test_analytical.py`. Each context = one scenario with known analytical results.
- Compare against textbook formulas (e.g., cantilever: δ = PL³/(3EI)). Document formula with variable meanings.
- Never test only numerical consistency — always validate against engineering solutions.

### Code Organization
- **Assembly changes?** Update `system_components/assembly.py` + add test to `test_analytical.py`.
- **New load type?** Add method to `SystemElements`, implement in `assembly.py` (see `apply_point_load`).
- **New solver?** Add to `system_components/solver.py` (see `stiffness_adaptation` for non-linear example).

### Documentation
- **Examples:** `examples/` folder shows workflows. Add examples for non-obvious features.
- **Docs:** `doc/source/` uses Sphinx. Build: `cd doc && make html`.
- **Type hints:** Use `anastruct/types.py` Literals (`ElementType`, `LoadDirection`, `VertexLike`).
