import sys
sys.setrecursionlimit(10000)
sys.path.insert(0, SPECPATH)

from release_materials import LEGAL, record_analysis

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files


if not (LEGAL / "THIRD-PARTY-NOTICES.txt").is_file():
    raise RuntimeError("Run release_materials.py prepare before building")

datas         = [(str(LEGAL), "licenses")]
binaries      = []
hiddenimports = []

_PKGS_TO_COLLECT = [
    "py4cytoscape",
    "ndex2",
    "pandas",
    "pyarrow",    # pandas ArrowExtensionArray dep
    "numpy",
    "networkx",
    "igraph",
    "requests",
    "charset_normalizer",
    "certifi",
    "urllib3",
    "idna",
    "chardet",
    "wget",
    "colorbrewer",
]

for _pkg in _PKGS_TO_COLLECT:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas         += _d
        binaries      += _b
        hiddenimports += _h
    except Exception as _e:
        print(f"[spec] Warning: collect_all({_pkg!r}) skipped: {_e}")


hiddenimports += [
    "xml.etree",
    "xml.etree.ElementTree",
    "xml.etree.cElementTree",
    "collections",
    "collections.abc",
    "typing",
    "types",
    "runpy",
    "traceback",
    "contextlib",
    "io",
    "threading",
    "_thread",
    "concurrent.futures",
    "textwrap",
    "dataclasses",
    "enum",
    "abc",
    "copy",
    "datetime",
    "pprint",
    "string",
    "time",
    "math",
    "re",
    "json",
    "itertools",
    "functools",
    "packaging",
    "packaging.version",
    "packaging.requirements",
    "packaging.specifiers",
]


a = Analysis(
    ["runner.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Keep pydoc for pyarrow and distutils for PyInstaller hooks.
    excludes=[
        "scipy",
        "matplotlib",
        "sklearn",
        "scikit-learn",
        "PIL",
        "Pillow",
        "cv2",
        "tensorflow",
        "torch",
        "numba",
        "tkinter",
        "pytest",
        "py",
        "_pytest",
        "xmlrpc",
        "ftplib",
        "imaplib",
        "telnetlib",
        "turtle",
        "curses",
        "readline",
    ],
    noarchive=False,
    optimize=0,
)

WINDOWS = sys.platform == "win32"

if WINDOWS:
    # Files the runtime never opens: package tests, C headers, type stubs, Cython sources.
    # One-folder builds ship each of them as a file of its own.
    def _needed(entry):
        dest = "/" + entry[0].replace("\\", "/").lower()
        return "/tests/" not in dest and not dest.endswith((".h", ".hpp", ".pyi", ".pxd", ".pyx"))
    a.datas = [entry for entry in a.datas if _needed(entry)]

record_analysis(a.binaries, a.pure)

pyz = PYZ(a.pure)

if WINDOWS:
    # One folder, not one file: a one-file exe unpacks its whole runtime into %TEMP% on
    # every start (about 18 s, virus scan included) and leaves it behind when killed.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="script-runner",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="script-runner")
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name="script-runner",
        debug=False,
        bootloader_ignore_signals=False,
        strip=sys.platform.startswith("linux"),  # stripping breaks macOS code signatures
        upx=False,  # UPX-packed binaries trip antivirus scanners and slow each start
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
