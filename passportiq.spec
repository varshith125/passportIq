# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = []
datas += collect_data_files('rapidocr_onnxruntime')
datas += collect_data_files('webview')

# Frontend dist directory
frontend_dist = os.path.abspath(os.path.join(os.getcwd(), 'frontend', 'dist'))
if os.path.exists(frontend_dist):
    datas.append((frontend_dist, 'frontend_dist'))

# Backend app directory
backend_dir = os.path.abspath(os.path.join(os.getcwd(), 'backend', 'app'))
if os.path.exists(backend_dir):
    datas.append((backend_dir, 'backend/app'))

hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'pydantic_settings',
    'python_multipart',
    'onnxruntime',
    'rapidocr_onnxruntime',
    'cv2',
    'PIL',
    'PIL.Image',
    'numpy',
    'clr_loader',
    'pythonnet',
    'webview',
]
hiddenimports += collect_submodules('app')
hiddenimports += collect_submodules('rapidocr_onnxruntime')
hiddenimports += collect_submodules('webview')

a = Analysis(
    ['desktop_main.py'],
    pathex=['.', 'backend'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'torch',
        'scipy',
        'transformers',
        'sentence_transformers',
        'web3',
        'django',
        'IPython',
        'pytest',
    ],
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
    name='PassportIQ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PassportIQ',
)
