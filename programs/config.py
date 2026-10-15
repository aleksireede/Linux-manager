from pathlib import Path

# Repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT.joinpath("bin")
ICONS_DIR = REPO_ROOT.joinpath("icons")

# Icon paths
CHECKMARK_ICON_PATH = ICONS_DIR.joinpath("checkmark.svg")
RED_X_ICON_PATH = ICONS_DIR.joinpath("red_x.svg")
QUESTION_MARK_ICON_PATH = ICONS_DIR.joinpath("question_mark.svg")
BLUE_RIGHT_ARROW_ICON_PATH = ICONS_DIR.joinpath("blue_right_arrow.svg")

# Managed versions
BASH_EXTRA_VERSION = "1.3"
BASH_CUSTOM_VERSION = "1.4"

# System/user config paths
PACMAN_CONF_PATH = Path("/etc/pacman.conf")
PACMAN_MIRRORLIST_PATH = Path("/etc/pacman.d/mirrorlist")
PACMAN_REFLECTOR_CONFIG_PATH = Path("/etc/xdg/reflector/reflector.conf")
XORG_KEYBOARD_CONF_PATH = Path("/etc/X11/xorg.conf.d/00-keyboard.conf")
FSTAB_PATH = Path("/etc/fstab")

BASH_EXTRA_PATH = Path.home().joinpath(".bash_extra")
BASHRC_PATH = Path.home().joinpath(".bashrc")
FISH_CONFIG_PATH = Path.home().joinpath(".config", "fish", "config.fish")
ZEROCONF_DEST_PATH = Path.home().joinpath(
    ".config", "pipewire", "pipewire.conf.d", "my-zeroconf-discover.conf"
).resolve()
AIRPLAY_DEST_PATH = Path.home().joinpath(
    ".config", "pipewire", "pipewire.conf.d", "raop-discover.conf"
).resolve()

# Template/source file paths
BASH_EXTRA_TEMPLATE_PATH = BIN_DIR.joinpath("bash_extra.sh")
BASH_CUSTOM_TEMPLATE_PATH = BIN_DIR.joinpath("bashrc.sh")
ZEROCONF_TEMPLATE_PATH = BIN_DIR.joinpath("zeroconf.txt")
AIRPLAY_TEMPLATE_PATH = BIN_DIR.joinpath("airplay.txt")
XORG_KEYBOARD_TEMPLATE_PATH = BIN_DIR.joinpath("xorg_keyboard_layout.txt")
REFLECTOR_TEMPLATE_PATH = BIN_DIR.joinpath("reflector.txt")
