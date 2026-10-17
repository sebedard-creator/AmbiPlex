"""Launch the local Chiaki application, never a command supplied by the browser."""

import csv
import io
import os
from pathlib import Path
import shutil
import subprocess
import threading


EXECUTABLES = {"chiaki.exe", "chiaki-ng.exe"}


def find_chiaki():
    configured = os.environ.get("AMBIPLEX_CHIAKI_PATH")
    if configured:
        candidates = [Path(configured)]
    else:
        candidates = [Path(found) for name in sorted(EXECUTABLES)
                      if (found := shutil.which(name))]
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base:
                for folder in ("chiaki-ng", "Chiaki", "Programs/chiaki-ng"):
                    candidates.extend(Path(base) / folder / name for name in sorted(EXECUTABLES))
        portable = Path.home() / "Downloads" / "AmbiPlex-PS4"
        candidates.extend(sorted(portable.glob("chiaki-ng-*/app/chiaki-ng-Win/chiaki.exe"), reverse=True))
    for candidate in candidates:
        resolved = candidate.resolve()
        if (candidate.is_absolute() and not resolved.drive.startswith("\\\\")
                and resolved.name.lower() in EXECUTABLES and resolved.is_file()):
            return resolved
    raise FileNotFoundError("Chiaki introuvable. Configure AMBIPLEX_CHIAKI_PATH sur le PC AmbiPlex.")


class ChiakiLauncher:
    def __init__(self):
        self.lock = threading.Lock()
        self.process = None

    def start(self):
        if os.name != "nt":
            raise NotImplementedError("Le lancement de Chiaki est disponible sur Windows uniquement.")
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                return {"status": "already_running", "message": "Chiaki est déjà ouvert."}
            # Check manually opened instances too, without a shell or extra dependency.
            inventory = subprocess.run(
                ["tasklist.exe", "/FO", "CSV", "/NH"], capture_output=True,
                text=True, errors="replace", timeout=3, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            rows = list(csv.reader(io.StringIO(inventory.stdout)))
            if not any(len(row) >= 2 and row[1].isdigit() for row in rows):
                raise OSError("Process inventory unavailable")
            if any(row and row[0].lower() in EXECUTABLES for row in rows):
                return {"status": "already_running", "message": "Chiaki est déjà ouvert."}
            executable = find_chiaki()
            self.process = subprocess.Popen(
                [str(executable)], cwd=str(executable.parent), shell=False,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return {"status": "started", "message": "Chiaki lancé."}
