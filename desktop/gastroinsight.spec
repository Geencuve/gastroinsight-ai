# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
LOCAL_APPS = ["config", "core", "authentication", "venues", "menus", "cameras", "ai_vision", "analytics", "chatbot",
              "api", "reports", "operations", "monitoring", "privacy", "assistant_chat", "sales"]

datas = []
for folder in LOCAL_APPS + ["templates", "staticfiles"]:
    for path in (ROOT / folder).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            datas.append((str(path), str(path.parent.relative_to(ROOT))))
datas += collect_data_files("django", include_py_files=True)
datas += collect_data_files("rest_framework", include_py_files=True)
datas += collect_data_files("reportlab")

hiddenimports = ["decouple", "waitress", "webview", "cv2", "numpy", "scipy", "scipy.stats", "sklearn",
                 "sklearn.linear_model", "sklearn.model_selection", "PIL", "reportlab", "reportlab.platypus",
                 "reportlab.lib", "segno", "rest_framework", "onnxruntime"]
hiddenimports += collect_submodules("django.contrib") + collect_submodules("rest_framework")

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tensorflow", "keras", "torch", "tkinter", "matplotlib", "IPython", "pytest", "black", "mypy"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="GastroInsightAI", console=False,
          icon=str(ROOT / "desktop" / "icon.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="GastroInsightAI")
