import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from programs.config import (
    PACMAN_CONF_PATH,
    BASH_EXTRA_PATH,
    BASHRC_PATH,
    BASH_EXTRA_VERSION,
    BASH_CUSTOM_TEMPLATE_PATH,
    BASH_EXTRA_TEMPLATE_PATH,
    BASH_CUSTOM_VERSION,
)

# Arch / Pacman config
pacman_conf = PACMAN_CONF_PATH
pacman_sync_dir = Path("/var/lib/pacman/sync")
multilib_disabled = "#[multilib]\n#Include = /etc/pacman.d/mirrorlist"
multilib_enabled = "[multilib]\nInclude = /etc/pacman.d/mirrorlist"

# Bash config
bash_extra_path = BASH_EXTRA_PATH
bashrc_path = BASHRC_PATH
bashrc_extra_text = 'if [ -f ~/.bash_extra ]; then\n. ~/.bash_extra\nfi'
bash_extra_version = BASH_EXTRA_VERSION
_bash_extra_body = BASH_EXTRA_TEMPLATE_PATH.read_text().rstrip()
bash_extra_text = (
    f"# Managed by Linux-Manager\n"
    f"# linux-manager-bash-extra-version: {bash_extra_version}\n\n"
    f"{_bash_extra_body}\n"
)
bash_custom_version = BASH_CUSTOM_VERSION
_bash_custom_body = BASH_CUSTOM_TEMPLATE_PATH.read_text().rstrip()
bash_custom_text = (
    f"# Managed by Linux-Manager\n"
    f"# linux-manager-bash-extra-version: {bash_custom_version}\n\n"
    f"{_bash_custom_body}\n"
)


# todo: find text and then read the whole line to edit eg. ParallelDownload=5 to edit the number
def check_if_text_exists(file: Path, search_text: str) -> bool:
    """
    Checks if text exists in file.
    :param file: the file to check
    :param search_text: the text to search for
    """
    data = file.read_text()

    if search_text not in data:
        print(f"Text not found: '{search_text}' — skipping.")
        return False
    else:
        return True


def sudo_replace_text(file: Path, search_text: str, replace_text: str) -> None:
    script_path = Path(__file__).resolve().parent / \
                  "../scripts/text_writer.py"
    subprocess.run([
        "pkexec",
        "python3",
        str(script_path),
        file,
        search_text,
        replace_text
    ], check=True)


def sudo_write_text(file: Path, text: str) -> None:
    script_path = Path(__file__).resolve().parent / \
                  "../scripts/text_writer.py"
    subprocess.run([
        "pkexec",
        "python3",
        str(script_path),
        file,
        text
    ], check=True)


def update_bash_custom() -> None:
    """
    Updates custom bash configuration
    """
    if bashrc_path.exists():
        print(f"Updating ~/.bash_extra to version {bash_custom_version}...")
    else:
        print(f"Installing ~/.bash_extra version {bash_custom_version}...")
    bashrc_path.write_text(bash_custom_text)


def enable_bash_extra() -> bool:
    """
    Enables extra bash configuration to add the bash_extra file

    Returns True if extra bash configuration was enabled
    """
    changed = False

    # Enable ~/.bash_extra source line in ~/.bashrc
    if not bashrc_path.exists():
        bashrc_path.touch()
    bashrc_data = bashrc_path.read_text()
    if bashrc_extra_text not in bashrc_data:
        with open(bashrc_path, "a") as f:
            f.write("\n" + bashrc_extra_text + "\n")
        changed = True

    if changed:
        print("Enabled bash extra in ~/.bashrc")
    return changed


def write_bash_extra() -> None:
    """
    Enables extra bash configuration to add the bash extra file
    If it already exists then it is updated.
    """
    # Backwards-compatible wrapper for full overwrite updates.
    update_bash_extra()


def update_bash_extra() -> None:
    """
    Overwrite ~/.bash_extra with the latest managed template and version header.
    """
    if bash_extra_path.exists():
        print(f"Updating ~/.bash_extra to version {bash_extra_version}...")
    else:
        print(f"Installing ~/.bash_extra version {bash_extra_version}...")
    bash_extra_path.write_text(bash_extra_text)


def check_multilib() -> bool:
    """
    Checks if multilib is enabled.
    Returns True if multilib configuration was enabled
    """
    if pacman_conf.exists():
        if multilib_enabled in pacman_conf.read_text():
            return True
        else:
            return False
    return False


def enable_multilib() -> None:
    # Enable multilib in pacman.conf
    if pacman_conf.exists():
        print("Enabling Multilib...")
        sudo_replace_text(pacman_conf, multilib_disabled, multilib_enabled)


def disable_multilib() -> None:
    # Disable multilib in pacman.conf
    if pacman_conf.exists():
        print("Disabling Multilib...")
        sudo_replace_text(pacman_conf, multilib_enabled, multilib_disabled)


def check_pacman_color() -> bool:
    """
    Check whether pacman color is enabled.
    Returns True if pacman color was enabled
    """
    if pacman_conf.exists():
        if "#Color" in pacman_conf.read_text():
            return False
        else:
            return True
    return False


def pacman_enable_color() -> None:
    # Enable pacman colored output
    if pacman_conf.exists():
        print("Enabling color in pacman...")
        sudo_replace_text(pacman_conf, "#Color", "Color")


def pacman_disable_color() -> None:
    # Disable pacman colored output
    if pacman_conf.exists():
        print("Enabling color in pacman...")
        sudo_replace_text(pacman_conf, "Color", "#Color")


def pacman_check_parallel_downloads() -> bool:
    """
    Checks if pacman parallel downloads is enabled.
    Returns True if pacman parallel downloads was enabled
    """
    if pacman_conf.exists():
        if "#ParallelDownloads=5" in pacman_conf.read_text():
            return False
        else:
            return True
    return False


def pacman_enable_parallel_downloads() -> None:
    # Enable parallel downloads
    if pacman_conf.exists():
        sudo_replace_text(pacman_conf, "#ParallelDownloads=5", "ParallelDownloads=5")


def pacman_disable_parallel_downloads() -> None:
    # Disable parallel downloads
    if pacman_conf.exists():
        sudo_replace_text(pacman_conf, "ParallelDownloads=5", "#ParallelDownloads=5")


def pacman_check_database_refreshed(max_age_hours=24):
    """
    Checks whether pacman's sync databases were refreshed recently.
    Returns True when at least one sync database exists and the newest one
    was updated within the allowed age window.
    todo: add return type
    """
    if not pacman_sync_dir.exists():
        return False

    db_files = list(pacman_sync_dir.glob("*.db"))
    if not db_files:
        return False

    newest_mtime = max(db_file.stat().st_mtime for db_file in db_files)
    newest_refresh = datetime.fromtimestamp(newest_mtime)
    return newest_refresh >= datetime.now() - timedelta(hours=max_age_hours)


def pacman_refresh_database() -> None:
    """Refresh pacman's package databases."""
    subprocess.run(
        ["pkexec", "pacman", "-Sy"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
