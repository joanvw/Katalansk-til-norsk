"""Pakk hele appen i én fil, ``xlive_eksport.pyz``, som er lett å flytte.

    python -m xlive_eksport.bygg            # → dist/xlive_eksport.pyz

Filen kjøres med ``python xlive_eksport.pyz`` (samme kommandoer som
``python -m xlive_eksport``) – f.eks. i a-Shell på iPad etter at den er
lagt i a-Shell-mappen via Filer-appen, AirDrop eller iCloud Drive.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipapp

PAKKE = os.path.dirname(os.path.abspath(__file__))
STARTER = "from xlive_eksport.__main__ import hoved\nraise SystemExit(hoved())\n"


def bygg(mal: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(mal)), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(PAKKE, os.path.join(tmp, "xlive_eksport"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "bygg.py"))
        with open(os.path.join(tmp, "__main__.py"), "w", encoding="utf-8") as f:
            f.write(STARTER)
        zipapp.create_archive(tmp, mal, interpreter="/usr/bin/env python3", compressed=True)
    return mal


if __name__ == "__main__":
    sti = bygg(sys.argv[1] if len(sys.argv) > 1 else os.path.join("dist", "xlive_eksport.pyz"))
    print(f"Laget {sti} ({os.path.getsize(sti) // 1024} kB)")
