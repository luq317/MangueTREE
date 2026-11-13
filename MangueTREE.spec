# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec of MangueTREE (desktop).
Packages Python + Streamlit + the app into a native executable.

Build (on the target operating system itself):
    pip install -r requirements.txt pyinstaller
    pip install --no-deps .
    pyinstaller MangueTREE.spec

Output:
    Windows: dist/MangueTREE/MangueTREE.exe   (self-contained folder)
    macOS:   dist/MangueTREE.app              (application bundle)
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None

# Collect code, data files and hidden imports of the heavy libraries
_pkgs = ["streamlit", "plotly", "reportlab", "matplotlib", "openpyxl",
         "unidecode", "PIL", "pandas", "numpy", "altair", "pyarrow", "tornado"]
datas, binaries, hiddenimports = [], [], []
for _p in _pkgs:
    try:
        d, b, h = collect_all(_p)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

# Package metadata that Streamlit reads at run time
for _m in ["streamlit", "pandas", "numpy", "altair", "pyarrow", "plotly"]:
    try:
        datas += copy_metadata(_m)
    except Exception:
        pass

# Application files: the whole package (code, app/, pages/, assets/) goes to
# <bundle>/manguetree, from where Streamlit runs app/Home.py.
datas += [("src/manguetree", "manguetree")]
if os.path.isdir(".streamlit"):
    datas += [(".streamlit", ".streamlit")]
if os.path.exists("data/guaratiba_T2_2009.xlsx"):
    datas += [("data/guaratiba_T2_2009.xlsx", "data")]

hiddenimports += ["manguetree", "manguetree.calc", "manguetree.io",
                   "manguetree.charts", "manguetree.report", "manguetree.branding",
                   "streamlit.web.cli", "streamlit.runtime.scriptrunner.magic_funcs"]

a = Analysis(
    ["src/manguetree/launcher.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_ASSETS = "src/manguetree/app/assets"
_ico = _ASSETS + "/logo.ico" if os.path.exists(_ASSETS + "/logo.ico") else None
_icns = _ASSETS + "/logo.icns" if os.path.exists(_ASSETS + "/logo.icns") else None

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MangueTREE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # no terminal window (the app has a "Quit MangueTREE" button)
    icon=_ico,
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False,
               name="MangueTREE")

# On macOS, package as an .app
app = BUNDLE(
    coll,
    name="MangueTREE.app",
    icon=_icns,
    bundle_identifier="org.manguetree.app",
    info_plist={"NSHighResolutionCapable": True,
                "CFBundleDisplayName": "MangueTREE",
                "CFBundleShortVersionString": "1.0.0"},
)
