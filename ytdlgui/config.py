"""Sauvegarde et chargement des réglages (settings.json)."""
import json
import os


def settings_path(app_dir):
    return os.path.join(app_dir, "settings.json")


def load_settings(app_dir):
    try:
        with open(settings_path(app_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(app_dir, data):
    try:
        with open(settings_path(app_dir), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
