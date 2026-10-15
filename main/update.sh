#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="aleksireede"
REPO_NAME="arch-mysetup"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
REPO_BRANCH="main"
INSTALL_DIR="/opt/linux-manager"
if [[ ! -d "$INSTALL_DIR/.git" && -d "/opt/arch-mysetup/.git" ]]; then
  INSTALL_DIR="/opt/arch-mysetup"
fi
LAUNCHER_BIN="/usr/local/bin/linux-manager"
LATEST_RELEASE_API="https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for release checks."
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required for updates."
  exit 1
fi

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  echo "Install not found at $INSTALL_DIR. Run setup first."
  exit 1
fi

CURRENT_TAG="$(git -C "$INSTALL_DIR" describe --tags --exact-match 2>/dev/null || true)"
if [[ -z "$CURRENT_TAG" ]]; then
  CURRENT_TAG="$(git -C "$INSTALL_DIR" describe --tags --abbrev=0 2>/dev/null || echo "unknown")"
fi

LATEST_TAG=""
if curl -fsSL "$LATEST_RELEASE_API" >/tmp/linux_manager_release.json 2>/dev/null; then
  LATEST_TAG="$(sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' /tmp/linux_manager_release.json | head -n1)"
fi
rm -f /tmp/linux_manager_release.json

if [[ -z "$LATEST_TAG" ]]; then
  echo "Unable to resolve latest release tag from GitHub."
  exit 1
fi

echo "Installed version: $CURRENT_TAG"
echo "Latest release:    $LATEST_TAG"

if [[ "$CURRENT_TAG" == "$LATEST_TAG" ]]; then
  echo "Already up to date."
  exit 0
fi

echo "Updating to $LATEST_TAG..."
git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
git -C "$INSTALL_DIR" fetch origin "$REPO_BRANCH" --tags --prune

if git -C "$INSTALL_DIR" show-ref --verify --quiet "refs/heads/$REPO_BRANCH"; then
  git -C "$INSTALL_DIR" switch "$REPO_BRANCH"
else
  git -C "$INSTALL_DIR" switch --track -c "$REPO_BRANCH" "origin/$REPO_BRANCH"
fi

git -C "$INSTALL_DIR" pull --ff-only origin "$REPO_BRANCH"

if [[ -x "$LAUNCHER_BIN" ]]; then
  echo "Update complete. Start with: $LAUNCHER_BIN"
else
  echo "Update complete. Launcher missing at $LAUNCHER_BIN; rerun setup."
fi
