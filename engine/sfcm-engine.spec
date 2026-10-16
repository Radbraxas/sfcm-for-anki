# SPDX-License-Identifier: AGPL-3.0-or-later
# PyInstaller recipe for the engine sidecar (roadmap A06). Run via `just build-engine`.
#
# --onedir, not --onefile: a onefile build unpacks itself to a temp folder on every
# launch, which is slow and commonly flagged by antivirus software.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ENGINE = Path(SPECPATH)
REPO = ENGINE.parent

datas = [(str(REPO / "prompts"), "prompts")]
datas += collect_data_files("sfcm_engine")  # SQL migrations
hiddenimports = collect_submodules("sfcm_engine")
binaries = []
# Anki's Rust core (_rsbridge) and its data files.
anki_datas, anki_binaries, anki_hidden = collect_all("anki")
datas += anki_datas
binaries += anki_binaries
hiddenimports += anki_hidden

a = Analysis(
    [str(ENGINE / "scripts" / "frozen_entry.py")],
    pathex=[str(ENGINE / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "pyright", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sfcm-engine",
    console=True,  # stdio is the protocol; the shell hides the window on Windows
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="sfcm-engine", upx=False)
