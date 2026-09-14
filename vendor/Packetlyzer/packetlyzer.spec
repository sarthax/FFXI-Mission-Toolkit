# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Packetlyzer.

Build with:
    pyinstaller packetlyzer.spec

Output goes to dist/Packetlyzer/
"""

import os
import sys

block_cipher = None

# Base directory
BASE = os.path.dirname(os.path.abspath(SPEC))

# Data files to include alongside the executable
# Format: (source_path, destination_folder_in_dist)
datas = [
    (os.path.join(BASE, 'packetlyzer_db.xml'), '.'),
    (os.path.join(BASE, 'lookup'), 'lookup'),
]

# Conditionally include optional files
for opt_file in ['packetlyzer_ext.json', 'signals_db.json', 'ffxi.xml']:
    path = os.path.join(BASE, opt_file)
    if os.path.isfile(path):
        datas.append((path, '.'))

a = Analysis(
    [os.path.join(BASE, 'packetlyzer.py')],
    pathex=[BASE],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'analyzer',
        'analyzer.config',
        'analyzer.decoder',
        'analyzer.detail_panel',
        'analyzer.dialog_table',
        'analyzer.display',
        'analyzer.export_tab',
        'analyzer.exporter',
        'analyzer.ffxi_dat',
        'analyzer.history_panel',
        'analyzer.importer',
        'analyzer.live_editor',
        'analyzer.lookup',
        'analyzer.message_resolver',
        'analyzer.npc_lookup',
        'analyzer.packet_db',
        'analyzer.reverse_engineer_tab',
        'analyzer.server',
        'analyzer.settings_panel',
        'analyzer.settings_tab',
        'analyzer.signal_db',
        'analyzer.themes',
        'analyzer.bottom_panel',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'tkinter', 'unittest'],
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
    name='Packetlyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (GUI app)
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
    upx=True,
    upx_exclude=[],
    name='Packetlyzer',
)
