#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="aleksireede"
REPO_NAME="arch-mysetup"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
INSTALL_DIR="/opt/linux-manager"
if [[ ! -d "$INSTALL_DIR/.git" && -d "/opt/arch-mysetup/.git" ]]; then
  INSTALL_DIR="/opt/arch-mysetup"
fi
LAUNCHER_BIN="/usr/local/bin/linux-manager"
if ! command -v git >/dev/null 2>&1; then
  echo "git is required for updates."
  exit 1
fi

if command -v rpm >/dev/null 2>&1 && rpm -q linux-manager >/dev/null 2>&1; then
  CURRENT_VERSION="$(rpm -q --qf '%{VERSION}' linux-manager)"
  LATEST_TAG="$(git ls-remote --tags --refs "$REPO_URL" | sed 's#.*refs/tags/##' | sort -V | tail -n1)"
  if [[ -z "$LATEST_TAG" ]]; then
    echo "Unable to resolve the latest version tag from GitHub."
    exit 1
  fi
  LATEST_VERSION="${LATEST_TAG#v}"
  echo "Installed RPM version: $CURRENT_VERSION"
  echo "Latest release:       $LATEST_VERSION"
  if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" ]]; then
    echo "Already up to date."
    exit 0
  fi
  if [[ "$(printf '%s\n' "$CURRENT_VERSION" "$LATEST_VERSION" | sort -V | tail -n1)" == "$CURRENT_VERSION" ]]; then
    echo "Installed version $CURRENT_VERSION is newer than $LATEST_VERSION; skipping downgrade."
    exit 0
  fi
  RPM_FILE="linux-manager-${LATEST_VERSION}-1.noarch.rpm"
  RPM_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases/download/${LATEST_TAG}/${RPM_FILE}"
  TEMP_RPM="$(mktemp --suffix=.rpm)"
  trap 'rm -f "$TEMP_RPM"' EXIT
  curl -fL "$RPM_URL" -o "$TEMP_RPM"
  if command -v dnf5 >/dev/null 2>&1; then
    if [[ "$EUID" -eq 0 ]]; then dnf5 install -y "$TEMP_RPM"; else sudo dnf5 install -y "$TEMP_RPM"; fi
  elif command -v dnf >/dev/null 2>&1; then
    if [[ "$EUID" -eq 0 ]]; then dnf install -y "$TEMP_RPM"; else sudo dnf install -y "$TEMP_RPM"; fi
  else
    echo "DNF or DNF5 is required to update the Fedora RPM."
    exit 1
  fi
  exit 0
fi

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  echo "Install not found at $INSTALL_DIR. Run setup first."
  exit 1
fi

CURRENT_TAG="$(git -C "$INSTALL_DIR" describe --tags --exact-match 2>/dev/null || echo "unknown")"

# The GitHub /releases/latest endpoint follows publication time, which can
# point at an older tag if newer version tags were pushed without a release.
git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
git -C "$INSTALL_DIR" fetch origin --tags --prune
LATEST_TAG="$(git -C "$INSTALL_DIR" tag --list | sort -V | tail -n1)"

if [[ -z "$LATEST_TAG" ]]; then
  echo "Unable to resolve the latest version tag from GitHub."
  exit 1
fi

echo "Installed version: $CURRENT_TAG"
echo "Latest release:    $LATEST_TAG"

if [[ -f "$INSTALL_DIR/main/install_app_integration.sh" ]]; then
  INSTALL_DIR="$INSTALL_DIR" bash "$INSTALL_DIR/main/install_app_integration.sh"
fi

if [[ "$CURRENT_TAG" == "$LATEST_TAG" ]]; then
  echo "Already up to date."
  exit 0
fi

# Protect installations on a newer version if the remote's highest tag is
# older or if the local checkout is ahead of all published tags.
if [[ "$CURRENT_TAG" != "unknown" ]]; then
  NEWER_TAG="$(printf '%s\n' "$CURRENT_TAG" "$LATEST_TAG" | sort -V | tail -n1)"
  if [[ "$NEWER_TAG" == "$CURRENT_TAG" ]]; then
    echo "Installed tag $CURRENT_TAG is newer than remote tag $LATEST_TAG; skipping downgrade."
    exit 0
  fi
fi

echo "Updating to $LATEST_TAG..."
git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
if ! git -C "$INSTALL_DIR" rev-parse --verify --quiet "refs/tags/$LATEST_TAG^{commit}" >/dev/null; then
  echo "Release tag $LATEST_TAG was not found after fetching tags."
  exit 1
fi
git -C "$INSTALL_DIR" checkout --detach "$LATEST_TAG"
printf '%s\n' "${LATEST_TAG#v}" > "$INSTALL_DIR/VERSION"

CHECKED_OUT_TAG="$(git -C "$INSTALL_DIR" describe --tags --exact-match 2>/dev/null || echo "unknown")"
if [[ "$CHECKED_OUT_TAG" != "$LATEST_TAG" ]]; then
  echo "Expected release $LATEST_TAG, but checked out $CHECKED_OUT_TAG."
  exit 1
fi
echo "Checked out release: $CHECKED_OUT_TAG"

# Recreate desktop integration after updating, including the launcher and icon.
INSTALL_DIR="$INSTALL_DIR" bash "$INSTALL_DIR/main/install_app_integration.sh"

if [[ -x "$LAUNCHER_BIN" ]]; then
  echo "Update complete. Start with: $LAUNCHER_BIN"
else
  echo "Update complete. Launcher missing at $LAUNCHER_BIN; rerun setup."
fi
