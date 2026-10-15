# ~/.bash_extra

# -----------------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------------

export EDITOR=nano
export QT_QPA_PLATFORM=wayland
if command -v pacman >/dev/null 2>&1; then
    export QT_PLUGIN_PATH=/usr/lib/qt/plugins
fi

export XDG_RUNTIME_DIR="/run/user/$UID"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"

# -----------------------------------------------------------------------------
# Network
# -----------------------------------------------------------------------------

alias localip='ip -br addr'
alias extip='dig -4 TXT +short o-o.myaddr.l.google.com @ns1.google.com'

# -----------------------------------------------------------------------------
# PATH
# -----------------------------------------------------------------------------

alias path='echo "$PATH" | tr ":" "\n"'

# -----------------------------------------------------------------------------
# History
# -----------------------------------------------------------------------------

alias hgrep='history | ugrep'

# -----------------------------------------------------------------------------
# Mounts
# -----------------------------------------------------------------------------

mnt() {
    mount |
        awk '{ printf "%s\t%s\n",$1,$3 }' |
        column -t |
        grep '^/dev/' |
        sort
}

# -----------------------------------------------------------------------------
# Fastfetch
# -----------------------------------------------------------------------------

alias ff='fastfetch | lolcat'
alias neofetch='fastfetch | lolcat'

# -----------------------------------------------------------------------------
# Paru
# -----------------------------------------------------------------------------

if command -v dnf5 >/dev/null 2>&1; then
    alias update='sudo dnf5 upgrade --refresh -y'
    alias install='sudo dnf5 install -y'
    alias remove='sudo dnf5 remove -y'
    alias listpkg='dnf5 repoquery --userinstalled --qf "%{name}"'
elif command -v dnf >/dev/null 2>&1; then
    alias update='sudo dnf upgrade --refresh -y'
    alias install='sudo dnf install -y'
    alias remove='sudo dnf remove -y'
    alias listpkg='dnf repoquery --userinstalled --qf "%{name}"'
elif command -v paru >/dev/null 2>&1; then
    alias update='paru -Syu --skipreview --needed'
    alias install='paru -S --skipreview --needed'
    alias remove='paru -Rns'
    alias listpkg='paru -Qenq'
    alias listaur='paru -Qemq'
elif command -v pacman >/dev/null 2>&1; then
    alias update='sudo pacman -Syu'
    alias install='sudo pacman -S --needed'
    alias remove='sudo pacman -Rns'
    alias listpkg='pacman -Qenq'
fi

# -----------------------------------------------------------------------------
# Startup
# -----------------------------------------------------------------------------

if command -v fortune >/dev/null &&
   command -v cowsay >/dev/null &&
   command -v lolcat >/dev/null; then

    clear
    fortune | cowsay -f tux | lolcat

fi
