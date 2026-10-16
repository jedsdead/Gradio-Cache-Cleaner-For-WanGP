"""Plugin settings, persisted to settings.json next to this file."""

import json
import os

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULTS = {
    "enabled": True,
    "max_age_hours": 12,           # cached files older than this are deleted
    "check_minutes": 30,           # how often to check
    "clear_previous_runs": True,   # at start-up, delete everything left by earlier runs
}

_settings = dict(DEFAULTS)


def load():
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        _settings.update({key: stored[key] for key in DEFAULTS if key in stored})
    except FileNotFoundError:
        pass
    except Exception as error:
        print(f"[Gradio Cache Cleaner] could not read settings.json, using defaults: {error}")


def save():
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as handle:
            json.dump(_settings, handle, indent=2)
    except Exception as error:
        print(f"[Gradio Cache Cleaner] could not save settings.json: {error}")


def get():
    return dict(_settings)


def set_value(key, value):
    if key in ("max_age_hours", "check_minutes"):
        value = max(1, int(value))
    _settings[key] = value
    save()
