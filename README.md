# AmbiPlex

![AmbiPlex Interface](screenshot1.png)

AmbiPlex synchronizes an addressable LED strip with a local Plex video player,
using a WLED-compatible controller. The interface and application logs are in French.

**AmbiPlex works in real time with MPV: no WLED Subtitles or preencoding are required.**
Configure your Plex player and LEDs, then play a video. WLED Subtitles are an
optional way to reduce CPU/GPU work by calculating a video's LED colors in advance.

## Features

- Local Plex playback selection with a configurable master player.
- Real-time LED rendering using an invisible MPV window and 160x90 RGB capture.
- Black-bar detection, per-side brightness, temporal smoothing, LED routing and offsets.
- Optional WLED Subtitles (`.wledsub.lz4`) that bypass MPV and video decoding during playback.
- Shared NumPy segment sampling for real-time processing and preencoding.
- DDP output to WLED, a web simulator and live monitoring over SSE.
- A web encoder and the Windows Rover application for optional batch preencoding.

## Requirements

- Windows; tested with Python 3.11 and 64-bit libmpv.
- A Plex server and a Plex client on the local network.
- Video paths reported by Plex must be accessible from the AmbiPlex computer.
- A WLED-compatible controller and addressable LEDs.

FFmpeg is needed **only for optional preencoding**, not for real-time playback.
The encoder checks the project directory and PATH, then downloads a Windows build
if none is available.

## Installation

1. Clone this repository and open a terminal in the project directory.
2. Create the environment: `python -m venv venv`.
3. Install dependencies: `venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Place `libmpv-2.dll` at the project root. The optional
   `download_mpv.py` helper downloads it from the upstream Windows builds.
5. Run `start.bat` and open [the dashboard](http://127.0.0.1:5777).

## Configuration and Playback

1. Enter the Plex server URL and token.
2. Set **Master Client Name** to the player's name as reported by Plex.
   Case, underscores and extra whitespace are ignored: `Sony_Bravia` matches
   `Sony Bravia`. Other name differences do not match.
3. Enter the WLED address, horizontal/vertical LED counts and strip routing.
4. Start local playback and adjust the LED settings and synchronization offset.

MPV extracts the LED colors automatically during playback. You do not need to
prepare your videos or generate any additional files.

When a master name is set, AmbiPlex waits for that player instead of selecting
another device. An empty name enables automatic selection among verified local
video sessions. Remote and relayed sessions are rejected; a private IP address
alone is not sufficient. Client identifiers and session keys are checked together.
This relies on Plex's LAN classification, which VPNs or unusual network settings
can affect.

Restart AmbiPlex after source-code updates. Closing the server gracefully releases
the reader, MPV and network resources. `stop.bat` uses forced termination, so it
does not guarantee that graceful cleanup runs.

## Optional: WLED Subtitles

Skip this section to use real-time rendering. To reduce CPU/GPU work during
playback, you can optionally precompute LED tracks for selected videos.

Open the web encoder, or run `start_rover.bat` for batch encoding. The CLI is also available:

```powershell
venv\Scripts\python.exe bake.py "D:\Movies\Film.mkv" --leds-x 64 --leds-y 36 --depth 8 --threads 0
```

The output sits beside the video as `Film.wledsub.lz4`. Its LED dimensions must
match the current configuration. Capture depth and black-bar processing are baked
into the track; changing those requires reencoding. Brightness, smoothing, routing
and side offsets remain adjustable during playback.

Compatible tracks are decompressed in 1 MiB blocks into a disk cache and accessed
with NumPy memmap. Detection is rechecked about once per second during playback.
Missing or incompatible tracks use MPV. Precomputation reduces CPU/GPU work but
does not eliminate it; RGB565 also has lower color precision than RGB888.

![LED Simulator](screenshot2.png)

## Validation and Limits

See [test instructions and measured results](tests/README.md).
The September 2026 changes passed 26 Python tests and 34 exact simulator-canvas
comparisons. Measurements cover individual color functions, not whole-application
CPU consumption. Physical Plex-to-WLED validation remains necessary.

The current DDP sender supports up to 480 LEDs in one packet; larger arrays are
truncated. Native refresh follows MPV's reported frame rate in real-time mode;
precomputed playback uses the configured refresh rate.

## Configuration and Repository Hygiene

`config.json` contains the Plex token and local settings and is ignored by Git.
Virtual environments, downloaded video binaries, calibration videos, generated
LED tracks and runtime caches are also excluded. Keep them locally as needed.
The server listens on port 5777 and has no application authentication; use it
on a trusted network.

## Gallery

![Configuration Detail](screenshot3.png)
![Synchronization Result](screenshot4.png)

Designed by Sébastien Bédard.
