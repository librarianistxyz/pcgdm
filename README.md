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
| **`airdrop_zero.py`** | **100% Universal** | Any Linux PC on Wi-Fi / Local Area Network | Standard Python 3 sockets & multi-threaded HTTP server |
| **`mac_hud.py`** | **Broad Laptop Support** | Apple MacBooks, ThinkPads, Dells, ASUS, System76 | Linux sysfs LED subsystem (`/sys/class/leds/*kbd_backlight*`) |
| **`cryo_ram_boost.py`** | **Universal CPU & RAM / Hardware Adaptive Cooling** | Any Intel or AMD Linux PC; custom fan curve for Apple SMC & ThinkPad | Intel P-State / AMD cpupreq, `/proc/sys/vm/`, Apple SMC |

---

## The 6 Active God Mode Engines

### 1. `warp_ram.py` — In-Memory Build Accelerator & Auto-Scratchpad
* **Zero-Sudo, Zero-Wear Architecture**: Mounts directly into the Linux kernel's high-speed shared memory (`/dev/shm`) and symlinks seamlessly to `~/ramdisk`.
* **Fully Automated**:
  - **Flutter / Dart Automation**: `PUB_CACHE` is routed directly to `~/ramdisk/.pub-cache` so packages and builds resolve at memory speed.
  - **Browser Cache Automation**: Google Chrome's disk cache is symlinked straight into `~/ramdisk/chrome_cache` to eliminate SSD wear and accelerate page loads.
  - **Archive Automation (`ram-extract`)**: Run `ram-extract file.tar.gz` or `.zip` anywhere to auto-extract into RAM in seconds.
  - **One-Key Jump (`cdr`)**: Fast jump to your RAM scratchpad in the terminal.
* **Continuous Auto-Sync**: Automatically mirrors all files to persistent SSD backing (`~/.local/share/pcGDM/ramdisk_backing`) every 60 seconds and on clean system shutdown. Restores the image into RAM automatically on boot!

### 2. `auto_janitor.py` — Broad User-Wide Real-Time File Sorter
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

### 3. `focus_freezer.py` — Zero-CPU Background Browser Freezer
* **Universal Linux Core**: Event-driven X11 window focus monitor via `xprop` and kernel signal suspension (`SIGSTOP` / `SIGCONT`).
* **What it does**: On laptops and multi-tab workflows, background browsers (Chromium, Chrome, Brave, Firefox, Edge, AdsPower) easily consume 40–70% CPU and cause fan noise.
  * When your browser is unfocused for >18 seconds and **not playing audio**, it suspends child tab renderers via `SIGSTOP`, dropping their CPU usage to **0.0%**.
  * The millisecond you click or Alt-Tab back, it sends `SIGCONT` (<10ms wake-up).
  * Automatically deprioritizes background file indexers (`localsearch-3`, `tracker`) to idle CPU priority (`nice 19`).
* **Audio Guard**: Automatically inspects PulseAudio/PipeWire sink inputs via `pactl` so YouTube, Spotify, or media tabs in the background are **never** frozen while playing audio.

### 4. `mac_hud.py` — Hardware Keyboard Pulse & Ambient HUD
* **Hardware Interface**: Uses standard Linux sysfs LED control (`/sys/class/leds/*kbd_backlight*`). On MacBooks it talks to `smc::kbd_backlight`; on ThinkPads to `tpacpi::kbd_backlight`; on other PCs to generic keyboard LEDs.
* **What it does**: Turns your physical backlit keyboard into a physical notification and telemetry engine:
  * **`flash`**: Rapid double-flash to acknowledge task completion (e.g. download sorted, file received).
  * **`breathe`**: Smooth sine-wave cosine breathing pulse.
  * **`alert`**: Strobe pattern for urgent alerts.
  * **`hud` daemon**: Background ambient monitor that triggers a slow breathing pulse when CPU temperature hits **82°C+** and flashes an alert when battery drops below **15%**.

### 5. `airdrop_zero.py` — Peer-to-Peer Local Network File Dropper
* **Universal Linux Core**: Lightweight Python multi-threaded HTTP server on port `7777`. Zero third-party dependencies.
* **What it does**: Wirelessly drop files between your phone (iOS / Android) and your Linux PC on the same Wi-Fi without cloud accounts, apps, or cables.
  * Open `http://<pc-ip>:7777` in your phone browser (or run `./godmode.sh drop` to view the terminal QR code).
  * **Upload (Phone → PC)**: Select photos/documents on your phone and tap Send. Files land in `~/Downloads`, Auto-Janitor sorts them instantly, and the keyboard backlight blinks twice.
  * **Download (PC → Phone)**: Tap any file under "Files on MacBook / PC" to download it straight to your phone.

### 6. `cryo_ram_boost.py` — Thermal Cryo Fan Curve & Memory Subsystem Engine
* **Universal CPU & Memory / Adaptive Cooling**:
  * **Power Governors (Universal)**: Manages Intel P-State and CPU scaling governors (`powersave` vs `performance`) and turbo controls across all Linux kernels.
  * **RAM Reclaimer (Universal)**: Directly controls `/proc/sys/vm/drop_caches` and `/proc/sys/vm/compact_memory` to reclaim gigabytes of bloated buffer/pagecache and compact physical RAM.
  * **Smart Power Profiles**:
    * **On Battery (`AUTO-STEALTH`)**: Disables Intel turbo voltage spikes and sets `powersave` governor to extend battery life.
    * **Plugged In (`AUTO-TURBO`)**: Unlocks maximum Turbo Boost with `performance` governor.
  * **Cooling Curves**: Integrates with Apple SMC hardware registers (`applesmc.768`) up to 6200 RPM, with fallback to standard Linux `hwmon` thermal zones.

---

## Directory Overview

```text
/home/librarianist/pcGDM/
├── godmode.sh           # Master CLI controller to manage and monitor all engines
├── warp_ram.py          # In-memory build scratchpad & auto-sync (Universal Linux)
├── auto_janitor.py      # Real-time inotify file organizer (Universal Linux)
├── janitorctl.sh        # Service controller for Auto-Janitor
├── focus_freezer.py     # Background browser tab zero-CPU freezer (Universal Linux)
├── mac_hud.py           # Hardware keyboard backlight pulse & HUD (Linux sysfs LEDs)
├── airdrop_zero.py      # Micro-web peer-to-peer file dropper (Universal Linux)
├── cryo_ram_boost.py    # Power profiles, fan curves & RAM subsystem engine
├── .gitignore           # Git ignore file for logs, pycache, and temporary state
└── README.md            # Documentation, compatibility matrix, and setup guide
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
6. `pcgdm-cryo.service` (root `systemd`)
7. Passwordless sudoers rule for CPU/thermal execution.

### 2. Verify Running Services
Check the live status of all hardware telemetry and background services:

```bash
./godmode.sh status
```

---

## Everyday Commands

| Command | Action |
| :--- | :--- |
| `./godmode.sh status` | Show live CPU temp, fan RPM, battery draw, RAM, frozen tabs, and systemctl status |
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
