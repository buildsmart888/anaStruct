import math, sys, traceback
sys.path.insert(0, 'D:/anaStruct')

from truss_generators import TrussGenerators
from truss_model import TrussModel
from truss_analysis import TrussAnalysisEngine

from anastruct import SystemElements as AnaStructSystemElements

class TrussAnalyzer:
    def __init__(self):
        self.ss = AnaStructSystemElements(); self.solved = False
    def add_truss_element(self, location, EA): return self.ss.add_truss_element(location=location, EA=EA)
    def add_support_hinged(self, node_id): self.ss.add_support_hinged(node_id=node_id)
    def add_support_roll(self, node_id, direction=2): self.ss.add_support_roll(node_id=node_id, direction=direction)
    def point_load(self, node_id, Fx=0, Fy=0): self.ss.point_load(node_id=node_id, Fx=Fx, Fy=Fy)
    def solve(self): self.ss.solve(); self.solved = True
    def get_element_results(self, element_id): return self.ss.get_element_results(element_id=element_id)
    @property
    def nodes(self): return {nid: {'x': n.vertex.x, 'y': n.vertex.y} for nid, n in self.ss.node_map.items()}
    @property
    def elements(self): return {eid: {'start': [e.vertex_1.x, e.vertex_1.y], 'end': [e.vertex_2.x, e.vertex_2.y]} for eid, e in self.ss.element_map.items()}
    @property
    def reaction_forces(self): return {nid: {'x': n.vertex.x, 'y': n.vertex.y, 'Fx': n.Fx, 'Fy': n.Fy} for nid, n in self.ss.reaction_forces.items()}

STEEL_GRADES = {'A36': {'Fy': 250, 'Fu': 400, 'E': 200000}}
STEEL_PROFILES = {
    'Box 50x50x2.3': {'Area': 3.71, 'rx': 1.49, 'ry': 1.49, 'Grade': 'A36'},
    'Box 100x100x3.2': {'Area': 12.1, 'rx': 2.61, 'ry': 2.61, 'Grade': 'A36'},
    'Pipe 60.3x3.2': {'Area': 5.64, 'rx': 1.89, 'ry': 1.89, 'Grade': 'A36'},
}
LOAD_COMBINATIONS = {
    'LRFD': {'1.2D + 1.6L': {'DL': 1.2, 'LL': 1.6, 'WL': 0.0, 'SL': 0.0}},
    'ASD': {}
}

params = {
    'span': 12.0, 'height': 3.0, 'bays': 6,
    'bottom_height': 1.0, 'rise': 2.0,
    'cantilever_len': 3.0, 'stub_height': 0.5,
}
profiles = {
    'bottom_chord': 'Box 50x50x2.3',
    'top_chord': 'Box 50x50x2.3',
    'diagonal': 'Box 50x50x2.3',
    'vertical': 'Box 50x50x2.3',
}

engine = TrussAnalysisEngine()
all_types = list(TrussGenerators._DISPATCH.keys())

print(f"Testing {len(all_types)} truss types\n{'='*60}")

for ttype in all_types:
    try:
        nodes, elements = TrussGenerators.generate(ttype, params, profiles)

        # Check 1: zero-length elements
        zero_len = []
        for i, el in enumerate(elements):
            na, nb = el['node_a']-1, el['node_b']-1
            if na >= len(nodes) or nb >= len(nodes):
                zero_len.append(f"E{i+1} node ref out of range")
                continue
            n1, n2 = nodes[na], nodes[nb]
            dist = math.sqrt((n2['x']-n1['x'])**2 + (n2['y']-n1['y'])**2)
            if dist < 1e-9:
                zero_len.append(f"E{i+1}(N{el['node_a']}-N{el['node_b']}) len=0")

        # Check 2: supports
        supports = [(i+1, n['support']) for i, n in enumerate(nodes) if n['support'] != 'Free']
        pinned = [s for s in supports if s[1] == 'Pinned']
        roller = [s for s in supports if s[1] == 'Roller']

        # Check 3: try FEA solve
        model = TrussModel()
        model.nodes_data = nodes
        model.elements_data = elements
        model.loads_data = [
            {'node_id': max(1, len(nodes)//2), 'fx': 0, 'fy': -50, 'case': 'DL'},
            {'node_id': max(1, len(nodes)//2), 'fx': 0, 'fy': -100, 'case': 'LL'},
        ]
        model.design_method = 'LRFD'
        model.selected_combo = '1.2D + 1.6L'

        ss = engine.build_and_solve(model, TrussAnalyzer, STEEL_GRADES, STEEL_PROFILES, LOAD_COMBINATIONS)
        results = engine.member_checks(model, ss, STEEL_GRADES, STEEL_PROFILES)

        status = "OK"
        notes = []
        if zero_len: notes.append(f"ZERO-LEN: {zero_len}")
        if len(pinned) != 1: notes.append(f"pinned={len(pinned)}")
        if len(roller) != 1: notes.append(f"roller={len(roller)}")
        note_str = " | ".join(notes) if notes else ""
        print(f"  {status} {ttype:30s} nodes={len(nodes):3d} elems={len(elements):3d} {note_str}")

    except Exception as e:
        tb = traceback.format_exc().strip().split('\n')
        last_lines = tb[-3:]
        print(f"  FAIL {ttype:30s} -> {e}")
        for l in last_lines:
            print(f"       {l}")

print(f"\n{'='*60}")
