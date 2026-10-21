import subprocess
from pathlib import Path

from programs.config import (
    file_zeroconf_pw,
    file_airplay_pw,
    file_xorg_kb_conf,
    file_pacman_mirrorlist,
    file_reflector_conf,
    file_zeroconf_content,
    file_airplay_content,
    file_xorg_kb_content,
    file_reflector_conf_content,
)
from programs.installer_logic import command_exists
from scripts.text_writer import write_text

# files
zeroconf_dest_path = file_zeroconf_pw
airplay_dest_path = file_airplay_pw
xorg_keyboard_conf_path = file_xorg_kb_conf
pacman_mirrorlist_path = file_pacman_mirrorlist
pacman_reflector_config_path = file_reflector_conf

# texts
zeroconf_text = file_zeroconf_content.read_text()
airplay_text = file_airplay_content.read_text()
xorg_keyboard_conf_text = file_xorg_kb_content.read_text()
reflector_text = file_reflector_conf_content.read_text()


def reflector_service_timer():
    """
    Enable reflector service timer
    To automatically update pacman mirrorlist
    """
    if pacman_reflector_config_path.exists():
        return
    else:
        if not command_exists("reflector"):
            return
        write_config_file(pacman_reflector_config_path,
                          reflector_text, True, True)
        command = ["pkexec", "systemctl", "enable", "--now", "reflector.timer"]
        subprocess.run(command, check=True)


def git_keystore():
    result = subprocess.run(
        ["git", "config", "--global", "credential.helper"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "Failed to read git credential.helper")

    current_helper = result.stdout.strip()
    if current_helper == "store":
        print("Git config not updated")
        return

    try:
        subprocess.run(
            ["git", "config", "--global", "credential.helper", "store"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.strip() or "Failed to update git credential.helper") from e
    print("Git config updated")


def sudo_write_text(file: Path, text: str):
    script_path = Path(__file__).resolve().parent / "text_writer.py"
    subprocess.run([
        "pkexec",
        "python3",
        str(script_path),
        str(file),
        text
    ], check=True)


def write_config_file(file: Path, content: str, sudo=False, remove=False):
    """
    Write config file
    Returns True if file was written
    :rtype: bool
    :param file:
    :param content:
    :param sudo:
    :param remove:
    """
    if file.exists():
        return False
    else:
        if remove:
            file.unlink()
        if sudo:
            sudo_write_text(file, content)
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            if not file.exists():
                file.touch()
            write_text(file, content)
        return True


def zeroconf_discover_pw():
    """
    Write zeroconf discover config file
    Then load zeroconf discover module
    """
    if zeroconf_dest_path.exists():
        return
    write_config_file(zeroconf_dest_path, zeroconf_text)
    subprocess.run(["pactl", "load-module", "module-zeroconf-discover"])


def airplay_discover_pw():
    """
    Write airplay discover config file
    Then load airplay discover module
    """
    if airplay_dest_path.exists():
        return
    write_config_file(airplay_dest_path, airplay_text)
    subprocess.run(["pactl", "load-module", "module-raop-discover"])


def xorg_keyboard_layout_fi():
    if xorg_keyboard_conf_path.exists():
        return
    write_config_file(xorg_keyboard_conf_path, xorg_keyboard_conf_text, True)
