# AmbiPlex

**Real-time ambient lighting for your Plex movies. And now, your Xbox games.**

## NEW: Xbox Series X + WLED

### Your Xbox games, all around your screen.

AmbiPlex now turns **Xbox Remote Play into live WLED lighting**. Play on your
TV with your controller connected to the Xbox, while AmbiPlex reads the Remote
Play image on your PC and brings its colors to your LED strip.

**No capture card. No HDMI splitter. No Twitch broadcast. No preencoding.**

Your Xbox stays connected **directly to your TV**. The browser capture feeds
the same LED engine used for Plex, with your existing layout, brightness,
smoothing and routing.

> **Tested on a real Xbox Series X and WLED setup.**
> In testing, colors matched with **no perceptible lighting delay**, and the
> TV **remained in Dolby Vision** during Remote Play.
> These are observations from the tested setup, not a measured zero-latency
> result or a guarantee for every TV, PC and network.

```text
Xbox Series X ---- HDMI directly ----------------> TV
      |
      +---- Remote Play ---> PC / AmbiPlex ------> WLED strip
```

**[Set up Xbox lighting](#xbox-remote-play-setup)** ·
**[Use Plex](#plex-playback)** ·
**[Install AmbiPlex](#installation)**

## Two Sources, One LED Setup

| Source | How it works | Preencoding |
| --- | --- | --- |
| **Xbox Remote Play** | Capture a browser tab on the AmbiPlex PC and send its colors to WLED. | **Never required.** |
| **Local Plex playback** | Follow your selected local player and extract colors with MPV. | **Not required.** Optional WLED Subtitles can reduce decoding work. |

The Plex dashboard, Remote Play page and encoder share a compact dark interface.
Application controls and logs are in French.

**WLED Subtitles are entirely optional.** Neither Xbox lighting nor standard
real-time Plex playback requires generated LED tracks.

## Features

- **Xbox Series X integration through Remote Play**, tested with Chrome.
- Browser capture with a 160x90 sampling image, 30/60 fps target and adjustable framing.
- Direct capture-track processing in Chrome/Edge, without depending on preview rendering.
- A single outstanding image to prevent a backlog; connection keepalives for static scenes.
- Exclusive WLED control during capture, with a **Retour à Plex** button.
- Strict local Plex session selection with a configurable master player.
- Real-time MPV capture, black-bar detection, per-side brightness and linked controls.
- Temporal smoothing, strip routing, corner margins and per-side LED offsets.
- DDP output, a live LED simulator and monitoring over SSE.
- Optional WLED Subtitles, a web encoder and the Windows Rover batch encoder.

## Requirements

### Common Installation

- Windows; tested with Python 3.11 and 64-bit libmpv.
- A WLED-compatible controller and addressable LEDs.
- A PC that can reach the controller on the local network.
- The Python dependencies and `libmpv-2.dll` described below. The current
  application still imports the MPV components when using Xbox capture.

### For Xbox

- Xbox Remote Play working in Chrome or Edge **on the AmbiPlex PC**.
- The capture page and the Xbox tab open in the same browser.
- Xbox Series X is the physically tested console. Other console/browser
  combinations have not been validated in this project.
- 720p is sufficient for the 160x90 LED sampling image; 1080p is not required.

### For Plex

- A Plex server and a Plex client on the local network.
- Video paths reported by Plex accessible from the AmbiPlex computer.

An active Plex playback session is **not** required for Xbox capture.

FFmpeg is needed **only for optional preencoding**, not for standard real-time
playback or Xbox capture. The encoder checks the project directory and PATH,
then downloads a Windows build if none is available.

## Installation

1. Clone this repository and open a terminal in the project directory.
2. Create the environment: `python -m venv venv`.
3. Install dependencies: `venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Place `libmpv-2.dll` at the project root. The optional
   `download_mpv.py` helper downloads it from the upstream Windows builds.
5. Start AmbiPlex using **one** method: `start.bat`, or your Python service manager.
6. Open [the dashboard](http://localhost:5777), enter the WLED address and LED
   layout, then apply the calibration.

**Upgrading an existing installation?** Reinstall the requirements to include
the new `websockets` dependency. Restart through your usual service manager
after Python changes, then refresh the browser to load the updated interface.

### Service Managers, Including PyManager

Use the project's `venv\Scripts\python.exe`, pass `web.py` as the script,
and set the working directory to the AmbiPlex folder. The web port is **5777**.

If PyManager already manages AmbiPlex, use its Start/Stop controls.
**Do not also launch `start.bat` or another copy of `web.py`.** A second
instance cannot bind port 5777 and exits, even though the first instance is
still serving the interface. Different launch arguments can also prevent a
manager from recognizing an independently started instance.

## Xbox Remote Play Setup

1. Keep the Xbox connected directly to your TV and the controller connected
   to the console. Start your game.
2. Open Xbox Remote Play on the AmbiPlex PC in Chrome or Edge. Start with
   **720p** and confirm that the game image looks correct.
3. In the **same browser**, open [AmbiPlex Remote Play](http://localhost:5777/remote),
   preferably in a separate window.
4. Click **Choisir la source** and select the **Xbox Remote Play tab**, without audio.
5. Leave the capture cadence at **60 images/s** for the first test. It is a target,
   not a guarantee that the source, browser and PC deliver 60 distinct frames/s.
6. Check the preview and enjoy the lights. Adjust framing if the preview includes
   browser-player controls or cuts off part of the game.

Centered 16:9 framing is enabled by default. Four crop margins are available
for off-center video. The preview shows the image actually supplied to the LED
engine, not a separate cosmetic preview.

The existing layout, brightness, smoothing, black-bar detection and routing
settings are reused. Xbox capture does not overwrite Plex synchronization
settings or save its framing/cadence controls to `config.json`.

### Switching Back to Plex

Click **Retour à Plex** to stop capture and return to the dashboard. Plex can
then resume LED output. This does **not** stop the Xbox game or the Xbox Remote
Play session.

**Arrêter**, ending browser sharing or closing the capture page also releases
WLED control. A connection with no frames or keepalives expires after fifteen
seconds. Last colors may remain until Plex or WLED's realtime timeout takes over;
stopping capture does not explicitly power off the strip.

### Capture and Latency Notes

- Open the capture page through **localhost**, not the PC's LAN address.
  Capture WebSockets require a loopback connection and a matching local Origin.
- Images are sent locally as RGBA8, with no additional lossy video encoder
  between browser capture and the LED engine. Remote Play itself remains a
  compressed video source.
- Only one image awaits acknowledgment; intermediate images are skipped
  instead of accumulating in a queue.
- The displayed timings measure **PC transport and LED processing only**.
  They do not measure the full Xbox-to-WLED delay.
- Smoothing deliberately softens and delays transitions. Use your normal LED
  settings and judge the result on the strip.
- Chrome/Edge use direct track processing. Other supported browsers may fall
  back to video rendering callbacks. Freezing/discarding a tab, source suspension
  or a network interruption can still interrupt capture.
- Refreshing the capture page ends sharing; select the Xbox tab again afterward.
- No capture file, Twitch relay or browser extension is required.

## Plex Playback

1. Enter the Plex server address and token in the dashboard.
2. Set **Lecteur local** to the player's name as reported by Plex.
   Case, underscores and extra whitespace are ignored: `Sony_Bravia` matches
   `Sony Bravia`. Other name differences do not match.
3. Configure WLED and start playback on that player.
4. Adjust the LED settings and synchronization offset as needed.

MPV extracts the colors automatically. There are **no additional files to
prepare** for standard real-time playback.

When a master name is set, AmbiPlex waits for that player instead of selecting
another device. An empty name enables automatic selection among verified local
video sessions. Remote and relayed **Plex sessions** are rejected; this restriction
does not disable the separately selected **Xbox Remote Play source**.

A private IP alone is not sufficient. Client identifiers and session keys are
checked together. Selection relies on Plex's LAN classification, which VPNs or
unusual network settings can affect.

## Optional: WLED Subtitles

Skip this section for Xbox or standard real-time Plex rendering. For selected
movies, you can optionally precompute LED tracks to reduce CPU/GPU decoding work.

Open the web encoder, or run `start_rover.bat` for batch encoding.
The CLI is also available:

```powershell
venv\Scripts\python.exe bake.py "D:\Movies\Film.mkv" --leds-x 64 --leds-y 36 --depth 8 --threads 0
```

The output sits beside the video as `Film.wledsub.lz4`. Its LED dimensions must
match the configuration. Capture depth and black-bar processing are baked into
the track; changing those requires reencoding. Brightness, smoothing, routing
and side offsets remain adjustable during playback.

Compatible tracks are decompressed in 1 MiB blocks into a disk cache and accessed
with NumPy memmap. Detection is rechecked about once per second during playback.
Missing or incompatible tracks use MPV. Precomputation reduces CPU/GPU work but
does not eliminate it; RGB565 also has lower color precision than RGB888.
These tracks are not used for live Xbox gameplay.

## Validation and Limits

See [test instructions and results](tests/README.md).

| Check | Recorded result |
| --- | --- |
| Python regression suite | 37 tests passed. |
| LED simulator | 34 exact canvas comparisons against the reference implementation. |
| Remote Play browser pipeline | Synthetic colors, lifecycle, static scenes, backpressure and return-to-Plex checks passed. |
| Shared web interface | 12 layouts tested across 320, 390, 768 and 1440 pixels. |
| Physical Xbox Series X + WLED | Matching colors, no perceptible delay and TV Dolby Vision retained in the tested setup. |
| Physical Plex local/remote selection | End-to-end verification after the selection changes remains outstanding. |

These results do not establish universal hardware compatibility or zero latency.
Function benchmarks exclude whole-application decoding, capture and networking.

The current DDP sender supports up to **480 LEDs** in one packet; larger arrays
are truncated. Native refresh follows MPV's reported frame rate in real-time
Plex mode. WLED Subtitles use the configured refresh rate; Xbox capture has its
own 30/60 fps selector.

The web server has no application authentication: use it on a trusted network,
not exposed directly to the Internet. Local capture restrictions do not add
authentication to the rest of the dashboard.

Graceful server shutdown releases the reader, MPV and network resources.
`stop.bat` uses forced termination and does not guarantee that cleanup runs.

## Configuration and Repository Hygiene

`config.json` contains the Plex token and local settings and is ignored by Git.
Virtual environments, downloaded video binaries, calibration videos, generated
LED tracks and runtime caches are excluded. Keep them locally as needed.
Automated browser-test screenshots are written to the OS temporary directory.

## Gallery

Current interface, captured September 14, 2026. Pages are shown at rest, with
no active playback or encoding. The Plex token is omitted and the WLED address
is an example; no saved settings were changed for these screenshots.

### Xbox Remote Play

Choose the Remote Play source, adjust framing and monitor local processing.
The preview is empty here because screen sharing has not started.

![Xbox Remote Play interface before starting capture](screenshot4.png)

### Plex Dashboard

![Plex connection, synchronization and playback status](screenshot1.png)

### WLED Calibration

![WLED layout, capture settings, LED simulator and brightness controls](screenshot2.png)

### Optional WLED Subtitles Encoder

![Optional video encoder for precomputed WLED Subtitles tracks](screenshot3.png)

Designed by Sébastien Bédard.
