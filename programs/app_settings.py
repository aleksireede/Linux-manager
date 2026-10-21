"""Persistent application preferences."""

from PyQt5.QtCore import QSettings


SETTINGS_ORGANIZATION = "Linux-Manager"
SETTINGS_APPLICATION = "Linux-Manager"
PACKAGE_CONFLICT_POLICY_KEY = "apps/package_conflict_policy"
LEGACY_FEDORA_CONFLICT_POLICY_KEY = "apps/fedora_conflict_policy"
ACCENT_COLOR_KEY = "appearance/accent_color"
BACKGROUND_COLOR_KEY = "appearance/background_color"
EXTERNAL_TERMINAL_KEY = "appearance/external_terminal"


def app_settings():
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def package_conflict_policy():
    settings = app_settings()
    policy = settings.value(PACKAGE_CONFLICT_POLICY_KEY)
    if policy is None:
        policy = settings.value(LEGACY_FEDORA_CONFLICT_POLICY_KEY, "skip")
    return policy if policy in {"skip", "ask", "replace"} else "skip"


def set_package_conflict_policy(policy):
    if policy not in {"skip", "ask", "replace"}:
        raise ValueError("Package conflict policy must be 'skip', 'ask', or 'replace'.")
    settings = app_settings()
    settings.setValue(PACKAGE_CONFLICT_POLICY_KEY, policy)
    settings.sync()


def fedora_conflict_policy():
    """Compatibility alias for the original Fedora-only setting name."""
    return package_conflict_policy()


def set_fedora_conflict_policy(policy):
    """Compatibility alias for the original Fedora-only setting name."""
    set_package_conflict_policy(policy)


def _valid_color(value, default):
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        return default
    try:
        int(value[1:], 16)
    except ValueError:
        return default
    return value.lower()


def accent_color():
    return _valid_color(app_settings().value(ACCENT_COLOR_KEY, "#007acc"), "#007acc")


def set_accent_color(color):
    color = _valid_color(color, None)
    if color is None:
        raise ValueError("Accent color must be a hex color in #RRGGBB format.")
    settings = app_settings()
    settings.setValue(ACCENT_COLOR_KEY, color.lower())
    settings.sync()


def background_color():
    return _valid_color(app_settings().value(BACKGROUND_COLOR_KEY, "#1e1e1e"), "#1e1e1e")


def set_background_color(color):
    color = _valid_color(color, None)
    if color is None:
        raise ValueError("Background color must be a hex color in #RRGGBB format.")
    settings = app_settings()
    settings.setValue(BACKGROUND_COLOR_KEY, color)
    settings.sync()


def external_terminal():
    return app_settings().value(EXTERNAL_TERMINAL_KEY, "auto") or "auto"


def set_external_terminal(terminal):
    if not isinstance(terminal, str) or not terminal.strip():
        raise ValueError("External terminal must be a non-empty terminal identifier.")
    settings = app_settings()
    settings.setValue(EXTERNAL_TERMINAL_KEY, terminal.strip())
    settings.sync()
