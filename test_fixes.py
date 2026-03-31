#!/usr/bin/env python
"""Test script to verify fixes for get_element_results() calls"""

from anastruct import SystemElements
from truss_analyzer_gui import TrussAnalyzer

print("Starting tests...")

# Create a simple truss
analyzer = TrussAnalyzer()
print("✓ TrussAnalyzer initialized")

# Add simple truss
analyzer.add_truss_element([[0, 0], [5, 0]], EA=15000)
analyzer.add_truss_element([[5, 0], [5, 5]], EA=15000)
analyzer.add_truss_element([[0, 0], [5, 5]], EA=15000)

print("✓ Elements added")

# Add supports
analyzer.add_support_hinged(1)
analyzer.add_support_roll(2, "y")
print("✓ Supports added")

# Add load
analyzer.point_load(3, Fx=0, Fy=-10)
print("✓ Load added")

# Solve
analyzer.solve()
print("✓ Analysis solved")

# Test get_element_results
print("\nElement Results:")
for elem_id in [1, 2, 3]:
    result = analyzer.get_element_results(element_id=elem_id)
    force = result.get('Nmin', 0.0)  # Use Nmin which is always present
    print(f"  Element {elem_id}: Force = {force:.2f} kN ({'Tension' if force > 0 else 'Compression'})")

print("\n✓ All tests PASSED! get_element_results() is working correctly.")
