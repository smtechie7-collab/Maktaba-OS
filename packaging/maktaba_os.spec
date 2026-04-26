# PyInstaller spec for Maktaba-OS.
# Build from the project root with: pyinstaller packaging/maktaba_os.spec

from pathlib import Path


ROOT = Path(SPECPATH).parent.parent


datas = [
    (str(ROOT / "src" / "layout" / "templates"), "src/layout/templates"),
    (str(ROOT / "src" / "ui" / "styles"), "src/ui/styles"),
]

binaries = []
bin_dir = ROOT / "bin"
if bin_dir.exists():
    binaries.extend((str(path), "bin") for path in bin_dir.iterdir() if path.is_file())


a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebChannel",
        "weasyprint",
        "pydub",
    ],
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
    [],
    exclude_binaries=True,
    name="Maktaba-OS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Maktaba-OS",
)
