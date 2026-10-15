#!/usr/bin/env python3
"""Privileged helper for installing validated Fedora repo files and RPM keys."""

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def main():
    if os.geteuid() != 0:
        raise SystemExit("This helper must run with administrator privileges.")
    if len(sys.argv) != 2:
        raise SystemExit("Expected a repository manifest path.")

    manifest_path = Path(sys.argv[1])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repo_dir = Path("/etc/yum.repos.d")
    repo_dir.mkdir(parents=True, exist_ok=True)

    for key_url in manifest.get("keys", []):
        if not isinstance(key_url, str) or not key_url.startswith("https://"):
            raise SystemExit("Refusing a non-HTTPS RPM signing key URL.")
        print(f"Importing RPM signing key: {key_url}", flush=True)
        subprocess.run(["rpm", "--import", key_url], check=True, timeout=45)

    for repo in manifest.get("repositories", []):
        repo_id = repo.get("id", "")
        if not REPO_ID_PATTERN.fullmatch(repo_id):
            raise SystemExit(f"Invalid repository ID: {repo_id}")
        source = Path(repo.get("source", ""))
        content = source.read_bytes()
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(content.decode("utf-8"))
        if not parser.has_section(repo_id):
            raise SystemExit(f"Repository file does not contain [{repo_id}].")
        section = parser[repo_id]
        if section.get("enabled", "1").strip() != "1" or section.get("gpgcheck", "0").strip() != "1":
            raise SystemExit(f"Repository {repo_id} must be enabled and require GPG checks.")
        if not section.get("gpgkey", "").strip().startswith("https://"):
            raise SystemExit(f"Repository {repo_id} does not declare an HTTPS signing key.")

        destination = repo_dir / f"{repo_id}.repo"
        with tempfile.NamedTemporaryFile(dir=repo_dir, prefix=f".{repo_id}-", delete=False) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_name = temp_file.name
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, destination)
        print(f"Installed repository configuration: {destination}", flush=True)

    package_manager = shutil.which("dnf5") or shutil.which("dnf")
    if package_manager:
        repo_args = [f"--repo={repo['id']}" for repo in manifest.get("repositories", [])]
        command = [package_manager, "makecache", "--refresh", *repo_args]
        print("Refreshing metadata for imported repositories.", flush=True)
        try:
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=240,
            )
        except subprocess.TimeoutExpired as error:
            raise SystemExit("DNF repository refresh timed out after 240 seconds.") from error
        if result.stdout:
            print(result.stdout.rstrip(), flush=True)
        if result.returncode:
            raise SystemExit(f"DNF repository refresh failed with status {result.returncode}.")

    print("Repository files, signing keys, and metadata refreshed successfully.", flush=True)


if __name__ == "__main__":
    main()
