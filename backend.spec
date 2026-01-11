# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Syncterra backend

import os
import sys

# Add project root to path
block_cipher = None

a = Analysis(
    ['run_backend.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('asyncapi.yaml', '.'),
    ],
    hiddenimports=[
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
        'aiosqlite',
        'sqlalchemy.dialects.sqlite',
        'backend.api',
        'backend.api.settings',
        'backend.api.tracks',
        'backend.api.system',
        'backend.api.websocket',
        'backend.api.playlists',
        'backend.api.album_art',
        'backend.db',
        'backend.db.database',
        'backend.db.models',
        'backend.db.albumart_database',
        'backend.db.albumart_models',
        'backend.core',
        'backend.core.scanner',
        'backend.core.syncer',
        'backend.core.album_art_scanner',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
