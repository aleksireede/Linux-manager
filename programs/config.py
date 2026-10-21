from pathlib import Path

# -----------------------------------------------------------------------------
# App values
# -----------------------------------------------------------------------------
icon_height = 20
icon_width = 20

# -----------------------------------------------------------------------------
# Directories
# -----------------------------------------------------------------------------
dir_app_root = Path(__file__).resolve().parent.parent
dir_bin = dir_app_root.joinpath("bin")
dir_icons = dir_app_root.joinpath("icons")

# -----------------------------------------------------------------------------
# Icons
# -----------------------------------------------------------------------------
icon_checkmark = dir_icons.joinpath("checkmark.svg")
icon_red_cross = dir_icons.joinpath("red_x.svg")
icon_question_mark = dir_icons.joinpath("question_mark.svg")
icon_blue_arrow = dir_icons.joinpath("blue_right_arrow.svg")

# -----------------------------------------------------------------------------
# Versions
# -----------------------------------------------------------------------------
shell_custom_ver = "1.0"

# -----------------------------------------------------------------------------
# Config paths
# -----------------------------------------------------------------------------
file_pacman_conf = Path("/etc/pacman.conf")
file_pacman_mirrorlist = Path("/etc/pacman.d/mirrorlist")
file_reflector_conf = Path("/etc/xdg/reflector/reflector.conf")
file_xorg_kb_conf = Path("/etc/X11/xorg.conf.d/00-keyboard.conf")
file_fstab = Path("/etc/fstab")
file_bashrc = Path.home().joinpath(".bashrc")
file_zshrc = Path.home().joinpath(".zshrc")
file_shell_custom = Path.home().joinpath(".shell_custom")
file_fish_sh_conf = Path.home().joinpath(".config", "fish", "config.fish")
file_zeroconf_pw = Path.home().joinpath(
    ".config", "pipewire", "pipewire.conf.d", "my-zeroconf-discover.conf"
).resolve()
file_airplay_pw = Path.home().joinpath(
    ".config", "pipewire", "pipewire.conf.d", "raop-discover.conf"
).resolve()

# -----------------------------------------------------------------------------
# Config contents
# -----------------------------------------------------------------------------
file_shell_custom_content = dir_bin.joinpath("shell_custom.sh")
file_zeroconf_content = dir_bin.joinpath("zeroconf.txt")
file_airplay_content = dir_bin.joinpath("airplay.txt")
file_xorg_kb_content = dir_bin.joinpath("xorg_keyboard_layout.txt")
file_reflector_conf_content = dir_bin.joinpath("reflector.txt")
