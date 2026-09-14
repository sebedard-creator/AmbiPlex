# Regression Checks

The reference implementation is Git commit
`81db0f00bcdf3cc94db47fc597fb028205fa72ab` (before the performance changes).
Python tests load its LED and bake functions in memory. The browser check
loads its JavaScript in an isolated page with synthetic configuration and SSE
events. Neither check connects to Plex or sends packets to a physical LED strip.
Keep this commit available in local Git history to rerun comparisons.

From the project directory:

```powershell
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

The Python suite requires the installed application dependencies and local libmpv
DLL described in the main README. The calibration-video test additionally requires
FFmpeg on PATH and local `calibration*.mp4` files. Those videos are ignored by Git;
this test is explicitly skipped when FFmpeg or the videos are absent.

For the simulator, use Node and an available Playwright installation:

```powershell
# Optional: absolute path to an existing Playwright package.
$env:PLAYWRIGHT_MODULE = 'C:/path/to/node_modules/playwright'
# Optional: use installed Chrome instead of Playwright's bundled Chromium.
$env:PLAYWRIGHT_CHANNEL = 'chrome'
node tests/check_simulator.cjs
```

## Verified on 2026-09-13

26 Python tests passed with all six local calibration videos available.

- Exact RGB output and smoothing state versus the original LED engine.
- Exact RGB565 bytes versus the original bake function.
- Synthetic sequences, dark frames, letterbox changes, routing, brightness,
  offsets, corner gaps, non-divisible zones and zero LEDs on one axis.
- All six local calibration videos, 90 frames per video, decoded once and
  supplied to both implementations.
- Identical DDP packets with a mocked socket and unchanged per-frame send cadence.
- WLEDSUB cache hits, negative results, appearance, replacement, removal,
  dimension changes, bounded decompression reads, Windows mapping release,
  asynchronous cancellation and a film change during loading.
- A slow browser retains the latest monitoring state; log/preset events remain ordered.
- MPV command deduplication and Rover's slider no longer creating widgets.
- 34 exact canvas comparisons on desktop/mobile, including geometry changes,
  font-cache invalidation and repeated frames; no JavaScript errors.
- Separate local MPV smoke test: 160x90 capture, pause, seek, speed and resume.

Five-run median on synthetic 160x90 RGB8 frames, 200 LEDs, depth 8%:

| Function | Reference | Optimized |
| --- | ---: | ---: |
| LED calculation | 1.410 ms/frame | 0.490 ms/frame |
| Bake calculation | 1.264 ms/frame | 0.331 ms/frame |

These timings exclude video decoding, GPU capture, disk and network latency.
They are not whole-application CPU or encoding-speed guarantees.

Rendering thresholds, smoothing, crop rules, RGB565 conversion, DDP format and
LED refresh-rate selection are unchanged. Sampling sums exact integer RGB8
values and preserves the original segment boundaries and final rounding.
Non-RGB8 inputs retain the original NumPy averaging path.

WLEDSUB files are rechecked once per second; a newly created/replaced file may
therefore take up to approximately one second to be detected, plus I/O time.
Paused MPV frames are still captured and processed every cycle to preserve
late reader updates, smoothing and LED output. Only redundant control commands
are suppressed, with MPV property observation and an unconditional fallback.

The physical Plex-to-WLED setup has not been exercised end to end. These checks
establish exact output for the tested inputs, not a universal hardware guarantee.

## Local session selection

`test_local_sessions.py` verifies that remote or relayed sessions cannot become
the AmbiPlex master, even when their reported IP is private or they share a client
identifier with a local session. It also covers pause/resume/seek, session changes,
multiple tabs, lookup failures and the session-query rate limit.

The configured `master_client` is now required to match the local player's name
(ignoring case, underscores and extra whitespace). There is no fallback to an
unrelated player when that name is set. Leaving it empty enables automatic
selection among verified local video sessions only.

Plex's `Player.local` flag must be true, `Player.relayed` must be false, and any
reported `Session.location` must be `lan`. Private IP prefixes are not sufficient.
Both client identifier and session key must match the verified session snapshot.
Snapshots refresh at most once per second on incoming playback notifications.
This follows Plex's LAN classification; a VPN or unusual Plex network settings
can affect that classification. No active sessions were available for a live
local-versus-remote comparison when this change was made.

## Remote Play capture

`test_remote_capture.py` exercises RGBA-to-LED equivalence, single ownership,
Plex output exclusion (including a capture started during WLEDSUB loading),
local Origin checks, invalid frames, missing WLED configuration, timeout,
disconnect, exceptions and cancellation. DDP is mocked; no physical strip is used.

```powershell
# Same Playwright environment as check_simulator.cjs above.
node tests/check_remote.cjs
```

The browser test starts its own isolated server with synthetic configuration,
a generated 720p canvas stream and a mocked DDP sender. It never reads the real
config or connects to Plex/Xbox/WLED. It checks pixel colors through the actual
LED engine, capture start/stop/restart, denied sharing, ended tracks, one pending
frame and ACK timeout, plus desktop/mobile layout and JavaScript errors.
Rendering callbacks are deliberately disabled to exercise the direct track
reader. A frozen source remains connected beyond the old five-second deadline;
a unit test verifies that keepalives renew the connection without sending DDP.
Screenshots go to the OS temporary directory, not the repository.

The project owner subsequently validated actual Xbox Series X Remote Play
capture with the physical WLED strip: matching colors, no perceptible delay,
and TV Dolby Vision retained in that setup. This user-driven result complements
the synthetic checks; it is not an instrumented latency/color measurement or
a compatibility claim for other hardware. Browser freezing and network-loss
behavior still depend on the installation.

Validation after this addition on 2026-09-13: 37 Python tests passed, the 34
existing simulator comparisons remained exact, and the Remote Play browser
checks passed with screenshots inspected at 1280x900 and 390x844.

## Shared Web Interface

```powershell
node tests/check_interface.cjs
```

Uses the same Playwright setup. All HTTP requests are intercepted: synthetic
configuration, mocked saves, file browsing and encoder progress. No real token,
configuration file, Plex connection, capture permission or WLED request is used.

Checks Plex and calibration payloads, linked/unlinked brightness, encoder
selection/start/completion, shared colors, navigation and control overflow on
all three pages at 1440, 768, 390 and 320 pixels. Six screenshots are written
to the OS temporary directory. Twelve layouts passed and desktop/mobile
screenshots were inspected. `check_simulator.cjs` still passes all 34 exact
pixel comparisons; `check_remote.cjs` also verifies that Retour a Plex releases
an active capture before navigation. Native Rover styling is unchanged.

## Release Validation Summary

Recorded for the Xbox/interface commit, reviewed on 2026-09-14:

- 37 Python tests passed on 2026-09-13, including the capture keepalive fix.
- 34 simulator comparisons remained pixel-identical after the interface update.
- Remote Play browser checks passed, including static scenes and return to Plex.
- 12 web layouts passed, with forms and desktop/mobile screenshots checked.
- Physical Xbox Series X/WLED operation was confirmed by the project owner.
- PyManager reports AmbiPlex running on port 5777; all three pages returned HTTP 200.

The 2026-09-14 documentation preparation did not rerun the code tests or change
application behavior. Instrumented end-to-end latency/colorimetry and a physical
Plex local-versus-remote selection test remain outside these recorded results.
