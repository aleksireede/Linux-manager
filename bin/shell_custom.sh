# Shared Linux-Manager shell configuration for Bash and Zsh.

export EDITOR=nano
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland}"
export PATH="$PATH:$HOME/.local/bin"

if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    if [ -n "${UID:-}" ]; then
        _lm_uid="$UID"
    else
        _lm_uid="$(id -u)"
    fi
    export XDG_RUNTIME_DIR="/run/user/$_lm_uid"
fi
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"

if command -v pacman >/dev/null 2>&1; then
    export QT_PLUGIN_PATH="${QT_PLUGIN_PATH:-/usr/lib/qt/plugins}"
fi

if [ -x /usr/bin/starship ]; then
    if [ -n "${BASH_VERSION:-}" ]; then
        eval "$(/usr/bin/starship init bash)"
    elif [ -n "${ZSH_VERSION:-}" ]; then
        eval "$(/usr/bin/starship init zsh)"
    fi
fi

alias localip='ip -br addr'
alias extip='dig -4 TXT +short o-o.myaddr.l.google.com @ns1.google.com'
alias path='printf "%s\n" "$PATH" | tr ":" "\n"'

if command -v ugrep >/dev/null 2>&1; then
    alias grep='ugrep --color=auto'
    alias fgrep='ugrep -F --color=auto'
    alias egrep='ugrep -E --color=auto'
    alias hgrep='history | ugrep'
else
    alias hgrep='history | grep'
fi

if command -v fastfetch >/dev/null 2>&1; then
    _lm_fetch=fastfetch
elif command -v screenfetch >/dev/null 2>&1; then
    _lm_fetch=screenfetch
else
    _lm_fetch=
fi

ff() {
    [ -n "$_lm_fetch" ] || return 0
    if command -v lolcat >/dev/null 2>&1; then
        "$_lm_fetch" | lolcat
    else
        "$_lm_fetch"
    fi
}
alias neofetch='ff'

mnt() {
    mount |
        awk '{ printf "%s\t%s\n", $1, $3 }' |
        column -t |
        grep '^/dev/' |
        sort
}

if command -v eza >/dev/null 2>&1; then
    alias ls='eza --all --long --group-directories-first --icons=auto'
    alias la='eza -a --group-directories-first --icons=auto'
    alias ll='eza -l --group-directories-first --icons=auto'
    alias lt='eza -aT --group-directories-first --icons=auto'
    alias l.='eza -ald .* --icons=auto'
fi

if command -v bat >/dev/null 2>&1; then
    alias cat='bat --style=header,snip,changes'
fi
if [ ! -x /usr/bin/yay ] && [ -x /usr/bin/paru ]; then
    alias yay='paru'
fi

alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias .....='cd ../../../..'
alias ......='cd ../../../../..'
mkcd() { mkdir -p "$1" && cd "$1"; }

alias cp='cp -iv'
alias mv='mv -iv'
alias mkdir='mkdir -pv'
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias cls='clear'
alias dir='dir --color=auto'
alias vdir='vdir --color=auto'

tarnow() {
    _lm_archive="$1"
    shift
    tar -acf "${_lm_archive}.tar.gz" "$@"
}
alias untar='tar -xf'

extract() {
    if [ ! -f "$1" ]; then
        echo "File not found."
        return 1
    fi
    case "$1" in
        *.tar.bz2) tar xjf "$1" ;;
        *.tar.gz) tar xzf "$1" ;;
        *.tar.xz) tar xJf "$1" ;;
        *.tar.zst) tar --zstd -xf "$1" ;;
        *.tar) tar xf "$1" ;;
        *.zip) unzip "$1" ;;
        *.7z) 7z x "$1" ;;
        *.rar) unrar x "$1" ;;
        *) echo "Unsupported archive."; return 1 ;;
    esac
}

if command -v dnf5 >/dev/null 2>&1; then
    alias update='sudo dnf5 upgrade --refresh -y'
    alias install='sudo dnf5 install -y'
    alias remove='sudo dnf5 remove -y'
    alias listpkg='dnf5 repoquery --userinstalled --qf "%{name}"'
    alias upd='sudo dnf5 upgrade --refresh -y'
    cleanup() { sudo dnf5 autoremove -y; }
elif command -v dnf >/dev/null 2>&1; then
    alias update='sudo dnf upgrade --refresh -y'
    alias install='sudo dnf install -y'
    alias remove='sudo dnf remove -y'
    alias listpkg='dnf repoquery --userinstalled --qf "%{name}"'
    alias upd='sudo dnf upgrade --refresh -y'
    cleanup() { sudo dnf autoremove -y; }
elif command -v apt >/dev/null 2>&1; then
    alias update='sudo apt update && sudo apt upgrade -y'
    alias install='sudo apt install -y'
    alias remove='sudo apt remove -y'
    alias listpkg='apt list --installed'
elif command -v paru >/dev/null 2>&1; then
    alias update='paru -Syu --skipreview --needed'
    alias install='paru -S --skipreview --needed'
    alias remove='paru -Rns'
    alias listpkg='paru -Qenq'
    alias listaur='paru -Qemq'
    alias upd='paru -Syu --skipreview --needed'
elif command -v yay >/dev/null 2>&1; then
    alias update='yay -Syu --skipreview --needed'
    alias install='yay -S --skipreview --needed'
    alias remove='yay -Rns'
    alias listpkg='yay -Qenq'
    alias listaur='yay -Qemq'
    alias upd='yay -Syu --skipreview --needed'
elif command -v pikaur >/dev/null 2>&1; then
    alias update='pikaur -Syu'
    alias install='pikaur -S --needed'
    alias remove='pikaur -Rns'
    alias listpkg='pikaur -Qenq'
    alias listaur='pikaur -Qemq'
elif command -v pakku >/dev/null 2>&1; then
    alias update='pakku -Syu'
    alias install='pakku -S --needed'
    alias remove='pakku -Rns'
    alias listpkg='pakku -Qenq'
    alias listaur='pakku -Qemq'
elif command -v aura >/dev/null 2>&1; then
    alias update='aura -Syu && aura -Au'
    alias install='aura -S --needed'
    alias remove='aura -Rns'
    alias listpkg='aura -Qenq'
    alias listaur='aura -Qmq'
elif command -v pacman >/dev/null 2>&1; then
    alias update='sudo pacman -Syu'
    alias install='sudo pacman -S --needed'
    alias remove='sudo pacman -Rns'
    alias listpkg='pacman -Qenq'
    alias upd='sudo pacman -Syu'
    alias grubup='sudo update-grub'
    alias rmpkg='sudo pacman -Rdd'
    fixpacman() { sudo rm -f /var/lib/pacman/db.lck; }
    cleanup() { pacman -Qtdq | xargs -r sudo pacman -Rns; }
fi

if command -v pacman >/dev/null 2>&1 && command -v reflector >/dev/null 2>&1; then
    alias mirror='sudo reflector --country Finland,Sweden,Estonia,Germany --protocol https --latest 20 --sort rate --save /etc/pacman.d/mirrorlist'
    alias mirrorfi='sudo reflector --country Finland --protocol https --latest 10 --sort rate --save /etc/pacman.d/mirrorlist'
    alias mirrorworld='sudo reflector --protocol https --latest 30 --sort rate --save /etc/pacman.d/mirrorlist'
fi

alias hw='hwinfo --short'
alias psmem='ps auxf | sort -nr -k4'
alias psmem10='ps auxf | sort -nr -k4 | head'
alias jctl='journalctl -p3 -xb'
if command -v pacman >/dev/null 2>&1; then
    alias big="expac -H M '%m\t%n' | sort -h | nl"
    alias gitpkg='pacman -Q | grep "-git" | wc -l'
    alias rip="expac --timefmt='%Y-%m-%d %T' '%l\t%n %v' | sort | tail -200 | nl"
elif command -v dnf5 >/dev/null 2>&1; then
    alias big='dnf5 repoquery --installed --qf "%{size}\t%{name}" | sort -h | nl'
    alias gitpkg='rpm -qa | grep -- "-git" | wc -l'
elif command -v dnf >/dev/null 2>&1; then
    alias big='dnf repoquery --installed --qf "%{size}\t%{name}" | sort -h | nl'
    alias gitpkg='rpm -qa | grep -- "-git" | wc -l'
fi

if command -v pacman >/dev/null 2>&1; then
    alias apt='man pacman'
    alias apt-get='man pacman'
elif command -v dnf5 >/dev/null 2>&1; then
    alias apt='man dnf5'
    alias apt-get='man dnf5'
elif command -v dnf >/dev/null 2>&1; then
    alias apt='man dnf'
    alias apt-get='man dnf'
fi
alias please='sudo'
alias helpme='cht.sh --shell'
if command -v pacdiff >/dev/null 2>&1; then
    alias pacdiff='sudo -H DIFFPROG=meld pacdiff'
fi

if command -v fortune >/dev/null 2>&1 &&
   command -v cowsay >/dev/null 2>&1 &&
   command -v lolcat >/dev/null 2>&1; then
    clear
    fortune | cowsay -f tux | lolcat
fi

unset _lm_fetch _lm_uid _lm_archive
