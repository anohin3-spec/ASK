# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller ASK.spec (вызывается из build_installer.bat)

_hidden = [
    'supabase',
    'postgrest',
    'realtime',
    'storage3',
    'httpx',
    'httpcore',
    'h11',
    'certifi',
    'anyio',
    'sniffio',
    'idna',
    'pydantic',
    'pydantic_core',
    'dotenv',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=_hidden,
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
    name='ASK',
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
    icon=['assets\\app.ico'],
)
