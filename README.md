# AmbiPlex

![AmbiPlex Interface](screenshot1.png)

*Note: The user interface and internal logs of this software are in French.*

An ultra-high-performance, 100% software-based Ambilight system designed to synchronize with the **Plex** video player and drive hardware LED strips (via **WLED / QuinLED ESP32**) on a local network.

## ✨ Features
- **Plex Man-in-the-Middle**: Listens to Plex playback events via Websocket and synchronizes an invisible (headless) `MPV` instance in the background.
- **Asymmetrical Auto-Crop (Anti-Subtitles)**: Mathematically detects black bars (2.35:1 Letterbox) in real time. Analyzes only the top bar to ignore subtitles, ensuring absolute visual stability.
- **Extreme Downscaling (Fallback)**: Uses `libmpv`'s `screenshot_raw` API and `Pillow` to reduce the image size in real time before extraction if the format requires it.
- **Zero CPU Mode (WLED Subtitles)**: Decompresses pre-calculated `.wledsub.lz4` files on the fly, maps them to memory (`numpy.memmap`), and completely bypasses the video player. Drastically reduces CPU consumption.
- **Numpy LED Engine**: Calculates the average colors (RGB) of the image borders in milliseconds using matrix slicing.
- **DDP Protocol (UDP)**: Transmits data to WLED via the *Distributed Display Protocol* at over 20 FPS for zero latency.
- **Modern Web Interface**: Real-time configuration (FastAPI + Vanilla JS Glassmorphism) with an interactive LED simulator.
- **WLED Subtitles Web Encoder**: Built-in web tool to extract WLED metadata from any video file using FFmpeg, avoiding CPU usage during playback.
- **AmbiPlex Rover (Batch Encoder)**: Standalone Windows GUI (`rover.py`) to recursively scan directories, visually highlight missing subtitles, and batch encode multiple movies sequentially with just one click.

## ⚙️ Hardware Requirements
- A Plex server and a local Plex client (e.g., Apple TV, Nvidia Shield, Smart TV).
- A WLED-compatible LED controller (Recommended: **QuinLED Dig-Uno** with Ethernet Hat).
- An addressable LED strip (e.g., **WS2812B** 60 leds/m).

## 🚀 Installation
1. Clone this repository.
2. Create a Python virtual environment (`python -m venv venv`).
3. Install dependencies (`pip install -r requirements.txt`).
4. Download the `libmpv-2.dll` dynamic library and place it at the project root (Windows).
5. Start the server using the **`start.bat`** file.

## 🔧 Usage
1. Open the web interface (default: `http://127.0.0.1:5777`).
2. Enter your Plex credentials (URL and Token) and the name of your Plex client.
3. Enter your WLED controller's IP address.
4. Adjust the number of LEDs for each border (Top, Bottom, Left, Right).
5. Play a movie on Plex: colors will instantly appear in the web simulator and on your wall!

## 🎬 Zero CPU Mode (WLED Subtitles) - *[OPTIONAL]*
By default, AmbiPlex analyzes your video in real-time using `libmpv`. However, for low-power platforms (Raspberry Pi, old PCs) or maximum efficiency, you have the option to pre-generate movie colors to completely eliminate CPU load during playback:
1. Open the Web Encoder from the AmbiPlex Dashboard.
2. Select your movie file and click "Encoder".
3. An ultra-light `.wledsub.lz4` file will be created next to the video.
4. On the next playback, AmbiPlex will automatically switch to Zero CPU mode!

![LED Simulator](screenshot2.png)

## 🛡️ Security & Privacy
No secrets (Plex Token, local IP) are hardcoded in the source code. All sensitive data is saved in a local `config.json` file (ignored by Git).

## 📸 Gallery
![Configuration Detail](screenshot3.png)
![Synchronization Result](screenshot4.png)

---
*Designed by Sébastien Bédard*
