# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

model_path = os.path.join('models', 'face_landmarker.task')
datas = []
if os.path.exists(model_path):
    datas.append((model_path, 'models'))

a = Analysis(
    ['observer_engine/main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pydantic',
        'pydantic.deprecated',
        'scipy',
        'scipy.spatial',
        'numpy',
        'cv2',
        'mediapipe',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'notebook', 'torch', 'tensorflow'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='observer-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='observer-engine',
)
