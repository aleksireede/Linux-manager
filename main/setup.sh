#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/aleksireede/arch-mysetup.git"
REPO_OWNER="aleksireede"
REPO_NAME="arch-mysetup"
INSTALL_DIR="/opt/arch-mysetup"
LAUNCHER_BIN="/usr/local/bin/arch-mysetup"
UPDATER_BIN="/usr/local/bin/arch-mysetup-update"
DESKTOP_FILE="/usr/share/applications/arch-mysetup.desktop"
APP_NAME="Arch MySetup"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
LATEST_RELEASE_API="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"

if command -v pacman >/dev/null 2>&1
then
    sudo pacman -S --needed --noconfirm \
    python python-pip python-pyqt5 python-pyqt6 \
    qt5-base qt5-xcb-private-headers libxcb gnome-console git curl

elif command -v dnf >/dev/null 2>&1
then
    sudo dnf install -y \
    python3 python3-pip python3-qt5 \
    qt5-qtbase qt5-qtx11extras libxcb-devel gnome-terminal git \
    curl
fi

echo "Checking installation directory..."
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
if curl -fsSL "$LATEST_RELEASE_API" >/tmp/arch_mysetup_release.json 2>/dev/null; then
  LATEST_TAG="$(sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' /tmp/arch_mysetup_release.json | head -n1)"
fi
rm -f /tmp/arch_mysetup_release.json

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
exec python /opt/arch-mysetup/main/main.py
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
exec bash /opt/arch-mysetup/main/update.sh
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
Comment=Arch setup utility
Exec=$LAUNCHER_BIN
Terminal=false
Categories=System;Settings;
StartupNotify=true
EOF"
sudo chmod 644 "$DESKTOP_FILE"

# Optional: copy launcher into user applications as well
mkdir -p "$USER_HOME/.local/share/applications"
cp "$DESKTOP_FILE" "$USER_HOME/.local/share/applications/arch-mysetup.desktop" || true

# Start app
"$LAUNCHER_BIN"
