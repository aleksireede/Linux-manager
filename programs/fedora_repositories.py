"""Load and import Fedora third-party repository definitions from app catalogs."""

import configparser
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml

from programs.installer_logic import command_exists, package_manager, open_terminal


CATALOG_FILES = ("app.yaml",)
REPO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def load_fedora_repositories():
    catalog_dir = Path(__file__).resolve().parent.parent / "bin"
    repositories = {}
    for catalog_name in CATALOG_FILES:
        try:
            entries = yaml.safe_load((catalog_dir / catalog_name).read_text(encoding="utf-8")) or []
        except (OSError, yaml.YAMLError):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("fedora_repo_id"):
                continue
            repo_id = str(entry["fedora_repo_id"])
            if not REPO_ID_PATTERN.fullmatch(repo_id):
                continue
            key_url = str(entry.get("fedora_gpg_key", "")).strip()
            if not key_url.startswith("https://"):
                continue
            repo = repositories.setdefault(repo_id, {
                "id": repo_id,
                "name": entry.get("fedora_repo_name", repo_id),
                "file_url": entry.get("fedora_repo_file_url"),
                "baseurl": entry.get("fedora_repo_baseurl"),
                "file_name": entry.get("fedora_repo_file_name", f"{repo_id}.repo"),
                "repo_type": entry.get("fedora_repo_type", "rpm-md"),
                "autorefresh": str(entry.get("fedora_repo_autorefresh", "1")),
                "gpg_key": key_url,
                "gpg_owner": str(entry.get("fedora_gpg_key_owner", "")),
                "apps": [],
            })
            app_name = entry.get("title", entry.get("name", ""))
            if app_name and app_name not in repo["apps"]:
                repo["apps"].append(app_name)
    return sorted(repositories.values(), key=lambda repo: str(repo["name"]).casefold())


def fedora_repository_is_configured(repo):
    repo_dir = Path("/etc/yum.repos.d")
    configured = False
    for repo_file in repo_dir.glob("*.repo"):
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(repo_file, encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        if parser.has_section(repo["id"]):
            section = parser[repo["id"]]
            configured = (
                section.get("enabled", "1").strip() == "1"
                and section.get("gpgcheck", "0").strip() == "1"
                and repo["gpg_key"].lower() in section.get("gpgkey", "").lower()
            )
            if configured:
                break
    # RPM key summaries are vendor supplied and vary across key imports, so
    # matching an owner string against SUMMARY can mark a valid repo missing.
    # The importer separately treats a failed rpm --import as an error.
    return configured


def _repo_file_content(repo):
    if repo.get("file_url"):
        request = urllib.request.Request(repo["file_url"], headers={"User-Agent": "Linux-Manager"})
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read(512 * 1024)
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(content.decode("utf-8"))
        if not parser.has_section(repo["id"]):
            raise RuntimeError(f"Repository file did not contain [{repo['id']}].")
        section = parser[repo["id"]]
        if section.get("gpgcheck", "0").strip() != "1":
            raise RuntimeError(f"Repository {repo['id']} does not require package signature checks.")
        if repo["gpg_key"].lower() not in section.get("gpgkey", "").lower():
            raise RuntimeError(f"Repository {repo['id']} uses an unexpected signing key URL.")
        return content

    baseurl = str(repo.get("baseurl", "")).strip()
    if not baseurl.startswith("https://"):
        raise RuntimeError(f"Repository {repo['id']} has no valid HTTPS base URL.")
    return (
        f"[{repo['id']}]\n"
        f"name={repo['name']}\n"
        f"baseurl={baseurl}\n"
        "enabled=1\n"
        "autorefresh=1\n"
        f"type={repo.get('repo_type', 'rpm-md')}\n"
        "gpgcheck=1\n"
        f"gpgkey={repo['gpg_key']}\n"
    ).encode("utf-8")


def import_fedora_repositories(repositories, progress_callback=None):
    if package_manager() not in {"dnf", "dnf5"}:
        raise RuntimeError("Fedora repositories can only be imported on Fedora.")
    if not repositories:
        raise RuntimeError("No Fedora repositories are configured in the app catalogs.")

    helper_path = Path(__file__).resolve().parent.parent / "scripts" / "install_fedora_repositories.py"
    with tempfile.TemporaryDirectory(prefix="linux-manager-repos-") as temp_directory:
        temp_path = Path(temp_directory)
        staged_repositories = []
        keys = []
        for index, repo in enumerate(repositories, 1):
            if progress_callback:
                progress_callback(f"Downloading repository file {index}/{len(repositories)}")
            filename = Path(repo["file_name"]).name
            if not filename.endswith(".repo"):
                filename = f"{repo['id']}.repo"
            staged_file = temp_path / filename
            staged_file.write_bytes(_repo_file_content(repo))
            staged_repositories.append({"id": repo["id"], "source": str(staged_file)})
            if repo["gpg_key"] not in keys:
                keys.append(repo["gpg_key"])

        manifest = temp_path / "manifest.json"
        manifest.write_text(json.dumps({"repositories": staged_repositories, "keys": keys}), encoding="utf-8")
        helper_command = [sys.executable, str(helper_path), str(manifest)]
        if command_exists("pkexec"):
            if progress_callback:
                progress_callback("Importing signing keys and repository files, then refreshing DNF metadata")
            process = subprocess.Popen(
                ["pkexec", *helper_command], stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True,
            )
            try:
                output, _ = process.communicate(timeout=240)
            except subprocess.TimeoutExpired as error:
                process.kill()
                process.communicate()
                raise RuntimeError("Repository import timed out.") from error
            output_tail = [line.strip() for line in output.splitlines() if line.strip()][-15:]
            if progress_callback:
                for line in output_tail:
                    progress_callback(line)
            return_code = process.returncode
            if return_code:
                message = "\n".join(output_tail) or f"pkexec exited with status {return_code}."
                raise RuntimeError(message)
            return "\n".join(output_tail) or "Repositories and signing keys imported."

        if progress_callback:
            progress_callback("Waiting for the administrator password in the terminal")
        process = open_terminal(["sudo", *helper_command])
        return_code = process.wait(timeout=240)
        if return_code:
            raise RuntimeError(f"Repository import terminal exited with status {return_code}.")
        return "Repository import command finished."
