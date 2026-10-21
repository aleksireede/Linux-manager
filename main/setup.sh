#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/aleksireede/arch-mysetup.git"
REPO_OWNER="aleksireede"
REPO_NAME="arch-mysetup"
INSTALL_DIR="/opt/linux-manager"
LEGACY_INSTALL_DIR="/opt/arch-mysetup"
LAUNCHER_BIN="/usr/local/bin/linux-manager"
UPDATER_BIN="/usr/local/bin/linux-manager-update"
USER_NAME="${SUDO_USER:-$USER}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
LATEST_RELEASE_API="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"

if [[ -z "$USER_HOME" ]]; then
  echo "Could not determine the home directory for $USER_NAME."
  exit 1
fi

run_root() {
  if [[ "$EUID" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

if command -v pacman >/dev/null 2>&1; then
  run_root pacman -S --needed --noconfirm \
    python python-pyyaml python-pyqt5 qt5-base qt5-wayland libxcb \
    gnome-console git curl
elif command -v dnf5 >/dev/null 2>&1; then
  run_root dnf5 install -y \
    python3 python3-pyyaml python3-qt5 qt5-qtbase-gui qt5-qtwayland \
    gnome-terminal git curl
elif command -v dnf >/dev/null 2>&1; then
  run_root dnf install -y \
    python3 python3-pyyaml python3-qt5 qt5-qtbase-gui qt5-qtwayland \
    gnome-terminal git curl
else
  echo "Unsupported distribution: expected pacman, dnf5, or dnf."
  exit 1
fi

echo "Checking installation directory..."
if [[ ! -e "$INSTALL_DIR" && -d "$LEGACY_INSTALL_DIR/.git" ]]; then
  echo "Migrating existing installation from $LEGACY_INSTALL_DIR"
  run_root mv "$LEGACY_INSTALL_DIR" "$INSTALL_DIR"
fi
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "Existing git install found: $INSTALL_DIR"
elif [[ -e "$INSTALL_DIR" ]]; then
  echo "Refusing to overwrite non-git path: $INSTALL_DIR"
  exit 1
else
  echo "Cloning repository into $INSTALL_DIR"
  run_root git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Ensure regular user can run/update project files later
USER_GROUP="$(id -gn "$USER_NAME")"
run_root chown -R "$USER_NAME:$USER_GROUP" "$INSTALL_DIR"

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

INSTALL_DIR="$INSTALL_DIR" bash "$INSTALL_DIR/main/install_app_integration.sh"

# Keep the old commands working for existing shortcuts and shell history.
run_root ln -sfn "$LAUNCHER_BIN" /usr/local/bin/arch-mysetup
run_root ln -sfn "$UPDATER_BIN" /usr/local/bin/arch-mysetup-update
run_root rm -f /usr/share/applications/arch-mysetup.desktop
rm -f "$USER_HOME/.local/share/applications/arch-mysetup.desktop"

# Start app
"$LAUNCHER_BIN"
