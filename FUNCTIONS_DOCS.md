# pcGDM Workspace — Complete Function & API Reference

Comprehensive reference for every module, class, function, and shell helper in `/home/librarianist/pcGDM`.

---

## 1. Desktop Workspace & Visual Capture

### [cctv_grid.py](file:///home/librarianist/pcGDM/cctv_grid.py)
*Arranges all open windows across all XFCE workspaces into a live, interactive CCTV grid on the active screen with instant zoom/unzoom and full workspace restore.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L34](file:///home/librarianist/pcGDM/cctv_grid.py#L34) | Logs timestamped messages to stdout and `~/.local/share/pcGDM/cctv_grid.log`. |
| `run(cmd)` | [L45](file:///home/librarianist/pcGDM/cctv_grid.py#L45) | Executes a subprocess command capturing stdout/stderr as text. |
| `get_screen_size()` | [L49](file:///home/librarianist/pcGDM/cctv_grid.py#L49) | Returns `(width, height)` of the X11 display via `xdotool getdisplaygeometry`. |
| `get_active_workspace()` | [L54](file:///home/librarianist/pcGDM/cctv_grid.py#L54) | Returns the 0-based index of the currently active XFCE workspace from `wmctrl -d`. |
| `get_wm_state(win_id)` | [L62](file:///home/librarianist/pcGDM/cctv_grid.py#L62) | Reads `_NET_WM_STATE` via `xprop` for maximized/fullscreen flags. |
| `list_real_windows()` | [L71](file:///home/librarianist/pcGDM/cctv_grid.py#L71) | Lists all normal user windows across all workspaces (excluding panels/desktop/dock), sorted by workspace and ID. |
| `existing_win_ids()` | [L97](file:///home/librarianist/pcGDM/cctv_grid.py#L97) | Returns the set of currently live X11 window IDs from `wmctrl -l`. |
| `tile_windows(win_ids)` | [L106](file:///home/librarianist/pcGDM/cctv_grid.py#L106) | Two-pass silent tiler: moves windows to active workspace, clears maximized/fullscreen states, waits for `xfwm4`, and places each window in a grid cell. |
| `enter_cctv()` | [L142](file:///home/librarianist/pcGDM/cctv_grid.py#L142) | Snapshots current window workspaces/geometries to `cctv_snapshot.json` and activates the CCTV grid. |
| `exit_cctv()` | [L158](file:///home/librarianist/pcGDM/cctv_grid.py#L158) | Restores every window to its original workspace, geometry, and maximized/fullscreen state, then switches back to `origin_ws`. |
| `is_debounced()` | [L194](file:///home/librarianist/pcGDM/cctv_grid.py#L194) | Enforces a `0.4s` wall-clock cooldown (`time.time()`) via `cctv_last_toggle` to prevent double-trigger glitches. |
| `toggle_cctv()` | [L207](file:///home/librarianist/pcGDM/cctv_grid.py#L207) | Toggles between `enter_cctv()` and `exit_cctv()` based on snapshot presence. |
| `zoom_active()` | [L216](file:///home/librarianist/pcGDM/cctv_grid.py#L216) | Maximizes the currently focused window, or unmaximizes and re-tiles the CCTV grid if already maximized. |
| `switch_workspace(delta)` | [L236](file:///home/librarianist/pcGDM/cctv_grid.py#L236) | Switches XFCE workspace by `delta` with wrap-around via `wmctrl -s`. |
| `ensure_shortcuts()` | [L247](file:///home/librarianist/pcGDM/cctv_grid.py#L247) | Clears stale state files and registers `<Super>g` (`toggle`) and `<Super>z` (`zoom`) in `xfce4-keyboard-shortcuts`. |
| `main()` | [L256](file:///home/librarianist/pcGDM/cctv_grid.py#L256) | CLI entrypoint (`toggle`, `start`, `stop`, `tile`, `zoom`, `init`, `ws-prev`, `ws-next`) guarded by `fcntl.flock`. |

---

### [ocr_grab.py](file:///home/librarianist/pcGDM/ocr_grab.py)
*Drag-selects any screen region, enhances contrast, runs offline Tesseract OCR, and copies extracted text to clipboard.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L25](file:///home/librarianist/pcGDM/ocr_grab.py#L25) | Writes timestamped logs to stdout and `~/.local/share/pcGDM/ocr_grab.log`. |
| `notify(title, body)` | [L36](file:///home/librarianist/pcGDM/ocr_grab.py#L36) | Sends a 2.5s desktop notification via `notify-send`. |
| `preprocess_image(src, dst)` | [L41](file:///home/librarianist/pcGDM/ocr_grab.py#L41) | Converts image to grayscale, upscales small regions (`<600x250`) 2× with Lanczos, and boosts contrast (`1.5x`). |
| `copy_to_clipboard(text)` | [L51](file:///home/librarianist/pcGDM/ocr_grab.py#L51) | Copies OCR text into both X11 `clipboard` and `primary` selections via `xclip`. |
| `grab_ocr(lang)` | [L62](file:///home/librarianist/pcGDM/ocr_grab.py#L62) | Launches `xfce4-screenshooter -r`, preprocesses image, runs `tesseract` (`OMP_THREAD_LIMIT=1`, 8s timeout), copies result, and notifies. |
| `ensure_shortcut()` | [L118](file:///home/librarianist/pcGDM/ocr_grab.py#L118) | Registers `<Super>o` → `ocr_grab.py grab` in `xfce4-keyboard-shortcuts`. |
| `main()` | [L132](file:///home/librarianist/pcGDM/ocr_grab.py#L132) | CLI entrypoint (`grab`, `init`, `--lang`). |

---

### [hyper_grab.py](file:///home/librarianist/pcGDM/hyper_grab.py)
*Event-driven X11 clipboard watcher for media URLs (`yt-dlp` MP4/MP3 download) and automatic JSON beautification.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L39](file:///home/librarianist/pcGDM/hyper_grab.py#L39) | Logs timestamped events to stdout and `hyper_grab.log`. |
| `load_handled_urls()` | [L50](file:///home/librarianist/pcGDM/hyper_grab.py#L50) | Loads previously processed URLs from `hyper_grab_handled.txt`. |
| `mark_url_handled(url)` | [L60](file:///home/librarianist/pcGDM/hyper_grab.py#L60) | Appends a handled URL to `hyper_grab_handled.txt`. |
| `notify(title, msg, timeout_ms)` | [L69](file:///home/librarianist/pcGDM/hyper_grab.py#L69) | Sends a desktop notification via `notify-send`. |
| `flash_keyboard()` | [L79](file:///home/librarianist/pcGDM/hyper_grab.py#L79) | Triggers `mac_hud.py flash` on download completion. |
| `get_clipboard()` | [L88](file:///home/librarianist/pcGDM/hyper_grab.py#L88) | Reads current X11 clipboard text via `xclip`. |
| `set_clipboard(text)` | [L96](file:///home/librarianist/pcGDM/hyper_grab.py#L96) | Writes text to X11 clipboard via `xclip`. |
| `is_media_url(text)` | [L104](file:///home/librarianist/pcGDM/hyper_grab.py#L104) | Checks if text matches supported video/audio domains. |
| `download_media_async(url, mode)` | [L111](file:///home/librarianist/pcGDM/hyper_grab.py#L111) | Runs `yt-dlp` in a background thread for 720p MP4 or MP3 download into `~/Downloads/`. |
| `prompt_user_action(url)` | [L158](file:///home/librarianist/pcGDM/hyper_grab.py#L158) | Shows a `rofi` or `zenity` action dialog for copied media URLs. |
| `handle_clipboard_content(text)` | [L197](file:///home/librarianist/pcGDM/hyper_grab.py#L197) | Routes newly copied clipboard text to media download or JSON formatting. |
| `run_daemon()` | [L221](file:///home/librarianist/pcGDM/hyper_grab.py#L221) | Monitors X11 clipboard changes continuously while ignoring pre-existing startup content. |
| `main()` | [L287](file:///home/librarianist/pcGDM/hyper_grab.py#L287) | CLI entrypoint (`daemon`). |

---

## 2. Offline Biometric Unlock (PC Daemon + Android APK)

### [bio_unlock.py](file:///home/librarianist/pcGDM/bio_unlock.py)
*Offline PC unlocker listening on TCP `29422`, UDP discovery `29423`, and Bluetooth RFCOMM `22` with HMAC-SHA256 challenge-response (supports LightDM PAM + `xfce4-screensaver`).*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L39](file:///home/librarianist/pcGDM/bio_unlock.py#L39) | Logs timestamped events to stdout and `bio_unlock.log`. |
| `load_or_create_key()` | [L50](file:///home/librarianist/pcGDM/bio_unlock.py#L50) | Loads or generates the 32-byte shared secret at `bio_unlock.key` (`0600`). |
| `write_pam_token()` | [L63](file:///home/librarianist/pcGDM/bio_unlock.py#L63) | When running as root, writes a single-use 15s PAM verification token at `/run/pcgdm-biounlock/verified`. |
| `unlock_session()` | [L75](file:///home/librarianist/pcGDM/bio_unlock.py#L75) | Writes PAM token, runs `loginctl unlock-sessions`, unlocks `xfce4-screensaver` / `light-locker`, and sends a desktop notification. |
| `handle_client(conn, peer, secret)` | [L106](file:///home/librarianist/pcGDM/bio_unlock.py#L106) | Sends `CHALLENGE:<nonce>`, reads `AUTH:<hmac>`, verifies with `hmac.compare_digest`, and calls `unlock_session()`. |
| `tcp_listener(secret, stop_evt)` | [L143](file:///home/librarianist/pcGDM/bio_unlock.py#L143) | Accepts TCP connections on `0.0.0.0:29422` (USB `adb reverse`, Wi-Fi, Hotspot, Tailscale). |
| `udp_discovery_listener(stop_evt)` | [L161](file:///home/librarianist/pcGDM/bio_unlock.py#L161) | Responds `PCGDM_HERE:29422` to `PCGDM_DISCOVER` broadcasts on UDP `29423`. |
| `bt_listener(secret, stop_evt)` | [L180](file:///home/librarianist/pcGDM/bio_unlock.py#L180) | Accepts Bluetooth RFCOMM connections on channel `22`. |
| `ensure_bluetooth_ready()` | [L204](file:///home/librarianist/pcGDM/bio_unlock.py#L204) | Powers on the Bluetooth controller and trusts the paired Galaxy S9+ (`88:BD:45:3D:7F:44`). |
| `run_daemon()` | [L212](file:///home/librarianist/pcGDM/bio_unlock.py#L212) | Starts TCP, UDP discovery, and Bluetooth listener threads with graceful `SIGTERM`/`SIGINT` shutdown. |
| `main()` | [L238](file:///home/librarianist/pcGDM/bio_unlock.py#L238) | CLI entrypoint (`daemon`, `key`, `unlock-test`). |

### [MainActivity.java](file:///home/librarianist/pcGDM/bio_unlock_app/src/com/pcgdm/biounlock/MainActivity.java)
*Android client (`pcgdm-bio-unlock.apk`) for Galaxy S9+ rear fingerprint authentication.*

| Method | Description |
| :--- | :--- |
| `onCreate(Bundle)` | Builds dark UI with custom logo, target info, status view, and starts unlock flow immediately. |
| `getTargetMac()` / `getTargetIp()` | Reads saved PC Bluetooth MAC and LAN IP from `SharedPreferences`. |
| `showDevicePicker()` | Lists bonded Bluetooth devices to select/save the target PC MAC. |
| `startUnlockFlow()` | Resets state and runs `connectAndReadChallenge()` in parallel with `promptFingerprint()`. |
| `discoverLanIp()` | Broadcasts `PCGDM_DISCOVER` on UDP `29423` to auto-discover the PC on LAN/Hotspot. |
| `tryTcpConnect(host, timeoutMs, label)` | Connects over TCP `29422` and reads the `CHALLENGE:` nonce. |
| `tryBluetoothConnect()` | Connects over Bluetooth RFCOMM channel `22` and reads the `CHALLENGE:` nonce. |
| `connectAndReadChallenge()` | Tries Bluetooth first, then USB (`127.0.0.1`), saved/default LAN IP, and UDP broadcast discovery. |
| `promptFingerprint()` | Triggers Android `BiometricPrompt` (API ≥ 28) or `FingerprintManager` (API 26–27). |
| `onFingerprintVerified()` | Computes `HMAC-SHA256(SECRET_HEX, nonce)`, sends `AUTH:<hmac>`, and displays `PC UNLOCKED!`. |
| `hmacSha256(key, msg)` / `hexToBytes(s)` | Cryptographic HMAC-SHA256 and hex conversion helpers. |

---

## 3. Apple SMC Hardware, Audio & Call Bridges

### [adjust_kbd_light.py](file:///home/librarianist/pcGDM/adjust_kbd_light.py)
*Manual Apple SMC keyboard backlight controller and F5/F6 daemon.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `get_current_setting()` | [L30](file:///home/librarianist/pcGDM/adjust_kbd_light.py#L30) | Reads current keyboard brightness preference/sysfs value. |
| `apply_brightness(val)` | [L52](file:///home/librarianist/pcGDM/adjust_kbd_light.py#L52) | Clamps and applies keyboard backlight brightness and saves user preference. |
| `run_daemon()` | [L81](file:///home/librarianist/pcGDM/adjust_kbd_light.py#L81) | Hardware keyboard illumination key listener service. |
| `main()` | [L127](file:///home/librarianist/pcGDM/adjust_kbd_light.py#L127) | CLI entrypoint (`up`, `down`, `daemon`, etc.). |

### [mac_hud.py](file:///home/librarianist/pcGDM/mac_hud.py)
*Controls `/sys/class/leds/smc::kbd_backlight` for ambient hardware telemetry and notification pulses.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `get_max_brightness()` | [L34](file:///home/librarianist/pcGDM/mac_hud.py#L34) | Reads `max_brightness` from sysfs. |
| `get_current_brightness()` | [L41](file:///home/librarianist/pcGDM/mac_hud.py#L41) | Reads current `brightness` from sysfs. |
| `get_stored_preference()` | [L51](file:///home/librarianist/pcGDM/mac_hud.py#L51) | Reads last user-intended baseline brightness. |
| `save_stored_preference(val)` | [L64](file:///home/librarianist/pcGDM/mac_hud.py#L64) | Persists baseline brightness preference. |
| `set_brightness(val, save_pref)` | [L72](file:///home/librarianist/pcGDM/mac_hud.py#L72) | Writes brightness to sysfs (and optionally saves baseline). |
| `flash(count, delay, target)` | [L87](file:///home/librarianist/pcGDM/mac_hud.py#L87) | Flashes keyboard backlight and restores baseline. |
| `fade_to(target, duration, steps)` | [L120](file:///home/librarianist/pcGDM/mac_hud.py#L120) | Smoothly transitions brightness and saves as new baseline. |
| `breathe(cycles, cycle_duration, min_val, max_val)` | [L139](file:///home/librarianist/pcGDM/mac_hud.py#L139) | Sine-wave breathing pulse around user's baseline. |
| `alert(pulses)` | [L163](file:///home/librarianist/pcGDM/mac_hud.py#L163) | Urgent strobe warning pattern that restores original level. |
| `run_hud_daemon()` | [L178](file:///home/librarianist/pcGDM/mac_hud.py#L178) | Background ambient hardware HUD loop. |
| `main()` | [L230](file:///home/librarianist/pcGDM/mac_hud.py#L230) | CLI entrypoint (`hud`, `flash`, `fade`, `breathe`, `alert`). |

### [mac_visualizer.py](file:///home/librarianist/pcGDM/mac_visualizer.py)
*Real-time MacBook Pro keyboard audio beat visualizer and typing-reactive backlight engine.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `get_user_brightness()` | [L38](file:///home/librarianist/pcGDM/mac_visualizer.py#L38) | Returns user's manual brightness ceiling (0–255). |
| `save_user_brightness(val)` | [L58](file:///home/librarianist/pcGDM/mac_visualizer.py#L58) | Saves manual brightness preference. |
| `is_manual_override_active()` | [L73](file:///home/librarianist/pcGDM/mac_visualizer.py#L73) | Returns `True` if user adjusted brightness within the last 2.0s. |
| `set_hardware_brightness(kbd_f, val)` | [L86](file:///home/librarianist/pcGDM/mac_visualizer.py#L86) | Writes integer brightness to sysfs file handle. |
| `is_running()` | [L98](file:///home/librarianist/pcGDM/mac_visualizer.py#L98) | Checks if visualizer daemon is already running. |
| `stop_visualizer()` | [L109](file:///home/librarianist/pcGDM/mac_visualizer.py#L109) | Stops active visualizer process cleanly. |
| `get_monitor_source()` | [L132](file:///home/librarianist/pcGDM/mac_visualizer.py#L132) | Finds active speaker playback monitor source (never microphone). |
| `hardware_key_listener_loop(kbd_f)` | [L143](file:///home/librarianist/pcGDM/mac_visualizer.py#L143) | Detects physical Apple F5/F6 illumination key presses. |
| `run_music_visualizer()` | [L181](file:///home/librarianist/pcGDM/mac_visualizer.py#L181) | Captures speaker playback audio and pulses keyboard backlight to beats. |
| `run_typing_reactive()` | [L318](file:///home/librarianist/pcGDM/mac_visualizer.py#L318) | Flares keyboard backlight on keypress with exponential decay. |
| `main()` | [L381](file:///home/librarianist/pcGDM/mac_visualizer.py#L381) | CLI entrypoint (`music`, `typing`, `stop`). |

### [mac_call.py](file:///home/librarianist/pcGDM/mac_call.py)
*Hands-free Bluetooth phone call and voice bridge for Xubuntu / MacBook Pro.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L36](file:///home/librarianist/pcGDM/mac_call.py#L36) | Logs call bridge events. |
| `get_connected_phone_mac()` | [L40](file:///home/librarianist/pcGDM/mac_call.py#L40) | Finds currently connected phone MAC via `bluetoothctl`/BlueZ. |
| `save_phone_mac(mac)` | [L60](file:///home/librarianist/pcGDM/mac_call.py#L60) | Saves connected phone MAC. |
| `is_bluetooth_connected(mac)` | [L65](file:///home/librarianist/pcGDM/mac_call.py#L65) | Checks Bluetooth connection state for a MAC address. |
| `set_call_lighting(active)` | [L73](file:///home/librarianist/pcGDM/mac_call.py#L73) | Pulses keyboard backlight during active calls. |
| `answer_call()` | [L91](file:///home/librarianist/pcGDM/mac_call.py#L91) | Answers incoming call via HFP/oFono/ADB. |
| `hangup_call()` | [L135](file:///home/librarianist/pcGDM/mac_call.py#L135) | Ends or declines active call. |
| `prompt_incoming_call(caller, number)` | [L169](file:///home/librarianist/pcGDM/mac_call.py#L169) | Displays desktop dialog to answer or decline incoming call. |
| `run_daemon()` | [L219](file:///home/librarianist/pcGDM/mac_call.py#L219) | Monitors incoming call events and manages call state. |
| `print_status()` | [L314](file:///home/librarianist/pcGDM/mac_call.py#L314) | Prints current call bridge status. |
| `main()` | [L338](file:///home/librarianist/pcGDM/mac_call.py#L338) | CLI entrypoint (`daemon`, `answer`, `hangup`, `status`). |

---

## 4. Performance, Thermal & Memory Engines

### [cryo_ram_boost.py](file:///home/librarianist/pcGDM/cryo_ram_boost.py)
*Controls Apple SMC exhaust fan (`applesmc.768`), Intel i5-3210M P-state turbo/governors, and Linux VM pagecache/ZRAM reclaimer.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `read_sysfs(path, default)` | [L48](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L48) | Safely reads a sysfs attribute. |
| `write_sysfs(path, value)` | [L55](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L55) | Safely writes a sysfs attribute. |
| `require_root()` | [L66](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L66) | Exits with an error if not invoked as root. |
| `notify_user(title, message, icon)` | [L73](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L73) | Sends a desktop notification to the user session even when invoked under `sudo`. |
| `get_cpu_temp()` | [L95](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L95) | Returns highest Intel `coretemp` package/core temperature in °C. |
| `get_battery_metrics()` | [L111](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L111) | Reads battery charge, AC status, and wattage. |
| `get_ram_metrics()` | [L134](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L134) | Reads RAM and swap usage from `/proc/meminfo`. |
| `set_cpu_governor(governor)` | [L164](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L164) | Sets scaling governor across all CPU cores. |
| `apply_profile(profile, quiet)` | [L172](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L172) | Applies fan/CPU/turbo thermal profiles. |
| `purge_ram(unswap, quiet)` | [L238](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L238) | Drops VM caches and optionally cycles swap. |
| `run_smart_daemon()` | [L281](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L281) | Autonomous thermal/RAM daemon running on boot via `pcgdm-cryo.service`. |
| `show_status()` | [L374](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L374) | Prints CPU temp, fan RPM, governor, battery, and RAM metrics. |
| `install_systemd_service()` | [L408](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L408) | Installs and enables root `pcgdm-cryo.service`. |
| `uninstall_systemd_service()` | [L441](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L441) | Disables and removes `pcgdm-cryo.service`. |
| `main()` | [L452](file:///home/librarianist/pcGDM/cryo_ram_boost.py#L452) | CLI entrypoint. |

### [focus_freezer.py](file:///home/librarianist/pcGDM/focus_freezer.py)
*Event-driven X11 `xprop -spy` daemon that freezes (`SIGSTOP`) unfocused heavy browser renderers while sparing audio-playing tabs.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L51](file:///home/librarianist/pcGDM/focus_freezer.py#L51) | Writes timestamped logs. |
| `get_active_window_info()` | [L63](file:///home/librarianist/pcGDM/focus_freezer.py#L63) | Returns `(root_pid, wm_class_lower)` of the currently focused X11 window. |
| `get_audio_playing_pids_and_apps()` | [L101](file:///home/librarianist/pcGDM/focus_freezer.py#L101) | Queries `pactl` so tabs/apps playing audio are never frozen. |
| `find_freezable_targets()` | [L131](file:///home/librarianist/pcGDM/focus_freezer.py#L131) | Finds heavy browser renderer/worker PIDs grouped by browser family. |
| `tame_background_indexers()` | [L176](file:///home/librarianist/pcGDM/focus_freezer.py#L176) | Renices background indexers (`localsearch-3`, `tracker`, etc.) to nice `19`. |
| `set_pids_frozen(pids, freeze)` | [L200](file:///home/librarianist/pcGDM/focus_freezer.py#L200) | Sends `SIGSTOP` or `SIGCONT` to target PIDs. |
| `wake_all_browsers()` | [L212](file:///home/librarianist/pcGDM/focus_freezer.py#L212) | Resumes all frozen browser renderers with `SIGCONT`. |
| `get_frozen_status()` | [L222](file:///home/librarianist/pcGDM/focus_freezer.py#L222) | Lists currently stopped (`T`) browser renderer processes. |
| `show_status()` | [L238](file:///home/librarianist/pcGDM/focus_freezer.py#L238) | Prints freeze state summary. |
| `run_daemon()` | [L252](file:///home/librarianist/pcGDM/focus_freezer.py#L252) | Main `xprop -spy` focus-watching loop. |
| `main()` | [L312](file:///home/librarianist/pcGDM/focus_freezer.py#L312) | CLI entrypoint. |

### [warp_ram.py](file:///home/librarianist/pcGDM/warp_ram.py)
*In-memory `/dev/shm` RAM disk scratchpad (`~/ramdisk`) with automatic SSD backing sync.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L32](file:///home/librarianist/pcGDM/warp_ram.py#L32) | Writes timestamped logs. |
| `notify(title, msg)` | [L43](file:///home/librarianist/pcGDM/warp_ram.py#L43) | Sends desktop notification via `notify-send`. |
| `init_ramdisk()` | [L53](file:///home/librarianist/pcGDM/warp_ram.py#L53) | Initializes RAM directory in `/dev/shm` and ensures `~/ramdisk` symlink exists. |
| `sync_to_disk()` | [L72](file:///home/librarianist/pcGDM/warp_ram.py#L72) | Mirrors files from RAM disk to persistent SSD backing directory. |
| `restore_from_disk()` | [L89](file:///home/librarianist/pcGDM/warp_ram.py#L89) | Restores saved SSD mirror back into RAM. |
| `get_usage()` | [L105](file:///home/librarianist/pcGDM/warp_ram.py#L105) | Computes used size and file count inside the RAM disk. |
| `run_daemon()` | [L125](file:///home/librarianist/pcGDM/warp_ram.py#L125) | Periodic sync daemon managed by `systemd --user`. |
| `show_status()` | [L158](file:///home/librarianist/pcGDM/warp_ram.py#L158) | Prints RAM disk usage and sync status. |
| `main()` | [L168](file:///home/librarianist/pcGDM/warp_ram.py#L168) | CLI entrypoint. |

---

## 5. File Organization, LAN Sharing & Remote Control

### [auto_janitor.py](file:///home/librarianist/pcGDM/auto_janitor.py)
*Kernel-level `inotify` real-time file organizer across user directories.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `is_protected_dir(directory)` | [L113](file:///home/librarianist/pcGDM/auto_janitor.py#L113) | Returns `True` for hidden folders, category folders, SDKs, or git/code repos. |
| `get_category(filepath)` | [L142](file:///home/librarianist/pcGDM/auto_janitor.py#L142) | Maps a file extension to its target category folder (or `None`). |
| `resolve_destination_base(...)` | [L163](file:///home/librarianist/pcGDM/auto_janitor.py#L163) | Resolves target base directory (local or central hub). |
| `unique_destination(dest_dir, filename)` | [L195](file:///home/librarianist/pcGDM/auto_janitor.py#L195) | Appends `_1`, `_2`, etc. to prevent overwriting existing files. |
| `notify(title, message)` | [L216](file:///home/librarianist/pcGDM/auto_janitor.py#L216) | Sends Xubuntu desktop notification via `notify-send`. |
| `log_action(log_file, message)` | [L229](file:///home/librarianist/pcGDM/auto_janitor.py#L229) | Appends action entry to janitor log. |
| `process_file(...)` | [L241](file:///home/librarianist/pcGDM/auto_janitor.py#L241) | Moves a single file into its category folder (supports `--dry-run`). |
| `expand_watch_directories(...)` | [L295](file:///home/librarianist/pcGDM/auto_janitor.py#L295) | Builds safe list of directories to watch. |
| `sweep_existing(...)` | [L331](file:///home/librarianist/pcGDM/auto_janitor.py#L331) | Sweeps existing loose files across watched directories. |
| `InotifyWatcher` | [L355](file:///home/librarianist/pcGDM/auto_janitor.py#L355) | `ctypes` wrapper around Linux kernel `inotify` (`__init__`, `add_watch`, `read_events`, `close`). |
| `main()` | [L406](file:///home/librarianist/pcGDM/auto_janitor.py#L406) | CLI entrypoint. |

### [airdrop_zero.py](file:///home/librarianist/pcGDM/airdrop_zero.py)
*Zero-dependency local HTTP file drop & download server (port 7777) with QR code support.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `render_qr_ascii(text)` | [L32](file:///home/librarianist/pcGDM/airdrop_zero.py#L32) | Prints ASCII QR code via `qrencode` or boxed URL fallback. |
| `get_local_ip()` | [L52](file:///home/librarianist/pcGDM/airdrop_zero.py#L52) | Detects active local LAN IP address. |
| `notify(title, msg)` | [L63](file:///home/librarianist/pcGDM/airdrop_zero.py#L63) | Sends desktop notification. |
| `AirDropHandler` | [L275](file:///home/librarianist/pcGDM/airdrop_zero.py#L275) | `BaseHTTPRequestHandler` subclass (`log_message`, `do_GET`, `do_POST`) serving upload UI and file transfers. |
| `run_server(port)` | [L388](file:///home/librarianist/pcGDM/airdrop_zero.py#L388) | Starts HTTP server on `0.0.0.0:port`. |
| `main()` | [L409](file:///home/librarianist/pcGDM/airdrop_zero.py#L409) | CLI entrypoint. |

### [hive_nexus.py](file:///home/librarianist/pcGDM/hive_nexus.py)
*Local mesh device coordinator (Smart TV DIAL/Cast, KDE Connect, and mDNS `avahi-browse`).*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `log(msg)` | [L43](file:///home/librarianist/pcGDM/hive_nexus.py#L43) | Logs mesh coordinator events. |
| `notify(title, msg, icon)` | [L54](file:///home/librarianist/pcGDM/hive_nexus.py#L54) | Sends desktop notification. |
| `get_tv_status(ip)` | [L68](file:///home/librarianist/pcGDM/hive_nexus.py#L68) | Queries Smart TV Cast/DIAL endpoint on port `8008`. |
| `get_phone_device_id(name_hint)` | [L108](file:///home/librarianist/pcGDM/hive_nexus.py#L108) | Resolves KDE Connect device ID for paired phone. |
| `ring_phone()` | [L124](file:///home/librarianist/pcGDM/hive_nexus.py#L124) | Rings paired phone via KDE Connect. |
| `push_clipboard_to_phone()` | [L136](file:///home/librarianist/pcGDM/hive_nexus.py#L136) | Pushes X11 clipboard to paired phone via KDE Connect. |
| `share_to_phone(path_or_url)` | [L148](file:///home/librarianist/pcGDM/hive_nexus.py#L148) | Shares a file or URL to phone via KDE Connect. |
| `send_sms(phone_number, message)` | [L160](file:///home/librarianist/pcGDM/hive_nexus.py#L160) | Sends SMS through paired phone via KDE Connect. |
| `scan_lan_devices()` | [L179](file:///home/librarianist/pcGDM/hive_nexus.py#L179) | Discovers LAN devices via `avahi-browse`. |
| `run_daemon()` | [L215](file:///home/librarianist/pcGDM/hive_nexus.py#L215) | Background device watcher managed by `systemd --user`. |
| `show_status()` | [L272](file:///home/librarianist/pcGDM/hive_nexus.py#L272) | Prints discovered devices and phone status. |
| `main()` | [L288](file:///home/librarianist/pcGDM/hive_nexus.py#L288) | CLI entrypoint. |

### [tele_key.py](file:///home/librarianist/pcGDM/tele_key.py)
*Physical Hardware USB Telegram Remote Bridge.*

| Symbol | Line | Description |
| :--- | :--- | :--- |
| `load_config()` / `save_config(cfg)` | [L53](file:///home/librarianist/pcGDM/tele_key.py#L53) | Loads and persists Telegram bot token, chat ID, and alias config. |
| `get_connected_usb_devices()` | [L82](file:///home/librarianist/pcGDM/tele_key.py#L82) | Lists connected USB devices (`lsusb`). |
| `flash_keyboard(pulses)` | [L111](file:///home/librarianist/pcGDM/tele_key.py#L111) | Flashes MacBook keyboard backlight. |
| `get_system_telemetry()` | [L120](file:///home/librarianist/pcGDM/tele_key.py#L120) | Collects CPU, RAM, disk, battery, and thermal telemetry. |
| `speak_deep_human(text)` | [L190](file:///home/librarianist/pcGDM/tele_key.py#L190) | Synthesizes and plays deep voice TTS through MacBook speakers. |
| `TelegramBotBridge` | [L230](file:///home/librarianist/pcGDM/tele_key.py#L230) | Telegram Bot API bridge (`__init__`, `clear_webhook`, `register_commands`, `send_message`, `answer_callback`, `send_photo`, `send_voice`, `send_document`, `build_dir_view`, `get_updates`, `handle_command`, `run_polling`, `start`, `stop`). |
| `main()` | [L1299](file:///home/librarianist/pcGDM/tele_key.py#L1299) | CLI/service entrypoint. |

---

## 6. Shell Installers & Service Control

| Script | Functions / Purpose |
| :--- | :--- |
| [godmode.sh](file:///home/librarianist/pcGDM/godmode.sh) | Installs & checks all user services: `install_freezer_service()` ([L59](file:///home/librarianist/pcGDM/godmode.sh#L59)), `install_hud_service()` ([L98](file:///home/librarianist/pcGDM/godmode.sh#L98)), `install_airdrop_service()` ([L133](file:///home/librarianist/pcGDM/godmode.sh#L133)), `install_warp_service()` ([L170](file:///home/librarianist/pcGDM/godmode.sh#L170)), `install_grab_service()` ([L206](file:///home/librarianist/pcGDM/godmode.sh#L206)), `install_hive_service()` ([L244](file:///home/librarianist/pcGDM/godmode.sh#L244)), `install_tele_service()` ([L281](file:///home/librarianist/pcGDM/godmode.sh#L281)), `install_all()` ([L319](file:///home/librarianist/pcGDM/godmode.sh#L319)), `status_all()` ([L354](file:///home/librarianist/pcGDM/godmode.sh#L354)). |
| [janitorctl.sh](file:///home/librarianist/pcGDM/janitorctl.sh) | Service control helper for `pcgdm-janitor.service`: `usage()` ([L18](file:///home/librarianist/pcGDM/janitorctl.sh#L18)), `install_service()` ([L32](file:///home/librarianist/pcGDM/janitorctl.sh#L32)), `uninstall_service()` ([L74](file:///home/librarianist/pcGDM/janitorctl.sh#L74)). |
| [install_root_biounlock.sh](file:///home/librarianist/pcGDM/install_root_biounlock.sh) | Installs root `pcgdm-biounlock.service`, `/usr/local/bin/pcgdm-pam-check`, and hooks `pam_exec.so` into `/etc/pam.d/lightdm` (with `/etc/pam.d/lightdm.bak` backup). |
| [enable_root_freedom.sh](file:///home/librarianist/pcGDM/enable_root_freedom.sh) | Configures `/etc/sudoers.d/pcgdm-admin` for passwordless `pcGDM` admin operations. |
