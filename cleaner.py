"""Deletes old files from Gradio's cache folder.

Gradio copies every file it shows in the interface (each generated video in the gallery, previews) and every file
you upload into its cache folder, and serves the copy. Wan2GP doesn't turn on Gradio's own clean-up, so the copies
are never deleted. Gradio's clean-up would also miss files left by earlier runs, and it measures age with
timedelta.seconds, which wraps every 24 hours, so this module does the clean-up itself.

The folder is the one Gradio uses: GRADIO_TEMP_DIR when it is set (Pinokio and some other launchers set it),
otherwise <system temp>/gradio. Nothing else is touched.
"""

import os
import tempfile
import threading
import time

RUN_STARTED = time.time()   # files created before this are leftovers from earlier runs
_EMPTY_DIR_GRACE = 600      # Gradio creates a folder just before copying into it: keep young empty folders
_lock = threading.Lock()


def cache_folder():
    try:
        from gradio.utils import get_upload_folder
        folder = get_upload_folder()
    except Exception:
        folder = os.environ.get("GRADIO_TEMP_DIR") or os.path.join(tempfile.gettempdir(), "gradio")
    return os.path.abspath(folder)


def unsafe_reason(folder):
    """Why this folder must not be cleaned, or None. Guards against GRADIO_TEMP_DIR pointing somewhere it shouldn't."""
    if not os.path.isdir(folder):
        return "the folder doesn't exist yet (nothing has been cached)"
    real = os.path.normcase(os.path.realpath(folder))
    if os.path.dirname(real) == real:
        return "it is a drive root"
    protected = {os.path.expanduser("~"), tempfile.gettempdir(), os.getcwd()}
    for path in protected:
        path = os.path.normcase(os.path.realpath(path))
        if real == path or path.startswith(real + os.sep):
            return f"it is, or contains, {path}"
    return None


def _created(st):
    """When the cached copy was made. shutil.copy2 keeps the original's modification time, so use the newest of the
    creation / change time and the modification time."""
    born = getattr(st, "st_birthtime", None)
    return max(born if born is not None else st.st_ctime, st.st_mtime)


def folder_stats(folder=None):
    folder = folder or cache_folder()
    count = size = 0
    for root, _dirs, files in os.walk(folder):
        for name in files:
            try:
                size += os.lstat(os.path.join(root, name)).st_size
                count += 1
            except OSError:
                pass
    return count, size


def sweep(max_age=None, created_before=None):
    """Delete cached files older than max_age seconds and/or created before the timestamp created_before.
    Returns (removed, freed_bytes, skipped, error). Files in use (Windows) are skipped and retried next time."""
    folder = cache_folder()
    if not os.path.isdir(folder):
        return 0, 0, 0, None  # nothing cached yet
    problem = unsafe_reason(folder)
    if problem:
        return 0, 0, 0, f"not cleaning {folder}: {problem}"
    now = time.time()
    removed = freed = skipped = 0
    with _lock:
        for root, _dirs, files in os.walk(folder, topdown=False):
            for name in files:
                path = os.path.join(root, name)
                try:
                    st = os.lstat(path)
                except OSError:
                    continue
                created = _created(st)
                old = ((max_age is not None and now - created > max_age)
                       or (created_before is not None and created < created_before))
                if not old:
                    continue
                try:
                    os.remove(path)
                    removed += 1
                    freed += st.st_size
                except OSError:
                    skipped += 1
            if os.path.normcase(root) != os.path.normcase(folder):
                try:
                    if not os.listdir(root) and now - os.stat(root).st_mtime > _EMPTY_DIR_GRACE:
                        os.rmdir(root)
                except OSError:
                    pass
    return removed, freed, skipped, None


def human_size(size):
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def describe(result, label):
    removed, freed, skipped, error = result
    if error:
        return f"{label}: {error}."
    text = f"{label}: removed {removed} file(s), freed {human_size(freed)}"
    if skipped:
        text += f"; {skipped} file(s) in use were skipped and will be retried"
    return text + "."


class Scheduler:
    """Background thread: clears earlier runs' leftovers once at start, then removes files older than the set age."""

    def __init__(self, get_settings, log):
        self._get = get_settings
        self._log = log
        self._wake = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="gradio-cache-cleaner", daemon=True)
            self._thread.start()

    def settings_changed(self):
        self._wake.set()

    def _run(self):
        cfg = self._get()
        if cfg["enabled"]:
            result = sweep(max_age=cfg["max_age_hours"] * 3600,
                           created_before=RUN_STARTED if cfg["clear_previous_runs"] else None)
            if result[0] or result[2] or result[3]:
                self._log(describe(result, "start-up clean"))
        while True:
            self._wake.wait(max(1, int(self._get()["check_minutes"])) * 60)
            self._wake.clear()
            cfg = self._get()
            if not cfg["enabled"]:
                continue
            try:
                result = sweep(max_age=cfg["max_age_hours"] * 3600)
                if result[0] or result[3]:
                    self._log(describe(result, "scheduled clean"))
            except Exception as error:
                self._log(f"clean failed: {error!r}")
