# PlayStation Setup: PS4 / PS5 + Chiaki-ng + AmbiPlex

[Back to AmbiPlex](README.md)

Chiaki-ng supports standard PS4 and PS5 consoles.
This guide uses a local Remote Play connection on the AmbiPlex Windows PC, then
captures its application window in Chrome. Chiaki-ng is an independent,
unofficial Remote Play client, not a Sony product.
[Chiaki-ng project](https://github.com/chiaki-ng/chiaki-ng)

```text
PS4 / PS5 -------- HDMI directly ----------------> TV
    |
    +---- LAN Remote Play ---> Chiaki-ng on PC
                                  |
                                  +---- Chrome / AmbiPlex ----> WLED

Controller ------ directly to console (two-user arrangement below)
```

No HDMI splitter, capture card, public broadcast or preencoded LED track is
needed. Direct HDMI avoids inserting another device in the TV signal path;
it does not guarantee that every console keeps every video mode during Remote
Play. Check the actual TV output on your setup.

## Compatibility and Validation

| Setup | Status |
| --- | --- |
| Ordinary PS4 or PS5 | Supported by Chiaki-ng; follow the standard account setup below. |
| PS4 with Chiaki-ng and Chrome | Live operation confirmed in AmbiPlex testing. A separate console user resolved the local-controller conflict; switching from Firefox to Chrome resolved the reported long-session capture freeze. |
| PS5 with AmbiPlex | Uses the same application-window capture path, but has not been physically validated in this project. |

PS4 LED saturation and near-black rendering are still under calibration. The
working connection is not a claim of calibrated color accuracy, measured
console-to-LED latency or compatibility with every firmware/client combination.
Check the current Chiaki-ng documentation for your console firmware.

## Before You Start

- Install and configure [AmbiPlex](README.md#installation), including WLED.
- Use the same LAN for the PC and console, preferably Ethernet.
- Use **Chrome for the capture**. Edge uses the same direct capture API but was
  not the browser used for the successful physical PS4 test. Firefox's fallback
  capture froze in that test even while Chiaki continued working.
- Download the Windows build from the
  [official Chiaki-ng releases](https://github.com/chiaki-ng/chiaki-ng/releases).
  Do not obtain clients or enter credentials on lookalike download sites.
- Keep the console powered on for the initial setup. Rest-mode wake is optional.
- Do not enable router port forwarding or put the console in a DMZ for this LAN
  workflow. Guest-network/client isolation can prevent local discovery.

## 1. Choose the Console User

There are two different arrangements. Choose before registering Chiaki.

| Arrangement | Console user registered in Chiaki | Controller connection |
| --- | --- | --- |
| Conventional Remote Play | Your gaming user | Controller on the PC; input travels through Remote Play. |
| TV gaming with AmbiPlex | A dedicated second user, for example `AmbiPlex` | Controller directly on the console, using your original gaming user. |

The second arrangement keeps controller input off the PC/network path. It is the
PS4 arrangement tested here. It still requires a working Remote Play video
session; it is not a special view-only mode in Chiaki.

Create or use a second console user and sign it in
to its own PlayStation account through the normal console menus. Register that
account in Chiaki, not your original gaming account. Creating only another
configuration profile inside Chiaki is not the same thing.

Do not change the identity of your existing gaming user or move its saves.
Use the normal PlayStation account setup for that dedicated user.

## 2. Enable Remote Play

Use these English console-menu labels; wording can vary with firmware.

| Console | Enable Remote Play | Obtain the pairing code |
| --- | --- | --- |
| PS4 | `Settings > Remote Play Connection Settings > Enable Remote Play` | `Settings > Remote Play Connection Settings > Add Device` |
| PS5 | `Settings > System > Remote Play > Enable Remote Play` | `Settings > System > Remote Play > Pair Device` (also called `Link Device`) |

Configure Remote Play for the user you will register in Chiaki. For a standard
PS4, also follow Sony's `Settings > Account Management > Activate as Your Primary
PS4 > Activate` instructions for that account; respect the one-primary-PS4 limit.
[Sony's console setup and pairing instructions](https://www.playstation.com/en-gb/support/games/playstation-remote-play-on-pc-and-mac/)

Optional wake from rest mode uses `Stay Connected to the Internet` and
`Enable Turning on PS4/PS5 from Network`, under PS4 `Power Save Settings > Set
Features Available in Rest Mode` or PS5 `System > Power Saving > Features
Available in Rest Mode`. Skip wake testing until a powered-on connection works.
[Sony's rest-mode instructions](https://www.playstation.com/en-gb/support/games/playstation-remote-play-on-pc-and-mac/)

Account enrollment can require Internet/PSN. A local Chiaki stream then travels
over the LAN, not through a public video-streaming service. Follow the normal
PlayStation account and Remote Play requirements for your console.

## 3. Register Chiaki-ng

1. Open Chiaki-ng and select the discovered console. If absent, use
   `Settings > Consoles > Register New` and enter its LAN IP as `Host`.
2. Select the actual console type. For `PSN Account-ID`, use Chiaki's `PSN Login`
   for the account selected above, or its `Public Lookup` if available.
3. Generate a fresh console pairing code and enter it as `Remote Play PIN`.
4. Register, connect and verify the moving game image in Chiaki before opening
   AmbiPlex capture. A console login passcode is different from the pairing PIN.

Account-ID is not the account's email or online nickname. Keep pairing codes,
OAuth redirect URLs/tokens, registration keys and client configuration private.
[Chiaki-ng registration reference](https://github.com/chiaki-ng/chiaki-ng/blob/main/docs/setup/configuration.md)

Leave **Auto-connect off until the controller arrangement is working**. Later,
it can be enabled for a single usual console. For `Action on Disconnect`, use
`Ask` and choose to leave the console on when ending a lighting session; avoid
automatic sleep during TV gaming.
[Chiaki-ng connection settings](https://github.com/chiaki-ng/chiaki-ng/blob/main/docs/setup/configuration.md)

## 4. Keep the Controller on the Console

For the two-user arrangement:

1. Connect Chiaki using the dedicated `AmbiPlex` console user.
2. Turn on the controller paired directly with the console.
3. At user selection, choose your **original gaming user**, not `AmbiPlex`.
4. Leave the dedicated user signed in in the background and launch your game
   from the original user. Confirm Chiaki still displays the moving game image.

Reclaiming the same user with the physical controller disconnected the PS4
Remote Play session during testing. If it happens, verify which account was
registered; disabling controller mappings is not a replacement for separating
the console users. Verify this arrangement on a PS5 before relying on it.

PS5 can show a Remote Play connection banner when another user joins. Supported
firmware offers `Settings > System > Remote Play > Hide Remote Play Connection
Status`. [Sony's notification explanation](https://www.playstation.com/en-gb/support/games/playstation-remote-play-on-pc-and-mac/)

## 5. Capture in AmbiPlex

1. In Chiaki's stream settings, start at **540p or 720p for PS4**, or **720p for
   PS5**, with a 60 fps target where offered. These are lighting test starting
   points, not guarantees of identical color quality. Increase resolution or
   bitrate if compression damages dark colors. Verify the decoded image first.
2. Keep Chiaki open and unminimized, preferably fullscreen. `F11` toggles
   fullscreen in Chiaki-ng. Do not change HDR/HDCP/TV settings just to obtain
   lighting; an HDR desktop/stream needs its own color validation.
   [Chiaki-ng fullscreen control](https://github.com/chiaki-ng/chiaki-ng/blob/main/docs/setup/controlling.md#special-button-mappings-you-need-to-assign-these-yourself)
3. In **Chrome**, open [AmbiPlex PlayStation capture](http://localhost:5777/remote?source=ps4).
   The `source=ps4` URL is retained for compatibility and selects the window
   profile for **either PS4 or PS5**; it does not choose the console in Chiaki.
4. Select **PlayStation Remote Play**, click **Choisir la source**, choose
   **Fenêtre**, then the actual **Chiaki stream window**, without audio.
5. Start at **60 images/s**. Verify the preview, reported capture surface and
   source dimensions. Window dimensions are not the stream resolution.
6. Remove visible title bars or borders with the crop margins. `Centrage 16:9`
   alone does not recognize an off-center game image. Confirm all screen edges.
7. Test motion, a dark scene and a stable colored scene for at least 15 minutes
   under your normal window/background conditions. Then check another Plex video
   before keeping any shared LED calibration changes.

Sampling stays at 160x90 sRGB RGBA8 with the existing LED engine. No PlayStation
credentials go into AmbiPlex. Capture does not save console profiles or overwrite
Plex/WLED settings. Its timings measure local transport/processing, not total
console-to-lighting latency.

Click **Arrêter** or **Retour à Plex** before changing sources. That releases
LED control without explicitly disconnecting Chiaki or sleeping the console.
Reloading the page ends sharing and requires selecting the window again.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Controller reconnect disconnects Chiaki | Register the dedicated console user; assign the physical controller to the original gaming user. |
| Chiaki moves but AmbiPlex freezes | Stop the old capture, close its page and retry in Chrome. Keep the source unminimized. A live socket does not prove fresh video frames. |
| Inactive for 15 seconds | Restart through the existing service manager after Python updates, reload the page, and select the source again. Keepalives cannot rescue a frozen/discarded page or suspended capture source. |
| Another capture is already active | Stop/close the previous capture; wait for its connection to release. Do not launch a second AmbiPlex server. |
| Console not discovered | Check same-LAN access and router isolation; try manual registration by IP. Do not expose ports to the Internet. |
| Black preview | Verify Chiaki first, then select its stream window again. Capture failure is not a reason to disable HDCP automatically. |
| Pale colors / gray blacks | Compare Chiaki, AmbiPlex preview and LEDs separately; check framing, gamma and black levels below. |

### Color Calibration Is Separate

AmbiPlex currently sends RGB values without a software gamma transform. WLED's
`Disable realtime gamma correction` setting determines whether WLED skips its
own correction for live input. If it is checked, neither layer applies gamma
in this pipeline. [WLED realtime output implementation](https://github.com/wled/WLED/blob/v16.0.0/wled00/FX_fcn.cpp#L1586)

For an A/B test, note the original setting, then uncheck it under WLED
`Config > Sync Interfaces > Realtime`, keeping other settings unchanged.
It can make dark colors substantially dimmer, especially with reduced per-side
brightness. This is a **shared WLED setting**, affecting Plex/Xbox too; compare
those sources and restore the setting if the result is worse. Do not compensate
with arbitrary saturation or black clipping before locating the discrepancy.
The current PS4 gamma test has no confirmed outcome yet.

## Keep Credentials Private

Do not commit personal IDs, PINs, client exports, router configuration or screenshots
of registration dialogs. This repository contains no ready-to-use console credentials.
