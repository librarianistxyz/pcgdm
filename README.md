# pcGDM — God Mode Automation Suite for Linux & MacBooks

A hardware-tailored, zero-dependency background engine and automation toolkit designed for **Linux PCs and laptops** (Ubuntu, Xubuntu, Debian, Fedora, Arch, ThinkPads, Dells) with specialized optimizations for **Intel/Apple hardware (e.g. 2012 MacBook Pro / Ivy Bridge / Apple SMC)**.

All daemons are built with **double persistence** via `systemd` user/system services and desktop session autostart so they **survive every reboot automatically**.

---

## Linux PC & Hardware Compatibility Matrix

The suite is engineered to run on standard Linux installations as well as Apple hardware running Linux:

| Engine | Universal Linux Compatibility | Supported Platforms | Hardware Drivers Used |
| :--- | :---: | :--- | :--- |
| **`auto_janitor.py`** | **100% Universal** | Any Linux PC, laptop, or server (Ubuntu, Debian, Fedora, Arch, etc.) | Linux Kernel `inotify` subsystem (`libc.so.6`) |
| **`focus_freezer.py`** | **100% Universal** | Any Linux desktop (X11 / XFCE / GNOME / KDE) | Kernel POSIX signals (`SIGSTOP`/`SIGCONT`), `xprop`, `pactl` |
| **`warp_ram.py`** | **100% Universal** | Any Linux PC, laptop, or server | Linux Kernel shared memory `tmpfs` (`/dev/shm`), `rsync` |
| **`hyper_grab.py`** | **100% Universal** | Any Linux desktop (X11 / XFCE / GNOME / KDE) | X11 clipboard (`xclip`), `yt-dlp`, `rofi`/`zenity` |
| **`hive_nexus.py`** | **100% Universal** | Any Linux PC on Wi-Fi / Local Area Network | Google Cast / DIAL REST API, KDE Connect, mDNS Avahi |
| **`airdrop_zero.py`** | **100% Universal** | Any Linux PC on Wi-Fi / Local Area Network | Standard Python 3 sockets & multi-threaded HTTP server |
| **`mac_hud.py`** | **Broad Laptop Support** | Apple MacBooks, ThinkPads, Dells, ASUS, System76 | Linux sysfs LED subsystem (`/sys/class/leds/*kbd_backlight*`) |
| **`mac_visualizer.py`** | **Broad Laptop Support** | Apple MacBooks & backlit Linux laptops | PipeWire/PulseAudio sink monitor + sysfs LEDs |
| **`adjust_kbd_light.py`** | **Broad Laptop Support** | Apple MacBooks & backlit Linux laptops | Apple SMC F5/F6 key listener + sysfs LEDs |
| **`cryo_ram_boost.py`** | **Universal CPU & RAM / Hardware Adaptive Cooling** | Any Intel or AMD Linux PC; custom fan curve for Apple SMC & ThinkPad | Intel P-State / AMD cpupreq, `/proc/sys/vm/`, Apple SMC |
| **`cctv_grid.py`** | **100% Universal (X11)** | Any Linux X11 desktop (XFCE / `xfwm4`) | `wmctrl`, `xdotool`, `xprop`, `fcntl` lock |
| **`ocr_grab.py`** | **100% Universal (X11)** | Any Linux X11 desktop | `xfce4-screenshooter`, Pillow, offline `tesseract`, `xclip` |
| **`bio_unlock.py`** | **100% Universal + Android** | Linux PC (`systemd` + LightDM/XFCE) + Galaxy S9+ APK | TCP `29422`, UDP `29423`, Bluetooth RFCOMM `22`, `pam_exec`, `HMAC-SHA256` |
| **`mac_call.py`** | **100% Universal (Bluetooth)** | Any Linux PC paired with Android/iOS via BlueZ HFP | `bluetoothctl`, BlueZ HFP, `zenity`/`rofi` |
| **`tele_key.py`** | **100% Universal** | Any Linux PC with USB key + Telegram Bot API | `lsusb`, Telegram Bot API, TTS |

---

## The Active God Mode Engines

### 1. `hive_nexus.py` — Local Mesh Device Coordinator & IoT Whisperer
* **Smart TV Integration (TCL / Google Cast / DIAL Protocol)**:
  - Discovers and monitors your Smart TV (`ISMART` at `10.1.0.144`).
  - Reads live telemetry: Online status, uptime, Cast build revision, SSDP UDN without extra libraries.
* **Android / Galaxy S9+ Bridge (KDE Connect)**:
  - **Ring Phone**: Locate your phone in the room instantly with `./godmode.sh ring`.
  - **Clipboard Push**: Push your PC clipboard to your phone with `./godmode.sh phone-clip`.
  - **Terminal SMS**: Send SMS text messages through your phone straight from the terminal with `./godmode.sh sms <number> <message>`.
  - **Share File / URL**: Push files directly to your phone with `./godmode.sh phone-share <path>`.
* **Autonomous LAN Radar**:
  - Sweeps the local Wi-Fi every 90 seconds using mDNS / Avahi.
  - Logs device arrivals/departures and displays desktop notifications when new devices join your network.

### 2. `hyper_grab.py` — Autonomous Clip-to-Action Watcher
* **Zero-Friction Media Downloader**: Watches the X11 clipboard in real time (<0.1s latency, 0% CPU).
  - Copy any YouTube, TikTok, Twitter/X, Instagram, Vimeo, or Reddit URL → brings up an instant action overlay (`1080p Video` / `MP3 Audio` / `Ignore`).
  - Downloads in the background via `yt-dlp` into `~/Downloads/`.
  - **Auto-Janitor** catches the finished download and automatically organizes it into `Videos/` or `Audio/`.
  - Your physical keyboard backlight flashes twice when the download is complete!
* **Auto-JSON Beautifier**: When unformatted, messy single-line JSON is copied, Hyper-Grab instantly formats and indents it directly on your clipboard.

### 3. `warp_ram.py` — In-Memory Build Accelerator & Auto-Scratchpad
* **Zero-Sudo, Zero-Wear Architecture**: Mounts directly into the Linux kernel's high-speed shared memory (`/dev/shm`) and symlinks seamlessly to `~/ramdisk`.
* **Fully Automated**:
  - **Flutter / Dart Automation**: `PUB_CACHE` is routed directly to `~/ramdisk/.pub-cache` so packages and builds resolve at memory speed.
  - **Browser Cache Automation**: Google Chrome's disk cache is symlinked straight into `~/ramdisk/chrome_cache` to eliminate SSD wear and accelerate page loads.
  - **Archive Automation (`ram-extract`)**: Run `ram-extract file.tar.gz` or `.zip` anywhere to auto-extract into RAM in seconds.
  - **One-Key Jump (`cdr`)**: Fast jump to your RAM scratchpad in the terminal.
* **Continuous Auto-Sync**: Automatically mirrors all files to persistent SSD backing (`~/.local/share/pcGDM/ramdisk_backing`) every 60 seconds and on clean system shutdown. Restores the image into RAM automatically on boot!

### 4. `auto_janitor.py` — Broad User-Wide Real-Time File Sorter
* **Universal Linux Core**: Hooks into the Linux kernel `inotify` C API (`libc.so.6`) via Python `ctypes` (0% polling overhead). Runs on any distribution.
* **What it does**: Watches 35+ user folders (including `~/Downloads`, `~/Desktop`, `~/Documents`, `~/Pictures`, `~/Videos`, `~/Music`, `~/Public`, and `$HOME`) and routes newly downloaded or moved files the instant they finish writing:
  * `.pdf`, `.epub` → `PDFs/`
  * `.png`, `.jpg`, `.webp`, `.svg` → `Images/`
  * `.zip`, `.tar.gz`, `.deb`, `.iso`, `.AppImage` → `Archives/`
  * `.sh`, `.py`, `.js`, `.json`, `.yaml`, `.html` → `Scripts_Code/`
  * `.docx`, `.csv`, `.xlsx`, `.txt` → `Documents/`
  * `.mp4`, `.mkv` → `Video/`
  * `.mp3`, `.flac`, `.wav` → `Audio/`
* **Protections**: Ignores temporary browser downloads (`.crdownload`, `.part`, `.tmp`), preserves `.desktop` launchers, never overwrites existing files (appends counter), and leaves Git repositories, project directories, and SDKs completely untouched.
* **Notification**: Triggers native desktop notification and blinks the physical keyboard backlight.

### 5. `focus_freezer.py` — Zero-CPU Background Browser Freezer
* **Universal Linux Core**: Event-driven X11 window focus monitor via `xprop` and kernel signal suspension (`SIGSTOP` / `SIGCONT`).
* **What it does**: On laptops and multi-tab workflows, background browsers (Chromium, Chrome, Brave, Firefox, Edge, AdsPower) easily consume 40–70% CPU and cause fan noise.
  * When your browser is unfocused for >18 seconds and **not playing audio**, it suspends child tab renderers via `SIGSTOP`, dropping their CPU usage to **0.0%**.
  * The millisecond you click or Alt-Tab back, it sends `SIGCONT` (<10ms wake-up).
  * Automatically deprioritizes background file indexers (`localsearch-3`, `tracker`) to idle CPU priority (`nice 19`).
* **Audio Guard**: Automatically inspects PulseAudio/PipeWire sink inputs via `pactl` so YouTube, Spotify, or media tabs in the background are **never** frozen while playing audio.

### 6. `mac_hud.py` — Hardware Keyboard Pulse & Ambient HUD
* **Hardware Interface**: Uses standard Linux sysfs LED control (`/sys/class/leds/*kbd_backlight*`). On MacBooks it talks to `smc::kbd_backlight`; on ThinkPads to `tpacpi::kbd_backlight`; on other PCs to generic keyboard LEDs.
* **What it does**: Turns your physical backlit keyboard into a physical notification and telemetry engine:
  * **`flash`**: Rapid double-flash to acknowledge task completion (e.g. download sorted, file received).
  * **`breathe`**: Smooth sine-wave cosine breathing pulse.
  * **`alert`**: Strobe pattern for urgent alerts.
  * **`hud` daemon**: Background ambient monitor that triggers a slow breathing pulse when CPU temperature hits **82°C+** and flashes an alert when battery drops below **15%**.

### 7. `airdrop_zero.py` — Peer-to-Peer Local Network File Dropper
* **Universal Linux Core**: Lightweight Python multi-threaded HTTP server on port `7777`. Zero third-party dependencies.
* **What it does**: Wirelessly drop files between your phone (iOS / Android) and your Linux PC on the same Wi-Fi without cloud accounts, apps, or cables.
  * Open `http://<pc-ip>:7777` in your phone browser (or run `./godmode.sh drop` to view the terminal QR code).
  * **Upload (Phone → PC)**: Select photos/documents on your phone and tap Send. Files land in `~/Downloads`, Auto-Janitor sorts them instantly, and the keyboard backlight blinks twice.
  * **Download (PC → Phone)**: Tap any file under "Files on MacBook / PC" to download it straight to your phone.

### 8. `cryo_ram_boost.py` — Thermal Cryo Fan Curve & Memory Subsystem Engine
* **Universal CPU & Memory / Adaptive Cooling**:
  * **Power Governors (Universal)**: Manages Intel P-State and CPU scaling governors (`powersave` vs `performance`) and turbo controls across all Linux kernels.
  * **RAM Reclaimer (Universal)**: Directly controls `/proc/sys/vm/drop_caches` and `/proc/sys/vm/compact_memory` to reclaim gigabytes of bloated buffer/pagecache and compact physical RAM.
  * **Smart Power Profiles**:
    * **On Battery (`AUTO-STEALTH`)**: Disables Intel turbo voltage spikes and sets `powersave` governor to extend battery life.
    * **Plugged In (`AUTO-TURBO`)**: Unlocks maximum Turbo Boost with `performance` governor.
  * **Cooling Curves**: Integrates with Apple SMC hardware registers (`applesmc.768`) up to 6200 RPM, with fallback to standard Linux `hwmon` thermal zones.

### 9. `cctv_grid.py` — Live Workspace CCTV Grid & Gesture Switcher
* **Multi-Workspace Command Center**: Gathers all open windows across every XFCE workspace onto your current screen in a live, interactive CCTV grid, saving a snapshot of original workspaces and geometries.
* **Controls**:
  * **`Super + G` / 3-finger swipe up (`toggle`)**: Toggle CCTV grid ON, or restore every window back to its original workspace and size.
  * **`Super + Z` / 3-finger swipe down (`zoom`)**: Maximize the focused tile, or snap it back into the grid.
  * **3-finger swipe left / right (`ws-prev` / `ws-next`)**: Wrap-around workspace switching via `wmctrl`.

### 10. `ocr_grab.py` — Offline Screen-to-Text OCR Grab
* **Drag-to-Copy Anything (`Super + O`)**: Select any region on screen (video frame, PDF, image, error dialog) with `xfce4-screenshooter -r`.
* **Fast Local Recognition**: Upscales small selections (`<600×250`), boosts contrast via Pillow, runs offline `tesseract` (`OMP_THREAD_LIMIT=1`), and copies the text to both X11 `clipboard` and `primary` selections.

### 11. `bio_unlock.py` + `pcgdm-bio-unlock.apk` — Offline S9+ Rear-Fingerprint PC Unlocker
* **Zero-Internet Challenge-Response**: Galaxy S9+ Android app (`bio_unlock_app/`) prompts the rear fingerprint sensor (`BiometricPrompt` / `FingerprintManager`), connects over **Bluetooth RFCOMM (ch 22)**, **USB (`adb reverse`)**, or **LAN/Hotspot TCP (`29422`) + UDP discovery (`29423`)**, and signs a random nonce with **HMAC-SHA256**.
* **Full Boot + Lockscreen Support**: Installed via `sudo ./install_root_biounlock.sh` as root `pcgdm-biounlock.service` with a `pam_exec` hook in `/etc/pam.d/lightdm` (for cold-boot LightDM login) and direct `xfce4-screensaver-command -d` unlock (`Super + L`).

### 12. `mac_visualizer.py` & `adjust_kbd_light.py` — Keyboard Audio Visualizer & Backlight Daemon
* Captures speaker playback audio (never microphone) to pulse the MacBook keyboard backlight to music beats (`music`) or keystrokes (`typing`), while preserving manual F5/F6 brightness control.

### 13. `mac_call.py` & `tele_key.py` — Bluetooth Call Bridge & USB Telegram Remote
* **`mac_call.py`**: Detects incoming Bluetooth phone calls, flashes keyboard lighting, and lets you answer/hang up from desktop hotkeys (`Super + C` / `Super + Shift + C`).
* **`tele_key.py`**: Hardware-key-gated Telegram bot bridge for remote telemetry, directory browsing, voice TTS, and media capture.

---

> See **[FUNCTIONS_DOCS.md](file:///home/librarianist/pcGDM/FUNCTIONS_DOCS.md)** for the complete function-by-function API reference across all files.

---

## Directory Overview

```text
/home/librarianist/pcGDM/
├── godmode.sh                  # Master CLI controller to manage and monitor core engines
├── cctv_grid.py                # Live multi-workspace CCTV grid, zoom & workspace switcher
├── ocr_grab.py                 # Offline screen-region Tesseract OCR to clipboard (Super+O)
├── bio_unlock.py               # Offline BT/TCP/UDP HMAC fingerprint unlocker (LightDM + XFCE)
├── install_root_biounlock.sh   # Installs root pcgdm-biounlock.service & LightDM PAM hook
├── bio_unlock_app/             # Android source & resources for PC Bio-Unlock
├── pcgdm-bio-unlock.apk        # Signed APK for Galaxy S9+ rear-fingerprint unlock
├── mac_visualizer.py           # Real-time audio beat & typing keyboard backlight visualizer
├── adjust_kbd_light.py         # Manual Apple SMC keyboard backlight controller & daemon
├── mac_call.py                 # Hands-free Bluetooth phone call bridge
├── tele_key.py                 # USB hardware key Telegram remote bridge
├── hive_nexus.py               # Local mesh IoT & device coordinator (Universal Linux)
├── hyper_grab.py               # Autonomous clip-to-action downloader (Universal Linux)
├── warp_ram.py                 # In-memory build scratchpad & auto-sync (Universal Linux)
├── auto_janitor.py             # Real-time inotify file organizer (Universal Linux)
├── janitorctl.sh               # Service controller for Auto-Janitor
├── focus_freezer.py            # Background browser tab zero-CPU freezer (Universal Linux)
├── mac_hud.py                  # Hardware keyboard backlight pulse & HUD (Linux sysfs LEDs)
├── airdrop_zero.py             # Micro-web peer-to-peer file dropper (Universal Linux)
├── cryo_ram_boost.py           # Power profiles, fan curves & RAM subsystem engine
├── FUNCTIONS_DOCS.md           # Full function-by-function API & symbol reference
├── .gitignore                  # Git ignore file for logs, pycache, and temporary state
└── README.md                   # Documentation, compatibility matrix, and setup guide
```

---

## Quick Setup & Installation

### 1. One-Click Enable All Boot Daemons
Run the master installer on your Linux PC:

```bash
cd /home/librarianist/pcGDM
./godmode.sh install
```

This single command sets up:
1. `pcgdm-janitor.service` (`systemd --user`)
2. `pcgdm-freezer.service` (`systemd --user`)
3. `pcgdm-hud.service` (`systemd --user`)
4. `pcgdm-airdrop.service` (`systemd --user`)
5. `pcgdm-warpram.service` (`systemd --user`)
6. `pcgdm-hypergrab.service` (`systemd --user`)
7. `pcgdm-hive.service` (`systemd --user`)
8. `pcgdm-telekey.service` (`systemd --user`)
9. `pcgdm-cryo.service` (root `systemd`)
10. Passwordless sudoers rule for CPU/thermal execution.

Additional standalone services installed in this workspace:
* `pcgdm-cctv.service` (`systemd --user`) — registers `Super+G` & `Super+Z` for `cctv_grid.py`
* `pcgdm-ocr.service` (`systemd --user`) — registers `Super+O` for `ocr_grab.py`
* `pcgdm-biounlock.service` (root `systemd`) — installed via `sudo ./install_root_biounlock.sh`
* `pcgdm-visualizer.service`, `pcgdm-kbdbacklight.service`, `pcgdm-callbridge.service`, `pcgdm-kdeconnect.service` (`systemd --user`)

### 2. Verify Running Services
Check the live status of all hardware telemetry and background services:

```bash
./godmode.sh status
```

---

## Everyday Commands

| Command | Action |
| :--- | :--- |
| `./godmode.sh status` | Show live CPU temp, fan RPM, battery draw, RAM, frozen tabs, TV and phone status |
| `./godmode.sh ring` | Find your phone by ringing your Galaxy S9+ from your laptop terminal |
| `./godmode.sh phone-clip` | Push your laptop's clipboard straight to your phone |
| `./godmode.sh phone-share <f>` | Send any file or URL directly to your Galaxy S9+ |
| `./godmode.sh sms <num> <msg>` | Send an SMS text message from your laptop terminal |
| `./godmode.sh tv` | Show real-time Smart TV (TCL/Cast) status & uptime |
| `./godmode.sh lan-scan` | Scan local airspace for all mDNS/ZeroConf devices |
| `./godmode.sh tele-config <t> <id>` | Configure Telegram Bot Token and Chat ID for USB Hardware Key |
| `./godmode.sh tele-status` | Check whether authorized USB hardware key is plugged in |
| `./godmode.sh warp-sync`| Manually mirror in-memory `~/ramdisk` changes to persistent SSD right now |
| `./godmode.sh purge` | Instantly flush Linux pagecache/dentries and reclaim RAM |
| `./godmode.sh sweep` | Manually run a full file sort across all 35 user folders right now |
| `./godmode.sh drop` | Display the AirDrop-Zero URL / QR code for your phone |
| `./godmode.sh wake` | Manually wake all frozen browser tabs immediately |
| `./godmode.sh flash` | Blink physical keyboard backlight twice |
| `./godmode.sh breathe` | Trigger a smooth ambient keyboard breathing pulse |
| `./godmode.sh alert` | Trigger an urgent strobe sequence on keyboard LEDs |
| `./godmode.sh turbo` | Force full Turbo CPU performance mode |
| `./godmode.sh stealth` | Force low-power cap for extended battery and lower temperatures |
| `./godmode.sh cryo` | Force maximum cooling fan blast |
| `cdr` | Instant terminal jump straight into `~/ramdisk` |
| `ram-extract <archive>` | Automatically extract `.tar.gz` or `.zip` directly into pure RAM |
