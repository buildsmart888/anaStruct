# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['anastruct',
 'anastruct.cython',
 'anastruct.fem',
 'anastruct.fem.cython',
 'anastruct.fem.plotter',
 'anastruct.fem.system_components',
 'anastruct.fem.util',
 'anastruct.fem.util.envelope',
 'anastruct.material',
 'anastruct.preprocess',
 'anastruct.sectionbase']

package_data = \
{'': ['*'], 'anastruct.sectionbase': ['data/*']}

install_requires = \
['numpy>=1.23.5', 'scipy>=1.10.0']

extras_require = \
{'plot': ['matplotlib>=3.0']}

setup_kwargs = {
    'name': 'anastruct',
    'version': '1.6.2',
    'description': 'Finite element analysis of 2D structures',
    'long_description': "# anaStruct 2D Frames and Trusses\n[![Python tests](https://github.com/ritchie46/anaStruct/actions/workflows/test.yaml/badge.svg)](https://github.com/ritchie46/anaStruct/actions/workflows/test.yaml)\n[![Documentation Status](https://readthedocs.org/projects/anastruct/badge/?version=latest)](http://anastruct.readthedocs.io/en/latest/?badge=latest)\n![PyPI - Version](https://img.shields.io/pypi/v/anastruct)\n![PyPI - Downloads](https://img.shields.io/pypi/dm/anastruct)\n![Latest Release](https://img.shields.io/github/release-date/ritchie46/anaStruct)\n![Commits since latest release](https://img.shields.io/github/commits-since/ritchie46/anaStruct/latest)\n\n\nAnalyse 2D Frames and trusses for slender structures. Determine the bending moments, shear forces, axial forces and displacements.\n\n## Installation\n\nFor the actively developed version:\n```\n$ pip install git+https://github.com/ritchie46/anaStruct.git\n```\n\nOr for a release:\n```\n$ pip install anastruct\n```\n\n## Read the docs!\n\n[Documentation](http://anastruct.readthedocs.io)\n\n## Questions\n\nGot a question? Please ask on [gitter](https://gitter.im/anaStruct/lobby).\n\n## Includes\n\n* trusses :heavy_check_mark:\n* beams :heavy_check_mark:\n* moment lines :heavy_check_mark:\n* axial force lines :heavy_check_mark:\n* shear force lines :heavy_check_mark:\n* displacement lines :heavy_check_mark:\n* hinged supports :heavy_check_mark:\n* fixed supports :heavy_check_mark:\n* spring supports :heavy_check_mark:\n* q-load in elements direction :heavy_check_mark:\n* point loads in global x, y directions on nodes :heavy_check_mark:\n* dead load :heavy_check_mark:\n* q-loads in global y direction :heavy_check_mark:\n* hinged elements :heavy_check_mark:\n* rotational springs :heavy_check_mark:\n* non-linear nodes :heavy_check_mark:\n* geometrical non linearity :heavy_check_mark:\n* load cases and load combinations :heavy_check_mark:\n* generic type of section - rectangle and circle :heavy_check_mark:\n* EU, US, UK steel section database :heavy_check_mark:\n\n## Examples\n\n```python\nfrom anastruct import SystemElements\nimport numpy as np\n\nss = SystemElements()\nelement_type = 'truss'\n\n# Create 2 towers\nwidth = 6\nspan = 30\nk = 5e3\n\n# create triangles\ny = np.arange(1, 10) * np.pi\nx = np.cos(y) * width * 0.5\nx -= x.min()\n\nfor length in [0, span]:\n    x_left_column = np.ones(y[::2].shape) * x.min() + length\n    x_right_column = np.ones(y[::2].shape[0] + 1) * x.max() + length\n\n    # add triangles\n    ss.add_element_grid(x + length, y, element_type=element_type)\n    # add vertical elements\n    ss.add_element_grid(x_left_column, y[::2], element_type=element_type)\n    ss.add_element_grid(x_right_column, np.r_[y[0], y[1::2], y[-1]], element_type=element_type)\n\n    ss.add_support_spring(\n        node_id=ss.find_node_id(vertex=[x_left_column[0], y[0]]),\n        translation=2,\n        k=k)\n    ss.add_support_spring(\n        node_id=ss.find_node_id(vertex=[x_right_column[0], y[0]]),\n        translation=2,\n        k=k)\n\n# add top girder\nss.add_element_grid([0, width, span, span + width], np.ones(4) * y.max(), EI=10e3)\n\n# Add stability elements at the bottom.\nss.add_truss_element([[0, y.min()], [width, y.min()]])\nss.add_truss_element([[span, y.min()], [span + width, y.min()]])\n\nfor el in ss.element_map.values():\n    # apply wind load on elements that are vertical\n    if np.isclose(np.sin(el.ai), 1):\n        ss.q_load(\n            q=1,\n            element_id=el.id,\n            direction='x'\n        )\n\nss.show_structure()\nss.solve()\nss.show_displacement(factor=2)\nss.show_bending_moment()\n\n```\n\n![](doc/source/img/examples/tower_bridge_struct.png)\n\n![](doc/source/img/examples/tower_bridge_displa.png)\n\n![](doc/source/img/examples/tower_bridge_moment.png)\n\n\n```python\nfrom anastruct import SystemElements\n\nss = SystemElements(EA=15000, EI=5000)\n\n# Add beams to the system.\nss.add_element(location=[0, 5])\nss.add_element(location=[[0, 5], [5, 5]])\nss.add_element(location=[[5, 5], [5, 0]])\n\n# Add a fixed support at node 1.\nss.add_support_fixed(node_id=1)\n\n# Add a rotational spring support at node 4.\nss.add_support_spring(node_id=4, translation=3, k=4000)\n\n# Add loads.\nss.point_load(Fx=30, node_id=2)\nss.q_load(q=-10, element_id=2)\n\n# Solve\nss.solve()\n\n# Get visual results.\nss.show_structure()\nss.show_reaction_force()\nss.show_axial_force()\nss.show_shear_force()\nss.show_bending_moment()\nss.show_displacement()\n```\n![](images/rand/structure.png)\n\n### Real world use case.\n[Non linear water accumulation analysis](https://ritchievink.com/blog/2017/08/23/a-nonlinear-water-accumulation-analysis-in-python/)\n",
    'author': 'Ritchie Vink',
    'author_email': 'ritchie46@gmail.com',
    'maintainer': 'Brooks Smith',
    'maintainer_email': 'smith120bh@gmail.com',
    'url': 'https://github.com/ritchie46/anaStruct',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'extras_require': extras_require,
    'python_requires': '>=3.10',
}
from build_cython_ext import *
build(setup_kwargs)

setup(**setup_kwargs)
