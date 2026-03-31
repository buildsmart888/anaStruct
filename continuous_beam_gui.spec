# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter

ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['continuous_beam_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(ctk_path, "assets"), "customtkinter/assets"),
        ('anastruct/material/*.csv', 'anastruct/material'),
        ('anastruct/sectionbase/data/*.xml', 'anastruct/sectionbase/data'),
    ],
    hiddenimports=['PIL._tkinter_wrapper'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='continuous_beam_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
