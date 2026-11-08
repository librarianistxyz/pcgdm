#!/usr/bin/env python3
"""
pcGDM Auto-Janitor (Broad User-Wide Edition)
Zero-dependency, kernel-level (inotify) real-time file organizer for Xubuntu.
Watches user folders broadly across /home/librarianist while intelligently protecting
source code repositories, SDKs, and system configs.
"""

import argparse
import ctypes
import ctypes.util
import datetime
import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

# --- Linux inotify constants ---
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_TO    = 0x00000080
IN_CREATE      = 0x00000100
IN_ISDIR       = 0x40000000
WATCH_MASK     = IN_CLOSE_WRITE | IN_MOVED_TO | IN_CREATE

# --- File Category Mapping ---
CATEGORIES = {
    "PDFs": {
        ".pdf", ".epub", ".mobi", ".djvu"
    },
    "Images": {
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
        ".tiff", ".tif", ".ico", ".heic", ".avif", ".raw", ".cr2", ".nef"
    },
    "Archives": {
        ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz",
        ".7z", ".rar", ".zst", ".deb", ".rpm", ".iso", ".AppImage", ".dmg"
    },
    "Scripts_Code": {
        ".sh", ".bash", ".zsh", ".py", ".js", ".ts", ".jsx", ".tsx",
        ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java", ".rb",
        ".php", ".lua", ".sql", ".html", ".css", ".json", ".yaml", ".yml",
        ".toml", ".xml", ".patch", ".diff"
    },
    "Documents": {
        ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".csv",
        ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp"
    },
    "Audio": {
        ".mp3", ".wav", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".wma"
    },
    "Video": {
        ".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"
    },
}

# Ignore browser temporary/in-progress download extensions and desktop shortcuts
IGNORE_EXTENSIONS = {
    ".crdownload",  # Chrome / Chromium / Brave partial download
    ".part",        # Firefox partial download
    ".download",    # Generic partial download
    ".tmp",         # Temporary files
    ".temp",
    ".opdownload",  # Opera partial download
    ".desktop",     # Keep XFCE desktop launchers on Desktop!
    ".torrent",
    ".swp",         # Vim swap files
    ".lock",        # Lockfiles
}

IGNORE_PREFIXES = (".", "~$")

# Folders in $HOME that should NEVER have their internal files moved (SDKs, apps, build dirs)
PROTECTED_DIR_NAMES = {
    "Android", "bin", "build", "flutter", "flutter_sdk", "go", "java",
    "libinput-gestures", "mbpfan", "node_modules", "nuclei-templates",
    "pcGDM", "skippy-xd", "snap", "testssl.sh", "vscode-backup",
    "watermark-remover-ai", "wordlists", "__pycache__", "venv", ".venv",
    "env", "dist", "target", "vendor",
}

# Project markers: if a directory contains any of these, it's a coding project/repo — don't scramble it!
PROJECT_MARKERS = {
    ".git", "package.json", "pubspec.yaml", "Cargo.toml", "pyproject.toml",
    "requirements.txt", "Makefile", "CMakeLists.txt", "go.mod", "pom.xml",
    "build.gradle", "firebase.json",
}

# Default user-wide folders to watch and organize
DEFAULT_BROAD_DIRS = [
    Path.home(),  # Top-level ~ (catches loose files dropped directly in /home/librarianist)
    Path.home() / "Downloads",
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Pictures",
    Path.home() / "Videos",
    Path.home() / "Music",
    Path.home() / "Public",
    Path.home() / "Sync",
    Path.home() / "LIBRARIANIST",
]

# Folders where files are already in their home category (unless a wrong file type lands there!)
NATIVE_FOLDER_CATEGORY = {
    "Pictures": "Images",
    "Videos": "Video",
    "Music": "Audio",
}


def is_protected_dir(directory: Path) -> bool:
    """Return True if directory is hidden, a Category folder, an SDK/app folder, or a code repository."""
    if not directory.exists() or not directory.is_dir():
        return True

    # Never watch hidden directories (.config, .local, .cache, .ssh, etc.)
    for part in directory.parts:
        if part.startswith(".") and part not in (".", "/"):
            return True

    # Never re-sort inside our own sorted category subfolders
    if directory.name in CATEGORIES:
        return True

    # Never touch known SDK/system directories
    if directory.name in PROTECTED_DIR_NAMES:
        return True

    # Never scramble a git repo or software project
    try:
        for marker in PROJECT_MARKERS:
            if (directory / marker).exists():
                return True
    except OSError:
        return True

    return False


def get_category(filepath: Path) -> str | None:
    """Return target category folder name for a file, or None if it should be ignored."""
    name = filepath.name
    if any(name.startswith(p) for p in IGNORE_PREFIXES):
        return None

    lower_name = name.lower()
    if lower_name.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")):
        return "Archives"

    ext = filepath.suffix.lower()
    if not ext or ext in IGNORE_EXTENSIONS:
        return None

    for category, exts in CATEGORIES.items():
        if ext in {e.lower() for e in exts}:
            return category

    return None


def resolve_destination_base(parent_dir: Path, category: str, central_hub: Path | None) -> Path | None:
    """
    Determine where the category subfolder should live.
    - If central_hub is set, all sorted files go to <central_hub>/<Category>.
    - If a file is dropped directly in $HOME (/home/librarianist), route it to standard XDG folders
      or ~/Downloads/<Category> so $HOME stays super clean!
    - If a file is already in its native folder (e.g. an Image in ~/Pictures), leave it in place.
    """
    if central_hub is not None:
        return central_hub / category

    # If an image is anywhere inside ~/Pictures, a video is inside ~/Videos, or audio is inside ~/Music, it's already home!
    for part in parent_dir.parts:
        if NATIVE_FOLDER_CATEGORY.get(part) == category:
            return None

    # If loose file dropped directly in /home/librarianist, route neatly into standard user folders
    if parent_dir == Path.home():
        home_routing = {
            "Images": Path.home() / "Pictures",
            "Video": Path.home() / "Videos",
            "Audio": Path.home() / "Music",
            "Documents": Path.home() / "Documents" / "Documents",
            "PDFs": Path.home() / "Documents" / "PDFs",
            "Archives": Path.home() / "Downloads" / "Archives",
            "Scripts_Code": Path.home() / "Documents" / "Scripts_Code",
        }
        return home_routing.get(category, Path.home() / "Downloads" / category)

    return parent_dir / category


def unique_destination(dest_dir: Path, filename: str) -> Path:
    """Ensure we never overwrite an existing file by appending _1, _2, etc."""
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    if filename.lower().endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst")):
        parts = filename.rsplit(".", 2)
        stem = parts[0]
        suffix = "." + ".".join(parts[1:])

    counter = 1
    while True:
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def notify(title: str, message: str) -> None:
    """Send a native Xubuntu desktop notification via notify-send."""
    try:
        subprocess.run(
            ["notify-send", "-a", "Auto-Janitor", "-i", "folder-saved-search", "-t", "3500", title, message],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def log_action(log_file: Path, message: str) -> None:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"Warning: could not write to log: {e}", file=sys.stderr)


def process_file(
    filepath: Path,
    parent_dir: Path,
    log_file: Path,
    central_hub: Path | None = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> bool:
    """Sort a single file into its category folder."""
    if not filepath.exists() or not filepath.is_file() or filepath.is_symlink():
        return False

    if parent_dir != Path.home() and is_protected_dir(parent_dir):
        return False

    category = get_category(filepath)
    if not category:
        return False

    dest_dir = resolve_destination_base(parent_dir, category, central_hub)
    if dest_dir is None or dest_dir == parent_dir:
        return False

    try:
        if filepath.stat().st_size == 0:
            return False
    except OSError:
        return False

    dest_path = unique_destination(dest_dir, filepath.name)

    if dry_run:
        log_action(log_file, f"[DRY-RUN] Would move: {filepath} -> {dest_path}")
        return True

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(filepath), str(dest_path))
        rel_dest = dest_path.relative_to(Path.home()) if dest_path.is_relative_to(Path.home()) else dest_path
        log_action(log_file, f"MOVED: {filepath.name} (from {parent_dir.name}) -> ~/{rel_dest}")
        if not quiet:
            notify("Auto-Janitor Sorted File", f"<b>{filepath.name}</b>\n→ ~/{rel_dest.parent}/")
            try:
                hud_script = Path(__file__).parent / "mac_hud.py"
                if hud_script.exists():
                    subprocess.run([sys.executable, str(hud_script), "flash", "--count", "1", "--delay", "0.08"], check=False)
            except Exception:
                pass
        return True
    except Exception as e:
        log_action(log_file, f"ERROR moving {filepath}: {e}")
        return False


def expand_watch_directories(root_dirs: list[Path], recursive: bool = True) -> list[Path]:
    """Build list of safe directories to watch across the user's home folders."""
    expanded: list[Path] = []
    seen: set[Path] = set()

    for root in root_dirs:
        if not root.exists() or not root.is_dir():
            continue

        # Always allow top-level $HOME (non-recursively, so we only catch loose files in ~)
        if root == Path.home():
            if root not in seen:
                expanded.append(root)
                seen.add(root)
            continue

        if is_protected_dir(root):
            continue

        if root not in seen:
            expanded.append(root)
            seen.add(root)

        if recursive:
            try:
                for sub in sorted(root.iterdir()):
                    if sub.is_dir() and not sub.is_symlink() and not is_protected_dir(sub):
                        if sub not in seen:
                            expanded.append(sub)
                            seen.add(sub)
            except OSError:
                pass

    return expanded


def sweep_existing(
    watch_dirs: list[Path],
    log_file: Path,
    central_hub: Path | None = None,
    dry_run: bool = False,
    quiet: bool = False,
) -> int:
    """Sweep existing loose files across all watched directories."""
    count = 0
    for d in watch_dirs:
        if not d.exists():
            continue
        try:
            for item in sorted(d.iterdir()):
                if item.is_file():
                    if process_file(item, d, log_file, central_hub=central_hub, dry_run=dry_run, quiet=True):
                        count += 1
        except OSError:
            pass
    if count > 0 and not quiet and not dry_run:
        notify("Auto-Janitor Sweep Complete", f"Organized {count} existing file(s) across your folders.")
    return count


class InotifyWatcher:
    """Lightweight ctypes wrapper around Linux kernel inotify."""

    def __init__(self) -> None:
        libc_name = ctypes.util.find_library("c") or "libc.so.6"
        self.libc = ctypes.CDLL(libc_name, use_errno=True)
        self.fd = self.libc.inotify_init()
        if self.fd < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"inotify_init failed: {os.strerror(errno)}")
        self.wd_to_path: dict[int, Path] = {}
        self.watched_paths: set[Path] = set()

    def add_watch(self, path: Path) -> bool:
        if path in self.watched_paths:
            return False
        path_bytes = str(path).encode("utf-8")
        wd = self.libc.inotify_add_watch(self.fd, ctypes.c_char_p(path_bytes), ctypes.c_uint32(WATCH_MASK))
        if wd < 0:
            return False
        self.wd_to_path[wd] = path
        self.watched_paths.add(path)
        return True

    def read_events(self):
        """Yield (watch_dir, filename, mask) tuples as kernel events arrive."""
        event_header_format = "iIII"
        event_header_size = struct.calcsize(event_header_format)

        while True:
            buf = os.read(self.fd, 4096)
            if not buf:
                break
            offset = 0
            while offset < len(buf):
                wd, mask, cookie, name_len = struct.unpack_from(event_header_format, buf, offset)
                offset += event_header_size
                raw_name = buf[offset : offset + name_len]
                offset += name_len

                filename = raw_name.rstrip(b"\x00").decode("utf-8", errors="replace")
                watch_dir = self.wd_to_path.get(wd)
                if watch_dir and filename:
                    yield watch_dir, filename, mask

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1


def main() -> None:
    parser = argparse.ArgumentParser(description="pcGDM Auto-Janitor: Broad User-Wide Real-Time File Organizer")
    parser.add_argument(
        "--dirs",
        nargs="+",
        default=[str(p) for p in DEFAULT_BROAD_DIRS],
        help="Directories to watch (default: ~, Downloads, Desktop, Documents, Pictures, Videos, Music, Public, Sync, LIBRARIANIST)",
    )
    parser.add_argument(
        "--central-hub",
        type=str,
        default=None,
        help="Optional single folder (e.g. ~/Sorted) where all organized files across the PC are collected",
    )
    parser.add_argument(
        "--no-subdirs",
        action="store_true",
        help="Do not automatically watch 1st-level subdirectories inside user folders",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Sweep existing files once and exit",
    )
    parser.add_argument(
        "--no-initial-sweep",
        action="store_true",
        help="Only sort newly arriving/moved files; leave existing files untouched on startup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be moved across all folders without moving any files",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Disable desktop notifications",
    )
    args = parser.parse_args()

    root_dirs = [Path(d).expanduser().resolve() for d in args.dirs]
    central_hub = Path(args.central_hub).expanduser().resolve() if args.central_hub else None
    log_file = Path.home() / ".local" / "share" / "pcGDM" / "janitor.log"

    watch_dirs = expand_watch_directories(root_dirs, recursive=not args.no_subdirs)

    if args.once or args.dry_run:
        moved = sweep_existing(watch_dirs, log_file, central_hub=central_hub, dry_run=args.dry_run, quiet=args.quiet)
        log_action(log_file, f"Broad sweep finished across {len(watch_dirs)} directories: {moved} file(s) processed.")
        return

    if not args.no_initial_sweep:
        moved = sweep_existing(watch_dirs, log_file, central_hub=central_hub, dry_run=False, quiet=args.quiet)
        if moved:
            log_action(log_file, f"Initial broad sweep moved {moved} file(s).")

    watcher = InotifyWatcher()
    for d in watch_dirs:
        if watcher.add_watch(d):
            log_action(log_file, f"Watching directory: {d}")

    try:
        for watch_dir, filename, mask in watcher.read_events():
            filepath = watch_dir / filename

            # If a new non-protected subfolder is created inside a watched user folder, auto-watch it too!
            if mask & IN_ISDIR:
                if watch_dir != Path.home() and not is_protected_dir(filepath):
                    if watcher.add_watch(filepath):
                        log_action(log_file, f"Auto-watching new subfolder: {filepath}")
                continue

            if not (mask & (IN_CLOSE_WRITE | IN_MOVED_TO)):
                continue

            # Brief 0.15s settle delay for browser rename/flush edge cases
            time.sleep(0.15)
            process_file(filepath, watch_dir, log_file, central_hub=central_hub, dry_run=False, quiet=args.quiet)
    except KeyboardInterrupt:
        log_action(log_file, "Auto-Janitor stopped by user.")
    finally:
        watcher.close()


if __name__ == "__main__":
    main()
