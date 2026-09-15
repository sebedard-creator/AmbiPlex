"""Discovery and sequential encoding, independent of the Tk event loop."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
DEFAULTS = {"leds_top": 64, "leds_side": 36, "led_depth": 8, "ffmpeg_threads": 0}
PROGRESS = re.compile(r"Progression:\s*(\d+(?:\.\d+)?)%")


@dataclass(frozen=True)
class VideoFile:
    path: str
    relative: str
    has_track: bool


def track_path(path):
    return Path(path).with_suffix(".wledsub.lz4")


def discover_videos(folder, stop, on_error):
    for root, directories, files in os.walk(folder, onerror=on_error):
        if stop.is_set():
            return
        directories.sort(key=str.casefold)
        # Reuse the directory listing instead of a stat call for each video.
        names = {os.path.normcase(name) for name in files}
        for name in sorted(files, key=str.casefold):
            if stop.is_set():
                return
            path = Path(root) / name
            if path.suffix.lower() in {".mkv", ".mp4", ".avi"}:
                yield VideoFile(str(path), os.path.relpath(path, folder),
                                os.path.normcase(track_path(path).name) in names)


def load_settings(path=ROOT / "config.json"):
    if not Path(path).exists():
        return DEFAULTS.copy()
    with open(path, encoding="utf-8") as source:
        config = json.load(source)
    if not isinstance(config, dict):
        raise ValueError("La configuration doit être un objet JSON.")
    settings = {key: int(config.get(key, value)) for key, value in DEFAULTS.items()}
    if not (0 <= settings["leds_top"] <= 65535 and 0 <= settings["leds_side"] <= 65535
            and settings["leds_top"] + settings["leds_side"] > 0):
        raise ValueError("Nombre de LED invalide pour le format WLEDSUB.")
    if not 1 <= settings["led_depth"] <= 100 or settings["ffmpeg_threads"] < 0:
        raise ValueError("Profondeur ou nombre de threads invalide.")
    return settings


def conflicting_outputs(files):
    seen, collisions = set(), []
    for path in files:
        output = os.path.normcase(os.path.abspath(track_path(path)))
        if output in seen:
            collisions.append(path)
        seen.add(output)
    return collisions


def encode_batch(files, settings, stop, emit):
    """Stop between files only, after the current bake publishes its track."""
    python = ROOT / "venv" / "Scripts" / "python.exe"
    python = str(python) if python.exists() else sys.executable
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    succeeded = failed = 0
    for index, path in enumerate(files):
        if stop.is_set():
            break
        emit("started", (path, index, len(files)))
        command = [python, "-u", str(ROOT / "bake.py"), path,
                   "--leds-x", str(settings["leds_top"]),
                   "--leds-y", str(settings["leds_side"]),
                   "--depth", str(settings["led_depth"]),
                   "--threads", str(settings["ffmpeg_threads"])]
        try:
            with subprocess.Popen(command, cwd=str(ROOT), env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", bufsize=1,
                                  creationflags=0x08000000 if os.name == "nt" else 0) as process:
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    match = PROGRESS.search(line)
                    if match:
                        percent = min(100.0, max(0.0, float(match.group(1))))
                        emit("progress", (path, index, len(files), percent, line))
                    else:
                        emit("log", line)
                code = process.wait()
            if code != 0:
                raise RuntimeError(f"L'encodeur a quitté avec le code {code}.")
            if not track_path(path).is_file():
                raise RuntimeError("La piste attendue n'a pas été créée.")
        except Exception as error:
            failed += 1
            emit("file_done", (path, False, str(error), index + 1, len(files)))
        else:
            succeeded += 1
            emit("file_done", (path, True, "", index + 1, len(files)))
    emit("batch_done", (succeeded, failed, len(files) - succeeded - failed))
