#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/aleksireede/arch-mysetup.git"
REPO_OWNER="aleksireede"
REPO_NAME="arch-mysetup"
INSTALL_DIR="/opt/linux-manager"
LEGACY_INSTALL_DIR="/opt/arch-mysetup"
LAUNCHER_BIN="/usr/local/bin/linux-manager"
UPDATER_BIN="/usr/local/bin/linux-manager-update"
DESKTOP_FILE="/usr/share/applications/linux-manager.desktop"
APP_NAME="Linux-Manager"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
LATEST_RELEASE_API="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"

if command -v pacman >/dev/null 2>&1
then
    sudo pacman -S --needed --noconfirm \
    python python-pip python-pyyaml python-pyqt5 python-pyqt6 \
    qt5-base qt5-xcb-private-headers libxcb gnome-console git curl

elif command -v dnf >/dev/null 2>&1
then
    sudo dnf install -y \
    python3 python3-pip python3-pyyaml python3-qt5 \
    qt5-qtbase qt5-qtx11extras libxcb-devel gnome-terminal git \
    curl
fi

echo "Checking installation directory..."
if [[ ! -e "$INSTALL_DIR" && -d "$LEGACY_INSTALL_DIR/.git" ]]; then
  echo "Migrating existing installation from $LEGACY_INSTALL_DIR"
  sudo mv "$LEGACY_INSTALL_DIR" "$INSTALL_DIR"
fi
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Existing git install found: $INSTALL_DIR"
elif [[ -e "$INSTALL_DIR" ]]; then
  echo "Refusing to overwrite non-git path: $INSTALL_DIR"
  exit 1
else
  echo "Cloning repository into $INSTALL_DIR"
  sudo git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Ensure regular user can run/update project files later
sudo chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"

echo "Checking latest GitHub release tag..."
LATEST_TAG=""
if curl -fsSL "$LATEST_RELEASE_API" >/tmp/linux_manager_release.json 2>/dev/null; then
  LATEST_TAG="$(sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' /tmp/linux_manager_release.json | head -n1)"
fi
rm -f /tmp/linux_manager_release.json

if [[ -n "$LATEST_TAG" ]]; then
  echo "Updating to release tag: $LATEST_TAG"
  git -C "$INSTALL_DIR" fetch --tags --quiet
  git -C "$INSTALL_DIR" checkout --quiet "$LATEST_TAG"
else
  echo "Could not resolve latest release tag; pulling current branch."
  git -C "$INSTALL_DIR" pull --ff-only || true
fi

# App launcher command
if [[ -e "$LAUNCHER_BIN" ]]; then
  echo "Updating launcher: $LAUNCHER_BIN"
else
  echo "Creating launcher: $LAUNCHER_BIN"
fi
sudo bash -c "cat > '$LAUNCHER_BIN' << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
export QT_QPA_PLATFORM=wayland
exec python /opt/linux-manager/main/main.py
EOF"
sudo chmod 755 "$LAUNCHER_BIN"

if [[ -e "$UPDATER_BIN" ]]; then
  echo "Updating updater command: $UPDATER_BIN"
else
  echo "Creating updater command: $UPDATER_BIN"
fi
sudo bash -c "cat > '$UPDATER_BIN' << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec bash /opt/linux-manager/main/update.sh
EOF"
sudo chmod 755 "$UPDATER_BIN"

# Desktop launcher
if [[ -e "$DESKTOP_FILE" ]]; then
  echo "Updating desktop entry: $DESKTOP_FILE"
else
  echo "Creating desktop entry: $DESKTOP_FILE"
fi
sudo bash -c "cat > '$DESKTOP_FILE' << EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=Linux setup and application manager
Exec=$LAUNCHER_BIN
Terminal=false
Categories=System;Settings;
StartupNotify=true
EOF"
sudo chmod 644 "$DESKTOP_FILE"

# Optional: copy launcher into user applications as well
mkdir -p "$USER_HOME/.local/share/applications"
cp "$DESKTOP_FILE" "$USER_HOME/.local/share/applications/linux-manager.desktop" || true

# Keep the old commands working for existing shortcuts and shell history.
sudo ln -sfn "$LAUNCHER_BIN" /usr/local/bin/arch-mysetup
sudo ln -sfn "$UPDATER_BIN" /usr/local/bin/arch-mysetup-update
sudo rm -f /usr/share/applications/arch-mysetup.desktop "$USER_HOME/.local/share/applications/arch-mysetup.desktop"

# Start app
"$LAUNCHER_BIN"
