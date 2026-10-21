import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from programs.config import (
    file_pacman_conf,
    file_bashrc,
    file_zshrc,
    file_shell_custom,
    file_shell_custom_content,
    shell_custom_ver,
)
from programs.shell_frameworks import default_shell
import re

# Arch / Pacman config
pacman_conf = file_pacman_conf
pacman_sync_dir = Path("/var/lib/pacman/sync")
multilib_disabled = "#[multilib]\n#Include = /etc/pacman.d/mirrorlist"
multilib_enabled = "[multilib]\nInclude = /etc/pacman.d/mirrorlist"

# Shared config loaded from either Bash or Zsh startup.
SHELL_CONFIGS = {
    "bash": {"rc_path": file_bashrc},
    "zsh": {"rc_path": file_zshrc},
}


def shell_config():
    shell = default_shell()
    if shell not in SHELL_CONFIGS:
        raise RuntimeError(f"Shell config actions support Bash and Zsh; the default shell is '{shell or 'unknown'}'.")
    return shell, SHELL_CONFIGS[shell]


def shell_custom_path():
    return file_shell_custom


def shell_custom_version():
    return shell_custom_ver


def get_shell_installed_version(kind="custom"):
    if kind == "extra":
        return None
    if not file_shell_custom.exists():
        return None
    match = re.search(r"^#\s*linux-manager-shell-custom-version:\s*(.+?)\s*$", file_shell_custom.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1).strip() if match else None


def is_shell_custom_enabled():
    _, config = shell_config()
    rc_path = config["rc_path"]
    if not rc_path.exists():
        return False
    content = rc_path.read_text(encoding="utf-8")
    return file_shell_custom.name in content and "Linux-Manager shell config" in content


def _ensure_shell_config_hook(shell, config):
    rc_path = config["rc_path"]
    original = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    start_marker = "# >>> Linux-Manager shell config >>>"
    end_marker = "# <<< Linux-Manager shell config <<<"
    content = original
    for old_start, old_end in (
        (start_marker, end_marker),
        ("# >>> Linux-Manager shell configs >>>", "# <<< Linux-Manager shell configs <<<"),
    ):
        start = content.find(old_start)
        if start >= 0:
            end = content.find(old_end, start)
            if end >= 0:
                end += len(old_end)
                content = content[:start].rstrip() + "\n\n" + content[end:].lstrip()
            else:
                content = content[:start].rstrip()

    hook = "\n".join([
        start_marker,
        f'if [ -r "$HOME/{file_shell_custom.name}" ]; then',
        f'    . "$HOME/{file_shell_custom.name}"',
        "fi",
        end_marker,
    ])
    backup_path = rc_path.with_name(rc_path.name + ".linux-manager-backup")
    if rc_path.exists() and not backup_path.exists():
        import shutil
        shutil.copy2(rc_path, backup_path)
    rc_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"{content}\n\n{hook}" if content else hook
    rc_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def update_shell_custom():
    shell, config = shell_config()
    target = file_shell_custom
    version = shell_custom_ver
    print(f"{'Updating' if target.exists() else 'Installing'} {target.name} version {version}...")
    body = file_shell_custom_content.read_text(encoding="utf-8").rstrip()
    target.write_text(
        f"# Managed by Linux-Manager\n# linux-manager-shell-custom-version: {version}\n\n{body}\n",
        encoding="utf-8",
    )
    _ensure_shell_config_hook(shell, config)


def enable_shell_custom():
    shell, config = shell_config()
    rc_path = config["rc_path"]
    previous = rc_path.read_text(encoding="utf-8") if rc_path.exists() else ""
    _ensure_shell_config_hook(shell, config)
    changed = previous != rc_path.read_text(encoding="utf-8")
    if changed:
        print(f"Enabled shared shell config in {rc_path.name}")
    return changed


def sudo_replace_text(file: Path, search_text: str, replace_text: str) -> None:
    script_path = Path(__file__).resolve().parent / "../scripts/text_writer.py"
    subprocess.run(
        ["pkexec", "python3", str(script_path), file, search_text, replace_text],
        check=True,
    )


def update_bash_custom():
    update_shell_custom()


def enable_bash_extra():
    return enable_shell_custom()


def write_bash_extra():
    update_shell_custom()


def update_bash_extra():
    update_shell_custom()

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
