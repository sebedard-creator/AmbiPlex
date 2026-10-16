# Xbox Setup: Series X|S + AmbiPlex

[Back to AmbiPlex](README.md) | [PS4 / PS5 guide](PLAYSTATION_SETUP.md)

Play on your TV with the controller connected to the Xbox. AmbiPlex captures
the Remote Play browser tab on your PC and sends its colors to WLED.

```text
Xbox Series X|S ------ HDMI directly --------------> TV
      |
      +---- Remote Play browser tab ---> AmbiPlex ---> WLED strip

Controller ---------- directly to Xbox
```

No HDMI splitter, capture card, Twitch broadcast, browser extension or
preencoded LED track is needed.

## Compatibility

Xbox lists **both Series X and Series S** as compatible with Remote Play.
This guide uses the same browser-capture workflow for either console.
[Xbox Remote Play requirements](https://www.xbox.com/en-US/consoles/remote-play)

Physical AmbiPlex testing was on **Series X**, not Series S: colors matched,
no lighting delay was perceptible, and the TV remained in Dolby Vision.
Those observations are not a zero-latency measurement or a promise that every
console, game and TV retains the same video modes. Series S remains untested
in this project; verify its TV output and local controller behavior too.

## Before You Start

- Complete the [AmbiPlex installation](README.md#installation) and WLED calibration.
- Use a Microsoft account with an Xbox profile and enable the console's remote
  features using [Xbox's setup instructions](https://support.xbox.com/en-US/help/games-apps/game-setup-and-play/how-to-set-up-remote-play).
- Keep the console powered on for the first test. Prefer Ethernet for the PC
  and Xbox, or a stable local network. Xbox's service also has Internet/account
  requirements; this guide does not replace them.
- Use **Chrome** on the AmbiPlex PC. Edge supports the direct capture path too,
  but Chrome is the physically tested browser here.
- Keep your controller paired directly with the Xbox for the TV-gaming setup.
  If your Remote Play client insists on a PC controller, resolve that arrangement
  first; do not assume every client behaves like the tested setup.

## 1. Start Xbox Remote Play

1. Keep the Xbox connected **directly to the TV** and start your game.
2. On the PC, open [Xbox Remote Play](https://www.xbox.com/en-US/play/consoles),
   sign in and connect to your own console, not a cloud-gaming session.
3. Confirm the game moves and its colors look correct in the browser tab.
4. If offered, start at **720p**. The LED sampling image is 160x90, so 1080p is
   not required; increase stream quality if compression harms the colors.
5. Verify the controller still operates the game directly on the console.

Do not change HDMI, HDR or Dolby Vision settings just to obtain lighting.
If the console changes its TV output during Remote Play, check that separately;
the PC stream is not a guarantee about the HDMI signal.

## 2. Capture in AmbiPlex

1. In the **same browser**, open [AmbiPlex Remote Play](http://localhost:5777/remote),
   preferably in a separate window.
2. Leave **Source** on **Xbox Remote Play** and click **Choisir la source**.
3. In the browser chooser, share the **Xbox Remote Play tab**, without audio.
   Do not select the AmbiPlex page or a different window.
4. Start with **60 images/s**. This is a target, not a guarantee that the source,
   browser and PC deliver 60 distinct frames every second.
5. Compare the preview with the game. Remove player controls or borders with
   the four crop margins; adjust **Centrage 16:9** if needed.
6. Test motion, dark scenes and stable colors under your normal window/background
   conditions. Do not discard/freeze the capture page or suspend its source.

Open AmbiPlex via **localhost**, not the PC's LAN address. Capture WebSockets
require loopback and a matching local Origin. No active Plex session is needed.

The preview shows the 160x90 sRGB image supplied to the shared LED engine.
Layout, per-side brightness, smoothing, black-bar detection and routing are
reused. Source dimensions report the captured image, not necessarily the
console stream's resolution. Framing/cadence controls are not saved to `config.json`.

## 3. Stop or Return to Plex

Click **Arrêter** or **Retour à Plex**, end browser sharing, or close the capture
page. AmbiPlex releases WLED control so Plex can resume. It does **not** explicitly
disconnect Xbox Remote Play, stop the game or turn off the strip.

Last LED colors can remain until Plex or WLED's realtime timeout takes over.
Only one AmbiPlex capture can own the output at a time. Stop it before switching
to another tab or console.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Capture unavailable | Open `http://localhost:5777/remote` in Chrome on the AmbiPlex PC and allow sharing. |
| Wrong colors or framing | Compare the Xbox tab and AmbiPlex preview; exclude browser/player controls and check the crop margins. |
| Stream works but lights freeze | Verify the capture page/source is not suspended. Retry in Chrome and check that fresh frames reach the preview. |
| Inactive for 15 seconds | Update/restart AmbiPlex through its existing manager, reload the page and reselect the tab. A frozen page cannot reply to keepalives. |
| Another capture is active | Stop or close the previous capture and let its connection release; do not start another AmbiPlex server. |
| Controller no longer controls the TV game | Verify it is still connected to the console rather than paired to the PC. Check the chosen Remote Play client's requirements. |
| Lag | Check the Remote Play image first, then network quality, stream settings and LED smoothing. Lower resolution is not a guarantee of lower total delay. |

After five seconds without a message, AmbiPlex sends a server probe. A client
that sends no frames or keepalive replies expires after fifteen seconds.
This avoids dependence on a browser heartbeat timer, but cannot restore a
suspended video source or frozen browser process.

## Colors and Latency

AmbiPlex adds no lossy encoder after browser capture, and allows only one image
to await acknowledgment rather than accumulating a queue. Remote Play itself
remains compressed. The displayed timings measure **local PC transport and LED
processing**, not console-to-WLED latency.

Smoothing deliberately delays transitions. WLED realtime gamma is shared across
Plex and console sources: note the previous setting, change one thing at a time
and compare other sources before keeping a calibration change.

Use AmbiPlex only on a trusted network. Keep Microsoft credentials, access tokens,
registration/client exports and personal screenshots outside the repository.
