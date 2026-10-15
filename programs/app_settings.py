"""Persistent application preferences."""

from PyQt5.QtCore import QSettings


SETTINGS_ORGANIZATION = "Linux-Manager"
SETTINGS_APPLICATION = "Linux-Manager"
FEDORA_CONFLICT_POLICY_KEY = "apps/fedora_conflict_policy"


def app_settings():
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def fedora_conflict_policy():
    policy = app_settings().value(FEDORA_CONFLICT_POLICY_KEY, "skip")
    return policy if policy in {"skip", "replace"} else "skip"


def set_fedora_conflict_policy(policy):
    if policy not in {"skip", "replace"}:
        raise ValueError("Fedora conflict policy must be 'skip' or 'replace'.")
    settings = app_settings()
    settings.setValue(FEDORA_CONFLICT_POLICY_KEY, policy)
    settings.sync()
