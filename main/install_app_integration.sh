#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
LAUNCHER_BIN="/usr/local/bin/linux-manager"
UPDATER_BIN="/usr/local/bin/linux-manager-update"
DESKTOP_FILE="/usr/share/applications/linux-manager.desktop"
ICON_FILE="/usr/share/icons/hicolor/scalable/apps/linux-manager.svg"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

run_root() {
  if [[ "$EUID" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

cat > "$TEMP_DIR/linux-manager" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$INSTALL_DIR/main/main.py" "\$@"
EOF

cat > "$TEMP_DIR/linux-manager-update" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec bash "$INSTALL_DIR/main/update.sh" "\$@"
EOF

cat > "$TEMP_DIR/linux-manager.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Linux-Manager
Comment=Linux setup and application manager
Exec=$LAUNCHER_BIN
TryExec=$LAUNCHER_BIN
Icon=linux-manager
Terminal=false
Categories=System;Settings;
StartupNotify=true
EOF

run_root install -Dm755 "$TEMP_DIR/linux-manager" "$LAUNCHER_BIN"
run_root install -Dm755 "$TEMP_DIR/linux-manager-update" "$UPDATER_BIN"
run_root install -Dm644 "$INSTALL_DIR/icons/linux-manager.svg" "$ICON_FILE"
run_root install -Dm644 "$TEMP_DIR/linux-manager.desktop" "$DESKTOP_FILE"

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  run_root gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  run_root update-desktop-database -q /usr/share/applications || true
fi

echo "Installed Linux-Manager launcher, updater, desktop entry, and icon."
