# PyInstaller spec for NCM v4 single-file desktop bundle.
# Build with:  pyinstaller installer/v4/ncm-v4-desktop.spec --clean --noconfirm
# Pre-req: run `npm --prefix app_v4/web run build` so static bundle is fresh.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]

datas = []
static_dir = PROJECT_ROOT / "app_v4" / "service" / "static"
if static_dir.exists():
    datas.append((str(static_dir), "app_v4/service/static"))

theme_dir = PROJECT_ROOT / "app_v4" / "desktop" / "theme"
if theme_dir.exists():
    datas.append((str(theme_dir / "ops_terminal.qss"), "app_v4/desktop/theme"))
    datas.append((str(theme_dir / "ncm.ico"), "app_v4/desktop/theme"))
    datas.append((str(theme_dir / "icon_64.png"), "app_v4/desktop/theme"))

# Collect everything under app_v4 EXCEPT the test tree. Pulling in tests drags
# pytest/qt fixtures and hidden imports that may not exist on the build host
# (e.g. modules that pytest-qt only resolves at test time), causing PyInstaller
# to spin on missing-import lookups.
hiddenimports = [
    name for name in collect_submodules("app_v4")
    if not name.startswith("app_v4.tests")
]
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "aiosqlite",
    "asyncssh",
    "telnetlib3",
    "argon2",
    "argon2._password_hasher",
    "apscheduler.triggers.cron",
    "apscheduler.triggers.interval",
    "apscheduler.executors.asyncio",
    "apscheduler.jobstores.memory",
    # pywin32 pure-python modules (win32/lib) are not picked up from
    # site-packages; without these the frozen app raises
    # "No module named 'win32timezone'" at backup time (v3 spec had these).
    "win32timezone",
    "win32serviceutil",
    "win32service",
    "win32event",
    "servicemanager",
    # Compliance report export (CSV/XLSX/PDF). Imported inside endpoint
    # handlers, so PyInstaller's static analysis misses them; without these
    # the /reviews/compliance/report endpoint 500s in the frozen app.
    "openpyxl",
    "openpyxl.cell._writer",
    "reportlab",
    "reportlab.pdfbase._fontdata",
]


a = Analysis(
    [str(PROJECT_ROOT / "app_v4" / "desktop" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL.ImageTk",
        "test",
        "unittest",
        "pytest",
        "_pytest",
        "pytest_asyncio",
        "pytest_qt",
        "app_v4.tests",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ncm-v4-desktop",
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
    icon=str(PROJECT_ROOT / "app_v4" / "desktop" / "theme" / "ncm.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ncm-v4-desktop",
)
