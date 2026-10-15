#!/usr/bin/env python3
"""Install and launch the official JetBrains Toolbox Linux archive for this user."""

import json
import platform
import posixpath
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath


RELEASES_URL = (
    "https://data.services.jetbrains.com/products/releases"
    "?code=TBA&latest=true&type=release"
)


def extract_archive_safely(archive, staging_dir):
    members = archive.getmembers()
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"Unsafe entry in JetBrains Toolbox archive: {member.name}")
        if not (member.isdir() or member.isfile() or member.issym()):
            raise RuntimeError(f"Unsupported entry in JetBrains Toolbox archive: {member.name}")
        if member.issym():
            target = PurePosixPath(member.linkname)
            resolved_target = posixpath.normpath(str(path.parent / target))
            if target.is_absolute() or resolved_target == ".." or resolved_target.startswith("../"):
                raise RuntimeError(f"Unsafe symlink in JetBrains Toolbox archive: {member.name}")

    data_members = [member for member in members if not member.issym()]
    if hasattr(tarfile, "data_filter"):
        archive.extractall(staging_dir, members=data_members, filter="data")
    else:
        # Older Python versions lack tarfile's safe data filter. These entries
        # have already been constrained to regular files and directories with
        # relative, traversal-free paths.
        archive.extractall(staging_dir, members=data_members)

    root = staging_dir.resolve()
    for member in members:
        if not member.issym():
            continue
        destination = staging_dir.joinpath(*PurePosixPath(member.name).parts)
        if not destination.parent.resolve().is_relative_to(root):
            raise RuntimeError(f"Unsafe symlink parent in JetBrains Toolbox archive: {member.name}")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"Duplicate path in JetBrains Toolbox archive: {member.name}")
        destination.symlink_to(member.linkname)

    for member in members:
        if member.issym():
            destination = staging_dir.joinpath(*PurePosixPath(member.name).parts)
            try:
                if not destination.resolve(strict=False).is_relative_to(root):
                    raise RuntimeError(f"Unsafe symlink in JetBrains Toolbox archive: {member.name}")
            except (OSError, RuntimeError) as error:
                raise RuntimeError(f"Unsafe symlink in JetBrains Toolbox archive: {member.name}") from error
    return members


def main():
    request = urllib.request.Request(RELEASES_URL, headers={"User-Agent": "Linux-Manager"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release_data = json.load(response)
    release = release_data["TBA"][0]
    platform_key = "linuxARM64" if platform.machine().lower() in {"aarch64", "arm64"} else "linux"
    download_url = release["downloads"][platform_key]["link"]
    install_dir = Path.home() / ".local/share/JetBrains/Toolbox"
    install_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="linux-manager-toolbox-") as temp_dir:
        archive_path = Path(temp_dir) / "toolbox.tar.gz"
        request = urllib.request.Request(download_url, headers={"User-Agent": "Linux-Manager"})
        with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as archive:
            shutil.copyfileobj(response, archive)

        staging_dir = Path(temp_dir) / "extracted"
        staging_dir.mkdir()
        with tarfile.open(archive_path, "r:gz") as archive:
            safe_members = extract_archive_safely(archive, staging_dir)

        for member in safe_members:
            if not member.isdir() or PurePosixPath(member.name).parent != PurePosixPath("."):
                continue
            staged_app = staging_dir / member.name
            if staged_app.is_dir() and not staged_app.is_symlink():
                shutil.copytree(staged_app, install_dir / member.name, dirs_exist_ok=True, symlinks=True)

    binaries = [
        install_dir.joinpath(*PurePosixPath(member.name).parts)
        for member in safe_members
        if PurePosixPath(member.name).name == "jetbrains-toolbox"
    ]
    binaries = [path for path in binaries if path.is_file()]
    if not binaries:
        raise RuntimeError("The downloaded JetBrains archive did not contain its executable.")

    binary = max(binaries, key=lambda path: path.stat().st_mtime_ns)
    binary.chmod(binary.stat().st_mode | 0o100)
    subprocess.Popen(
        [str(binary)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    print("JetBrains Toolbox was installed and launched. It will create its application menu entry on first run.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"JetBrains Toolbox installation failed: {error}")
        raise SystemExit(1)
