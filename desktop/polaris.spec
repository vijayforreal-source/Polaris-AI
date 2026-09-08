# Folder-based PyInstaller build is intentional: PyTorch and NetCDF are more
# reliable as collected resources than in a single-file extraction bundle.
from pathlib import Path
import pyproj

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
hiddenimports = collect_submodules("backend") + ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto"]
datas = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "backend"), "backend"),
    (str(ROOT / "models"), "models"),
    (str(ROOT / "data" / "processed"), "data/processed"),
    (str(ROOT / "data" / "raw"), "data/raw"),
    (str(Path(pyproj.__file__).resolve().parent / "proj_dir"), "pyproj/proj_dir"),
]

a = Analysis([str(ROOT / "desktop" / "launcher.py")], pathex=[str(ROOT)], hiddenimports=hiddenimports, datas=datas)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name="POLARIS-AI", console=False, exclude_binaries=True)
coll = COLLECT(exe, a.binaries, a.datas, name="POLARIS-AI")
