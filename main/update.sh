#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="aleksireede"
REPO_NAME="arch-mysetup"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
REPO_BRANCH="main"
INSTALL_DIR="/opt/arch-mysetup"
LAUNCHER_BIN="/usr/local/bin/arch-mysetup"
if ! command -v git >/dev/null 2>&1; then
  echo "git is required for updates."
  exit 1
fi

if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  echo "Install not found at $INSTALL_DIR. Run setup first."
  exit 1
fi

CURRENT_TAG="$(git -C "$INSTALL_DIR" describe --tags --exact-match 2>/dev/null || echo "unknown")"

git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
git -C "$INSTALL_DIR" fetch origin "+refs/heads/$REPO_BRANCH:refs/remotes/origin/$REPO_BRANCH" --tags --prune
LATEST_TAG="$(git -C "$INSTALL_DIR" describe --tags --exact-match "origin/$REPO_BRANCH" 2>/dev/null || true)"
if [[ -z "$LATEST_TAG" ]]; then
  LATEST_TAG="$(git -C "$INSTALL_DIR" tag --merged "origin/$REPO_BRANCH" --sort=-version:refname | head -n1)"
fi
if [[ -z "$LATEST_TAG" ]]; then
  echo "No version tag was found on origin/$REPO_BRANCH."
  exit 1
fi

echo "Installed version: $CURRENT_TAG"
echo "Latest version:    $LATEST_TAG"

if [[ "$CURRENT_TAG" != "unknown" ]]; then
  NEWER_TAG="$(printf '%s\n' "$CURRENT_TAG" "$LATEST_TAG" | sort -V | tail -n1)"
  if [[ "$NEWER_TAG" == "$CURRENT_TAG" ]]; then
    echo "Installed tag $CURRENT_TAG is already current or newer; skipping downgrade."
    exit 0
  fi
fi

echo "Updating to tag $LATEST_TAG..."
UPDATER_COPY="$(mktemp)"
cp "$INSTALL_DIR/main/update.sh" "$UPDATER_COPY"
trap 'rm -f "$UPDATER_COPY"' EXIT

# This checkout may contain the updater fixes being applied. Restore only the
# two version-management files before switching tags, then carry the fixed
# updater and tag check forward to the new version.
git -C "$INSTALL_DIR" restore -- main/update.sh gui/setup_window.py
git -C "$INSTALL_DIR" checkout --detach "$LATEST_TAG"
CHECKED_OUT_TAG="$(git -C "$INSTALL_DIR" describe --tags --exact-match 2>/dev/null || echo "unknown")"
if [[ "$CHECKED_OUT_TAG" != "$LATEST_TAG" ]]; then
  echo "Expected tag $LATEST_TAG, but checked out $CHECKED_OUT_TAG."
  exit 1
fi
echo "Checked out version: $CHECKED_OUT_TAG"
install -m 755 "$UPDATER_COPY" "$INSTALL_DIR/main/update.sh"

python3 - "$INSTALL_DIR/gui/setup_window.py" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
start_marker = "    @staticmethod\n    def fetch_latest_release_tag():"
end_marker = "\n    @staticmethod\n    def get_current_version():"
start = source.find(start_marker)
end = source.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("Could not update the version check in gui/setup_window.py")

replacement = '''    @staticmethod
    def fetch_latest_release_tag():
        output = subprocess.check_output(
            [
                "git", "ls-remote", "--tags", "--refs",
                "https://github.com/aleksireede/arch-mysetup.git",
            ],
            text=True,
            timeout=8,
        )
        tags = [
            line.rsplit("refs/tags/", 1)[-1]
            for line in output.splitlines()
            if "refs/tags/" in line
        ]
        version_tags = [tag for tag in tags if re.fullmatch(r"v?\\d+(?:\\.\\d+)*", tag)]
        if not version_tags:
            raise RuntimeError("Could not resolve a version tag from GitHub")
        return max(
            version_tags,
            key=lambda tag: tuple(
                int(part) for part in (tag[1:] if tag.startswith("v") else tag).split(".")
            ),
        )
'''
source = source[:start] + replacement + source[end:]
if "import re\n" not in source:
    if "import json\n" in source:
        source = source.replace("import json\n", "import re\n", 1)
    else:
        source = source.replace("import sys\n", "import sys\nimport re\n", 1)
source = source.replace("import urllib.request\n", "", 1)
source = source.replace("Latest release:", "Latest version:")
source = source.replace("Latest release {latest_tag}", "Latest version {latest_tag}")
path.write_text(source, encoding="utf-8")
PY

if [[ -x "$LAUNCHER_BIN" ]]; then
  echo "Update complete. Start with: $LAUNCHER_BIN"
else
  echo "Update complete. Launcher missing at $LAUNCHER_BIN; rerun setup."
fi
