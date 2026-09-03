# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets')]
binaries = []
hiddenimports = [
    'et_xmlfile',
    'cryptography',
    'cryptography.fernet',
    'cryptography.hazmat',
    'cryptography.hazmat.primitives',
    'cryptography.hazmat.primitives.hashes',
    'cryptography.hazmat.primitives.kdf.pbkdf2',
    'cryptography.hazmat.backends',
]
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

crypto_ret = collect_all('cryptography')
datas += crypto_ret[0]; binaries += crypto_ret[1]; hiddenimports += crypto_ret[2]



a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineQuick',
        'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtOpenGL', 'PySide6.QtQuick3D',
        'PySide6.QtPdf', 'PySide6.QtGraphs', 'PySide6.Qt3DRender', 'PySide6.Qt3DCore',
        'PyQt6', 'PyQt5', 'pandas', 'numpy', 'matplotlib', 'scipy',
        'tensorflow', 'keras', 'torch', 'IPython', 'jupyter', 'notebook', 'cv2'
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HavanoPOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/havano_new_blue.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HavanoPOS',
)
