#!/usr/bin/env python3
"""
pcGDM Cryo & RAM Boost Engine (2012 MacBook Pro Edition)
Directly controls Apple SMC Exhaust Fan (applesmc.768), Intel i5-3210M P-State Turbo & Governors,
and Linux VM Pagecache / ZRAM Swap Reclaimer.
"""

import argparse
import datetime
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

# --- Hardware Sysfs Paths (2012 MacBook Pro) ---
SMC_DIR = Path("/sys/devices/platform/applesmc.768")
FAN_INPUT = SMC_DIR / "fan1_input"      # Current actual RPM
FAN_MANUAL = SMC_DIR / "fan1_manual"    # 1 = manual override, 0 = automatic/mbpfan
FAN_OUTPUT = SMC_DIR / "fan1_output"    # Target RPM when manual=1
FAN_MIN = SMC_DIR / "fan1_min"          # Minimum RPM floor when manual=0

PSTATE_DIR = Path("/sys/devices/system/cpu/intel_pstate")
NO_TURBO = PSTATE_DIR / "no_turbo"      # 0 = 3.1GHz Turbo ON, 1 = 2.5GHz Cap (Ice-Cold Stealth)
MAX_PERF = PSTATE_DIR / "max_perf_pct"  # 0-100%
MIN_PERF = PSTATE_DIR / "min_perf_pct"

AC_ONLINE = Path("/sys/class/power_supply/ADP1/online")
BAT_DIR = Path("/sys/class/power_supply/BAT0")

DROP_CACHES = Path("/proc/sys/vm/drop_caches")
SWAPPINESS = Path("/proc/sys/vm/swappiness")
VFS_CACHE_PRESSURE = Path("/proc/sys/vm/vfs_cache_pressure")

STATE_FILE = Path("/tmp/pcgdm_cryo_mode")

# --- ANSI Colors ---
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
MAGENTA = "\033[0;35m"
BOLD = "\033[1m"
NC = "\033[0m"


def read_sysfs(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return default


def write_sysfs(path: Path, value: str | int) -> bool:
    try:
        path.write_text(f"{value}\n", encoding="utf-8")
        return True
    except PermissionError:
        return False
    except OSError as e:
        print(f"{RED}[!] Failed writing {value} to {path}: {e}{NC}", file=sys.stderr)
        return False


def require_root() -> None:
    if os.geteuid() != 0:
        print(f"{YELLOW}[!] Hardware SMC/CPU/VM tuning requires root privileges.{NC}")
        print(f"    Re-running with sudo...\n")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)


def notify_user(title: str, message: str, icon: str = "utilities-system-monitor") -> None:
    """Send desktop notification even when invoked via sudo."""
    sudo_user = os.environ.get("SUDO_USER")
    uid = os.environ.get("SUDO_UID")
    cmd = ["notify-send", "-a", "pcGDM CryoBoost", "-i", icon, "-t", "4000", title, message]
    try:
        if sudo_user and uid:
            env = os.environ.copy()
            env[" DISPLAY"] = ":0"
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"
            subprocess.run(
                ["sudo", "-u", sudo_user, f"DISPLAY=:0", f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus"] + cmd,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def get_cpu_temp() -> float:
    """Return highest Intel coretemp package/core temperature in °C."""
    temps: list[float] = []
    for p in glob.glob("/sys/class/hwmon/hwmon*/temp*_input"):
        try:
            name_path = Path(p).parent / "name"
            chip = read_sysfs(name_path)
            if chip == "coretemp":
                val = int(read_sysfs(Path(p), "0")) / 1000.0
                if 10.0 < val < 120.0:
                    temps.append(val)
        except ValueError:
            pass
    return max(temps) if temps else 50.0


def get_battery_metrics() -> dict[str, str]:
    ac = read_sysfs(AC_ONLINE, "0") == "1"
    status = read_sysfs(BAT_DIR / "status", "Unknown")
    capacity = read_sysfs(BAT_DIR / "capacity", "?")

    # Compute live wattage from voltage_now (µV) and current_now (µA) or power_now (µW)
    watts = 0.0
    try:
        v_uv = int(read_sysfs(BAT_DIR / "voltage_now", "0"))
        i_ua = int(read_sysfs(BAT_DIR / "current_now", "0"))
        watts = (v_uv / 1e6) * (i_ua / 1e6)
    except ValueError:
        pass

    return {
        "ac_online": "Plugged In (MagSafe)" if ac else "On Battery",
        "ac_bool": "1" if ac else "0",
        "status": status,
        "capacity": f"{capacity}%",
        "watts": f"{watts:.1f} W" if watts > 0 else "N/A",
    }


def get_ram_metrics() -> dict[str, float]:
    mem: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val_kb = int(parts[1].strip().split()[0])
                mem[key] = val_kb
    except Exception:
        pass

    total_mb = mem.get("MemTotal", 0) / 1024.0
    avail_mb = mem.get("MemAvailable", 0) / 1024.0
    used_mb = total_mb - avail_mb
    swap_total_mb = mem.get("SwapTotal", 0) / 1024.0
    swap_free_mb = mem.get("SwapFree", 0) / 1024.0
    swap_used_mb = swap_total_mb - swap_free_mb
    cached_mb = (mem.get("Cached", 0) + mem.get("SReclaimable", 0)) / 1024.0

    return {
        "total_mb": total_mb,
        "used_mb": used_mb,
        "avail_mb": avail_mb,
        "cached_mb": cached_mb,
        "swap_total_mb": swap_total_mb,
        "swap_used_mb": swap_used_mb,
    }


def set_cpu_governor(governor: str) -> None:
    for gov_file in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor"):
        write_sysfs(Path(gov_file), governor)


# ==============================================================================
# PROFILES: TURBO, CRYO, STEALTH, AUTO
# ==============================================================================
def apply_profile(profile: str, quiet: bool = False) -> None:
    require_root()

    if profile == "turbo":
        # Full 3.1 GHz Turbo + Pre-cooled 5600 RPM Fan Floor + Performance Governor
        write_sysfs(NO_TURBO, 0)
        write_sysfs(MAX_PERF, 100)
        write_sysfs(MIN_PERF, 40)
        set_cpu_governor("performance")
        # Let mbpfan scale up to 6200, but lock minimum floor to 5500 RPM so CPU never heat-soaks
        write_sysfs(FAN_MANUAL, 0)
        write_sysfs(FAN_MIN, 5500)
        write_sysfs(SWAPPINESS, 10)
        write_sysfs(VFS_CACHE_PRESSURE, 50)
        STATE_FILE.write_text("TURBO (3.1 GHz Max + 5500 RPM Pre-Cool)\n")
        msg = "CPU: 3.1 GHz Turbo Unlocked (performance)\nFan Floor: 5500 RPM (Anti-Throttle)"
        print(f"{GREEN}[+] Applied TURBO GOD MODE:{NC}\n    {msg.replace(chr(10), chr(10) + '    ')}")
        if not quiet:
            notify_user("CryoBoost: TURBO MODE", msg)

    elif profile == "cryo":
        # Maximum 6200 RPM Blizzard Blast (instant rapid cooldown when MacBook is hot)
        write_sysfs(FAN_MANUAL, 1)
        write_sysfs(FAN_OUTPUT, 6200)
        write_sysfs(FAN_MIN, 6200)
        STATE_FILE.write_text("CRYO BLAST (6200 RPM Max Manual Lock)\n")
        msg = "Apple SMC Exhaust Fan locked to MAX 6200 RPM!"
        print(f"{CYAN}[+] Applied CRYO MAX BLAST:{NC} {msg}")
        if not quiet:
            notify_user("CryoBoost: 6200 RPM CRYO BLAST", msg)

    elif profile == "stealth":
        # Disable Intel Turbo (caps i5-3210M at 2.5GHz base clock -> drops heat ~18°C & halves battery drain!)
        write_sysfs(NO_TURBO, 1)
        write_sysfs(MAX_PERF, 80)
        write_sysfs(MIN_PERF, 15)
        set_cpu_governor("powersave")
        write_sysfs(FAN_MANUAL, 0)
        write_sysfs(FAN_MIN, 2200)
        write_sysfs(SWAPPINESS, 20)
        STATE_FILE.write_text("STEALTH (2.5 GHz Cap / Ice-Cold Battery Saver)\n")
        msg = "Intel Turbo Disabled (2.5 GHz Base Cap)\nGovernor: powersave | Fan Floor: 2200 RPM\nCuts heat by ~15°C & extends battery!"
        print(f"{CYAN}[+] Applied STEALTH ICE MODE:{NC}\n    {msg.replace(chr(10), chr(10) + '    ')}")
        if not quiet:
            notify_user("CryoBoost: STEALTH BATTERY MODE", msg)

    elif profile == "balanced":
        # Smart everyday sweet spot: 3.1 GHz Turbo allowed, responsive 3000 RPM airflow floor
        write_sysfs(NO_TURBO, 0)
        write_sysfs(MAX_PERF, 100)
        write_sysfs(MIN_PERF, 20)
        set_cpu_governor("powersave")
        write_sysfs(FAN_MANUAL, 0)
        write_sysfs(FAN_MIN, 3000)
        write_sysfs(SWAPPINESS, 10)
        write_sysfs(VFS_CACHE_PRESSURE, 50)
        STATE_FILE.write_text("BALANCED (Smart Turbo + 3000 RPM Floor)\n")
        msg = "CPU: Dynamic 1.2–3.1 GHz\nFan: Auto mbpfan (3000–6200 RPM)"
        print(f"{GREEN}[+] Applied BALANCED MODE:{NC}\n    {msg.replace(chr(10), chr(10) + '    ')}")
        if not quiet:
            notify_user("CryoBoost: BALANCED MODE", msg)


# ==============================================================================
# RAM & SWAP MULTIPLIER / RECLAIMER (`purge`)
# ==============================================================================
def purge_ram(unswap: bool = False, quiet: bool = False) -> None:
    require_root()
    before = get_ram_metrics()
    print(f"{CYAN}[*] Before RAM Purge:{NC} Available: {before['avail_mb']:.0f} MiB | Cached: {before['cached_mb']:.0f} MiB | Swap Used: {before['swap_used_mb']:.0f} MiB")

    # 1. Flush filesystem buffers to disk safely
    subprocess.run(["sync"], check=False)

    # 2. Drop clean pagecache, dentries, and inodes (frees reclaimable cache immediately)
    write_sysfs(DROP_CACHES, 3)

    # 3. Trigger kernel memory compaction so large contiguous blocks are available
    compact_path = Path("/proc/sys/vm/compact_memory")
    if compact_path.exists():
        write_sysfs(compact_path, 1)

    # 4. Optional unswap: pull sluggish swapped pages back into fast physical DDR3 RAM if space permits
    if unswap and before["swap_used_mb"] > 10:
        after_cache = get_ram_metrics()
        if after_cache["avail_mb"] > before["swap_used_mb"] + 600:
            print(f"{YELLOW}[*] Pulling {before['swap_used_mb']:.0f} MiB out of ZRAM/Swap back into fast physical RAM...{NC}")
            subprocess.run(["swapoff", "-a"], check=False)
            subprocess.run(["swapon", "-a"], check=False)
        else:
            print(f"{YELLOW}[!] Skipping full swap drain (not enough free headroom for {before['swap_used_mb']:.0f} MiB swap).{NC}")

    time.sleep(0.3)
    after = get_ram_metrics()
    gained = after["avail_mb"] - before["avail_mb"]
    sign = "+" if gained >= 0 else ""

    summary = (
        f"Available RAM: {before['avail_mb']:.0f} MiB → {after['avail_mb']:.0f} MiB ({sign}{gained:.0f} MiB freed)\n"
        f"Swap Used: {after['swap_used_mb']:.0f} MiB"
    )
    print(f"{GREEN}[+] RAM Purge Complete!{NC}\n    {summary.replace(chr(10), chr(10) + '    ')}")
    if not quiet:
        notify_user("CryoBoost: RAM Purged", summary)


# ==============================================================================
# AUTONOMOUS SMART THERMAL DAEMON (`daemon`)
# ==============================================================================
def run_smart_daemon() -> None:
    """
    Unified Autonomous Engine (runs on boot via systemd):
    Combines Stealth (on battery), Turbo/Balanced (on MagSafe AC), Cryo (thermal curve),
    and automatic RAM Purge into one continuous self-driving loop!
    """
    require_root()
    print(f"{GREEN}[+] Starting pcGDM Unified Autonomous Cryo + RAM + Power Engine...{NC}", flush=True)

    # Apply initial memory subsystem tuning & initial safe cache purge on startup
    write_sysfs(SWAPPINESS, 10)
    write_sysfs(VFS_CACHE_PRESSURE, 50)
    subprocess.run(["sync"], check=False)
    write_sysfs(DROP_CACHES, 1)

    last_cache_drop = time.time()
    last_mode = ""

    try:
        while True:
            temp = get_cpu_temp()
            ac = read_sysfs(AC_ONLINE, "0") == "1"
            ram = get_ram_metrics()

            # --- 1. Automatic Power Profile (Battery = Stealth | MagSafe AC = Dynamic Turbo) ---
            if not ac:
                # On Battery: protect battery life & keep palmrest cool
                write_sysfs(NO_TURBO, 1)
                write_sysfs(MAX_PERF, 82)
                write_sysfs(MIN_PERF, 15)
                set_cpu_governor("powersave")
                active_mode = "AUTO-STEALTH (On Battery: 2.5 GHz Cap / Low Power)"
            else:
                # Plugged into MagSafe: unlock 3.1 GHz Turbo unless thermally critical (>86°C)
                if temp >= 86.0:
                    write_sysfs(NO_TURBO, 1)
                    active_mode = "AUTO-CRYO GUARD (AC Plugged: Cooling Down >=86°C)"
                else:
                    write_sysfs(NO_TURBO, 0)
                    write_sysfs(MAX_PERF, 100)
                    write_sysfs(MIN_PERF, 25)
                    set_cpu_governor("performance" if temp < 76.0 else "powersave")
                    active_mode = "AUTO-TURBO (AC Plugged: 3.1 GHz Unlocked)"

            # --- 2. Dynamic Apple SMC Fan Curve (2200 -> 6200 RPM) ---
            if temp >= 82.0:
                # Emergency Full 6200 RPM Cryo Blast
                write_sysfs(FAN_MANUAL, 1)
                write_sysfs(FAN_OUTPUT, 6200)
                write_sysfs(FAN_MIN, 6200)
            elif temp >= 74.0:
                write_sysfs(FAN_MANUAL, 0)
                write_sysfs(FAN_MIN, 5400)
            elif temp >= 66.0:
                write_sysfs(FAN_MANUAL, 0)
                write_sysfs(FAN_MIN, 4200)
            elif temp >= 58.0:
                write_sysfs(FAN_MANUAL, 0)
                write_sysfs(FAN_MIN, 3100)
            else:
                write_sysfs(FAN_MANUAL, 0)
                write_sysfs(FAN_MIN, 2200)

            if active_mode != last_mode:
                STATE_FILE.write_text(f"{active_mode}\n")
                print(f"[{datetime.datetime.now():%H:%M:%S}] Mode switched -> {active_mode} (Temp: {temp:.1f}°C)", flush=True)
                last_mode = active_mode

            # --- 3. Automatic RAM & Cache Reclaimer ---
            # Triggers whenever Available RAM drops below 900 MiB OR Cache bloats past 3500 MiB (max once per 3 mins)
            now = time.time()
            if (ram["avail_mb"] < 900 or (ram["cached_mb"] > 3500 and ram["avail_mb"] < 2000)) and (now - last_cache_drop) > 180:
                subprocess.run(["sync"], check=False)
                write_sysfs(DROP_CACHES, 3)
                compact_path = Path("/proc/sys/vm/compact_memory")
                if compact_path.exists():
                    write_sysfs(compact_path, 1)
                last_cache_drop = now
                after_ram = get_ram_metrics()
                print(
                    f"[{datetime.datetime.now():%H:%M:%S}] Auto-Purged RAM: "
                    f"{ram['avail_mb']:.0f} MiB -> {after_ram['avail_mb']:.0f} MiB available",
                    flush=True,
                )

            time.sleep(4)
    except KeyboardInterrupt:
        print("\n[-] Daemon stopped.")


# ==============================================================================
# LIVE TELEMETRY DASHBOARD (`status`)
# ==============================================================================
def show_status() -> None:
    temp = get_cpu_temp()
    fan_rpm = read_sysfs(FAN_INPUT, "?")
    fan_min = read_sysfs(FAN_MIN, "?")
    fan_manual = read_sysfs(FAN_MANUAL, "0")
    no_turbo = read_sysfs(NO_TURBO, "0")
    max_perf = read_sysfs(MAX_PERF, "100")
    gov = read_sysfs(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"), "unknown")
    cur_freq_khz = int(read_sysfs(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"), "0"))
    cur_freq_ghz = cur_freq_khz / 1e6 if cur_freq_khz else 0.0
    swappiness = read_sysfs(SWAPPINESS, "?")
    bat = get_battery_metrics()
    ram = get_ram_metrics()
    mode_str = read_sysfs(STATE_FILE, "Custom / System Default")

    temp_color = GREEN if temp < 65 else (YELLOW if temp < 80 else RED)

    print(f"{BOLD}╔══════════════════════════════════════════════════════════════════╗{NC}")
    print(f"{BOLD}║     pcGDM CRYO & RAM BOOST — 2012 MacBook Pro Telemetry          ║{NC}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════════════════╝{NC}")
    print(f"  {BOLD}Active Profile :{NC} {MAGENTA}{mode_str}{NC}")
    print(f"  {BOLD}CPU Core Temp  :{NC} {temp_color}{temp:.1f}°C{NC} (Crit: 105°C)")
    print(f"  {BOLD}CPU Clock/Gov  :{NC} {CYAN}{cur_freq_ghz:.2f} GHz{NC} | Governor: {BOLD}{gov}{NC} | Max Perf: {max_perf}%")
    print(f"  {BOLD}Intel Turbo    :{NC} {'DISABLED (2.5 GHz Stealth Cap)' if no_turbo == '1' else 'ENABLED (Up to 3.1 GHz)'}")
    print(f"  {BOLD}Apple SMC Fan  :{NC} {CYAN}{fan_rpm} RPM{NC} (Min Floor: {fan_min} RPM | Max: 6200 RPM | Mode: {'MANUAL' if fan_manual == '1' else 'AUTO/mbpfan'})")
    print(f"  {BOLD}Power & Drain  :{NC} {bat['ac_online']} ({bat['status']}, {bat['capacity']}) | Live Draw: {YELLOW}{bat['watts']}{NC}")
    print(f"  {BOLD}DDR3 RAM       :{NC} {ram['used_mb']:.0f} / {ram['total_mb']:.0f} MiB used ({GREEN}{ram['avail_mb']:.0f} MiB Available{NC} | {ram['cached_mb']:.0f} MiB Cache)")
    print(f"  {BOLD}ZRAM + Swap    :{NC} {ram['swap_used_mb']:.0f} / {ram['swap_total_mb']:.0f} MiB used | Swappiness: {swappiness}")


SERVICE_FILE = Path("/etc/systemd/system/pcgdm-cryo.service")
SUDOERS_FILE = Path("/etc/sudoers.d/pcgdm-cryo")


def install_systemd_service() -> None:
    """Install and start pcgdm-cryo.service at the root systemd level so it starts on every boot."""
    require_root()
    script_path = Path(__file__).resolve()
    sudo_user = os.environ.get("SUDO_USER", "librarianist")

    service_content = f"""[Unit]
Description=pcGDM Unified Cryo, Power & RAM Boost Engine (2012 MacBook Pro)
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {script_path} daemon
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    SERVICE_FILE.write_text(service_content, encoding="utf-8")

    # Also allow the user to run cryo_ram_boost.py without a password prompt anytime
    sudoers_content = f"{sudo_user} ALL=(ALL) NOPASSWD: /usr/bin/python3 {script_path} *, {script_path} *\n"
    SUDOERS_FILE.write_text(sudoers_content, encoding="utf-8")
    os.chmod(SUDOERS_FILE, 0o440)

    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", "pcgdm-cryo.service"], check=True)
    print(f"{GREEN}[+] Installed and started permanent boot service: pcgdm-cryo.service!{NC}")
    print(f"{GREEN}[+] Enabled passwordless execution for {sudo_user}.{NC}\n")
    subprocess.run(["systemctl", "status", "pcgdm-cryo.service", "--no-pager"], check=False)


def uninstall_systemd_service() -> None:
    require_root()
    subprocess.run(["systemctl", "disable", "--now", "pcgdm-cryo.service"], check=False)
    if SERVICE_FILE.exists():
        SERVICE_FILE.unlink()
    if SUDOERS_FILE.exists():
        SUDOERS_FILE.unlink()
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    print(f"{YELLOW}[-] Removed pcgdm-cryo.service boot daemon.{NC}")


def main() -> None:
    parser = argparse.ArgumentParser(description="pcGDM Cryo & RAM Boost for 2012 MacBook Pro")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=["status", "install", "uninstall", "turbo", "stealth", "cryo", "balanced", "purge", "deep-purge", "daemon"],
        help="Command to execute (default: status)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress desktop notifications")
    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "install":
        install_systemd_service()
        print()
        show_status()
    elif args.command == "uninstall":
        uninstall_systemd_service()
    elif args.command in ("turbo", "stealth", "cryo", "balanced"):
        apply_profile(args.command, quiet=args.quiet)
        print()
        show_status()
    elif args.command == "purge":
        purge_ram(unswap=False, quiet=args.quiet)
    elif args.command == "deep-purge":
        purge_ram(unswap=True, quiet=args.quiet)
    elif args.command == "daemon":
        run_smart_daemon()


if __name__ == "__main__":
    main()
