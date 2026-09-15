"""Interactive native preview using disposable videos, never local settings."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rover import AmbiPlexRover
from rover_batch import DEFAULTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("FFmpeg doit être installé pour cet essai (aucun téléchargement automatique).")
    with tempfile.TemporaryDirectory(prefix="ambiplex-rover-test-") as folder:
        root = Path(folder)
        subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x180:rate=24", "-t", "4", "-c:v", "mpeg4",
                        str(root / "01 - Mire couleur.mp4")], check=True,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
        shutil.copyfile(root / "01 - Mire couleur.mp4", root / "02 - Seconde mire.mp4")
        (root / "03 - Fichier invalide.mkv").write_bytes(b"Synthetic invalid video for failure testing")
        with patch("rover.load_settings", return_value=DEFAULTS.copy()):
            app = AmbiPlexRover()
            app.title("AmbiPlex Rover - Fichiers de test")
            if args.compact:
                app.geometry("880x720")
            app.current_folder = folder
            app.folder_entry.configure(state="normal")
            app.folder_entry.insert(0, "Fichiers de test temporaires")
            app.folder_entry.configure(state="readonly")
            app.scan_folder()
            app.mainloop()


if __name__ == "__main__":
    main()
