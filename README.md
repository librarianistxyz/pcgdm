# pcGDM — God Mode Automation Suite

A hardware-tailored, zero-dependency background engine and automation toolkit designed specifically for a **2012 MacBook Pro (Ivy Bridge Intel Core i5 / Apple SMC / Broadcom BCM4331) running Xubuntu Linux**.

All daemons are built with **double persistence** via `systemd` user/system services and XFCE session autostart so they **survive every reboot automatically**.

---

## The 5 Active God Mode Engines

### 1. `auto_janitor.py` — Broad User-Wide Real-Time File Sorter
* **Technology**: Linux kernel `inotify` C API (`libc.so.6`) via Python `ctypes` (0% polling overhead).
* **What it does**: Watches 35+ user folders (including `~/Downloads`, `~/Desktop`, `~/Documents`, `~/Pictures`, `~/Videos`, `~/Music`, `~/Public`, and the top-level `$HOME`) and routes newly downloaded or moved files the instant they finish writing:
  * `.pdf`, `.epub` → `PDFs/`
  * `.png`, `.jpg`, `.webp`, `.svg` → `Images/`
  * `.zip`, `.tar.gz`, `.deb`, `.iso`, `.AppImage` → `Archives/`
  * `.sh`, `.py`, `.js`, `.json`, `.yaml`, `.html` → `Scripts_Code/`
  * `.docx`, `.csv`, `.xlsx`, `.txt` → `Documents/`
  * `.mp4`, `.mkv` → `Video/`
  * `.mp3`, `.flac`, `.wav` → `Audio/`
* **Protections**: Ignores temporary browser downloads (`.crdownload`, `.part`, `.tmp`), preserves `.desktop` launchers, never overwrites existing files (appends counter), and leaves Git repositories, project directories, and SDKs completely untouched.
* **Notification**: Triggers native Xubuntu desktop notification and blinks the physical keyboard backlight.

### 2. `focus_freezer.py` — Zero-CPU Background Browser Freezer
* **Technology**: Event-driven X11 window focus monitor via `xprop` and kernel signal suspension (`SIGSTOP` / `SIGCONT`).
* **What it does**: On an Ivy Bridge dual-core CPU with 8GB RAM, background browsers (Chromium, Chrome, Brave, Firefox, Edge, AdsPower) easily consume 40–70% CPU and cause fan noise.
  * When your browser is unfocused for >18 seconds and **not playing audio**, it suspends the child tab renderers via `SIGSTOP`, dropping their CPU usage to **0.0%**.
  * The millisecond you click or Alt-Tab back, it sends `SIGCONT` (<10ms wake-up).
  * Automatically deprioritizes background file indexers (`localsearch-3`, `tracker`) to idle CPU priority (`nice 19`).
* **Audio Guard**: Automatically inspects PulseAudio/PipeWire sink inputs via `pactl` so YouTube, Spotify, or media tabs in the background are **never** frozen while playing audio.

### 3. `mac_hud.py` — Apple SMC Keyboard Hardware Pulse & Ambient HUD
* **Technology**: Interfaces directly with `/sys/class/leds/smc::kbd_backlight/brightness` (0–255).
* **What it does**: Turns your physical MacBook Pro backlit keyboard into a physical notification and telemetry engine:
  * **`flash`**: Rapid double-flash to acknowledge task completion (e.g. download sorted, file received).
  * **`breathe`**: Smooth sine-wave cosine breathing pulse.
  * **`alert`**: Strobe pattern for urgent alerts.
  * **`hud` daemon**: Background ambient monitor that triggers a slow breathing pulse when CPU temperature hits **82°C+** and flashes an alert when battery drops below **15%**.

### 4. `airdrop_zero.py` — Peer-to-Peer Local Network File Dropper
* **Technology**: Lightweight Python multi-threaded HTTP server on port `7777`.
* **What it does**: Wirelessly drop files between your phone (iOS / Android) and your MacBook Pro on the same Wi-Fi without cloud accounts, apps, or cables.
  * Open `http://<laptop-ip>:7777` in your phone browser (or run `./godmode.sh drop` to view the terminal QR code).
  * **Upload (Phone → MacBook)**: Select photos/documents on your phone and tap Send. Files land in `~/Downloads`, Auto-Janitor sorts them instantly, and the keyboard backlight blinks twice.
  * **Download (MacBook → Phone)**: Tap any file under "Files on MacBook" to download it straight to your phone.

### 5. `cryo_ram_boost.py` — Apple SMC Cryo Fan Curve & RAM Engine
* **Technology**: Apple SMC thermal registers (`applesmc.768`), Intel P-State turbo, and Linux VM kernel memory controls (`/proc/sys/vm/drop_caches`, `compact_memory`).
* **What it does**:
  * **Smart Power Profiles**: Automatically detects MagSafe AC power vs. battery.
    * **On Battery (`AUTO-STEALTH`)**: Disables Intel 3.1 GHz Turbo voltage spikes (`no_turbo=1`) and sets `powersave` governor to keep palmrests cool and extend battery life.
    * **On MagSafe (`AUTO-TURBO`)**: Unlocks full 3.1 GHz Turbo Boost with `performance` governor.
  * **Dynamic Fan Curve**: Smoothly steps Apple SMC exhaust fan minimum floor (`2200` → `3100` → `4200` → `5400` → full **6200 RPM Cryo Blast** if CPU hits 82°C+).
  * **Auto-RAM Reclaimer**: Flushes pagecache and compacts memory when available RAM dips below 900 MiB or cache exceeds 3.5 GB.

---

## Directory Overview

```text
/home/librarianist/pcGDM/
├── godmode.sh           # Master CLI controller to manage and monitor all engines
├── auto_janitor.py      # Real-time inotify file organizer
├── janitorctl.sh        # Service controller for Auto-Janitor
├── focus_freezer.py     # Background browser tab zero-CPU freezer
├── mac_hud.py           # Apple SMC keyboard backlight pulse & HUD
├── airdrop_zero.py      # Micro-web peer-to-peer file dropper
├── cryo_ram_boost.py    # Apple SMC cooling & memory subsystem engine
├── .gitignore           # Git ignore file for logs, pycache, and temporary state
└── README.md            # Documentation and setup guide
```

---

## Quick Setup & Installation

### 1. One-Click Enable All Boot Daemons
Run the master installer to configure all `systemd` unit files and session autostart entries:

```bash
cd /home/librarianist/pcGDM
./godmode.sh install
```

This single command sets up:
1. `pcgdm-janitor.service` (`systemd --user`)
2. `pcgdm-freezer.service` (`systemd --user`)
3. `pcgdm-hud.service` (`systemd --user`)
4. `pcgdm-airdrop.service` (`systemd --user`)
5. `pcgdm-cryo.service` (root `systemd`)
6. Passwordless sudoers rule for hardware SMC/CPU execution.

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
| `./godmode.sh purge` | Instantly flush Linux pagecache/dentries and reclaim RAM |
| `./godmode.sh sweep` | Manually run a full file sort across all 35 user folders right now |
| `./godmode.sh drop` | Display the AirDrop-Zero URL / QR code for your phone |
| `./godmode.sh wake` | Manually wake all frozen browser tabs immediately |
| `./godmode.sh flash` | Blink physical keyboard backlight twice |
| `./godmode.sh breathe` | Trigger a smooth ambient keyboard breathing pulse |
| `./godmode.sh alert` | Trigger an urgent strobe sequence on keyboard LEDs |
| `./godmode.sh turbo` | Force full 3.1 GHz Turbo + 5500 RPM fan floor |
| `./godmode.sh stealth` | Force 2.5 GHz low-power cap for extended battery |
| `./godmode.sh cryo` | Force Apple SMC exhaust fan to 6200 RPM maximum blizzard speed |
