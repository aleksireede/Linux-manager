import os
import secrets
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from functools import lru_cache
import yaml
import configparser
from programs.app_settings import external_terminal, package_conflict_policy

# Filesystem types that are backed by the network (fstab "type" field).
NETWORK_FS_TYPES = {
    "cifs", "cifs4", "smbfs", "smb", "nfs", "nfs4", "nfsv4", "nfsd",
    "sshfs", "ncpfs", "webdav", "davfs2", "dav", "ftp", "ftps",
}


def command_exists(command):
    return shutil.which(command) is not None


def package_manager():
    """Detect the system's native package manager."""
    try:
        distro_id = next((line.split("=", 1)[1].strip('"') for line in Path("/etc/os-release").read_text().splitlines()
                          if line.startswith("ID=")), "")
    except OSError:
        distro_id = ""
    if distro_id == "fedora":
        if command_exists("dnf5"):
            return "dnf5"
        if command_exists("dnf"):
            return "dnf"
    if command_exists("pacman"):
        return "pacman"
    if command_exists("dnf5"):
        return "dnf5"
    if command_exists("dnf"):
        return "dnf"
    return None


def is_fedora():
    try:
        return any(line.startswith("ID=fedora") for line in Path("/etc/os-release").read_text().splitlines())
    except OSError:
        return package_manager() in {"dnf", "dnf5"}


def _catalog_signature():
    root = Path(__file__).parent.parent / "bin"
    signature = []
    path = root / "app.yaml"
    try:
        stat = path.stat()
        signature.append(("app.yaml", stat.st_mtime_ns, stat.st_size))
    except OSError:
        signature.append(("app.yaml", None, None))
    return tuple(signature)


@lru_cache(maxsize=8)
def _load_fedora_app_records(signature):
    """Load Fedora package overrides and repository requirements once."""
    root = Path(__file__).parent.parent / "bin"
    records = {}
    try:
        entries = yaml.safe_load((root / "app.yaml").read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError):
        entries = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name"):
            records.setdefault(entry["name"], entry)
    return records


def _fedora_app_records():
    # IDE edits do not call clear_app_catalog_cache(), so include catalog file
    # metadata in the cache key to avoid using stale package names in a live UI.
    return _load_fedora_app_records(_catalog_signature())


def clear_app_catalog_cache():
    """Reload package-name mappings after the YAML catalog changes."""
    _load_fedora_app_records.cache_clear()
    _fedora_repository_ready.cache_clear()


def fedora_app_name(app_name):
    """Translate a catalog's Arch identifier to its Fedora package name, if defined."""
    record = _fedora_app_records().get(app_name)
    return record.get("fedora_app_name", app_name) if record else app_name


def fedora_install_type(app_name):
    """Return a catalog-defined non-RPM Fedora installation method, if any."""
    record = _fedora_app_records().get(app_name, {})
    return record.get("fedora_install_type")


def _jetbrains_toolbox_installed():
    """Recognize both Toolbox's extracted version directory and its stable path."""
    toolbox_dir = Path.home() / ".local/share/JetBrains/Toolbox"
    binary_paths = [toolbox_dir / "bin/jetbrains-toolbox"]
    try:
        binary_paths.extend(toolbox_dir.glob("jetbrains-toolbox-*/bin/jetbrains-toolbox"))
    except OSError:
        pass
    return any(path.is_file() and os.access(path, os.X_OK) for path in binary_paths) or command_exists(
        "jetbrains-toolbox"
    )


def arch_app_name(app_name):
    """Translate a catalog identifier to its Arch package name, when set."""
    record = _fedora_app_records().get(app_name)
    return record.get("arch_app_name", app_name) if record else app_name


def arch_catalog_app_name(package_name):
    """Translate an installed Arch package name back to its catalog identifier."""
    for app_name, record in _fedora_app_records().items():
        if record.get("arch_app_name") == package_name:
            return app_name
    return package_name


def fedora_catalog_app_name(package_name):
    """Translate an installed Fedora package back to its catalog identifier."""
    for app_name, record in _fedora_app_records().items():
        fedora_name = record.get("fedora_app_name")
        if fedora_name == package_name:
            return app_name
        if isinstance(fedora_name, str) and fedora_name.rsplit(".", 1)[-1] in {
            "i386", "i486", "i586", "i686", "x86_64", "aarch64", "armv7hl",
            "ppc64le", "s390x", "riscv64", "noarch",
        } and fedora_name.rsplit(".", 1)[0] == package_name:
            return app_name
    return package_name


def _fedora_flatpak_installed(app_name):
    record = _fedora_app_records().get(app_name, {})
    app_id = record.get("fedora_flatpak_app_id")
    if not app_id or not command_exists("flatpak"):
        return False
    for scope in ("--user", "--system"):
        try:
            subprocess.run(
                ["flatpak", "info", scope, app_id],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=True, timeout=8,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


@lru_cache(maxsize=None)
def _fedora_repository_ready(app_name):
    record = _fedora_app_records().get(app_name, {})
    repo_id = record.get("fedora_repo_id")
    if not repo_id:
        return True

    expected_key = str(record.get("fedora_gpg_key", "")).lower()
    if not expected_key:
        return False
    expected_baseurl = str(record.get("fedora_repo_baseurl", "")).strip().lower().rstrip("/")

    for repo_file in Path("/etc/yum.repos.d").glob("*.repo"):
        parser = configparser.ConfigParser()
        try:
            parser.read(repo_file, encoding="utf-8")
        except (OSError, configparser.Error):
            continue
        for section_id in parser.sections():
            section = parser[section_id]
            actual_baseurl = section.get("baseurl", "").strip().lower().rstrip("/")
            if section_id == str(repo_id) or (
                expected_baseurl and expected_baseurl in actual_baseurl
            ):
                # COPR's own enable command uses a canonical section ID,
                # which differs from our catalog ID. Match it by repository URL.
                if (
                    section.get("enabled", "1").strip() == "1"
                    and section.get("gpgcheck", "0").strip() == "1"
                    and expected_key in section.get("gpgkey", "").lower()
                ):
                    return True

    return False


def fedora_packages_available(app_names):
    """Resolve many catalog apps against enabled Fedora repos in one query."""
    manager = package_manager()
    if manager not in {"dnf", "dnf5"}:
        return set()
    available = {
        app_name for app_name in dict.fromkeys(app_names)
        if fedora_install_type(app_name) == "jetbrains-toolbox"
    }
    package_names = {}
    for app_name in dict.fromkeys(app_names):
        package_name = _system_package_name(app_name)
        if package_name == "@development-tools" and _fedora_repository_ready(app_name):
            # DNF groups are installable targets but do not appear in repoquery
            # package results, so recognize the Fedora equivalent directly.
            available.add(app_name)
        elif package_name and _fedora_repository_ready(app_name):
            package_names[app_name] = package_name
    if not package_names:
        return available
    try:
        result = subprocess.run(
            [
                manager, "repoquery", "--available", "--queryformat",
                "%{name}.%{arch}\\n", *sorted(set(package_names.values())),
            ],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=120,
        )
        available_names = {
            line.strip() for line in result.stdout.splitlines() if line.strip()
        }
        # DNF can return a non-zero status when any requested name is missing,
        # while still printing matches for the other names. Keep those matches
        # so one bad catalog entry cannot hide every valid package.
        def requested_package_is_available(package_name):
            suffix = package_name.rsplit(".", 1)[-1]
            if suffix in {
                "i386", "i486", "i586", "i686", "x86_64", "aarch64", "armv7hl",
                "ppc64le", "s390x", "riscv64", "noarch",
            }:
                return package_name in available_names
            return any(name.startswith(f"{package_name}.") for name in available_names)

        available.update({
            app_name for app_name, package_name in package_names.items()
            if requested_package_is_available(package_name)
        })
        return available
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return available


def fedora_package_available(app_name):
    """Check one catalog application's package against enabled Fedora repos."""
    return app_name in fedora_packages_available([app_name])


def _system_package_name(app_name):
    return fedora_app_name(app_name) if is_fedora() else arch_app_name(app_name)


def detect_install_method(app_name):
    """
    Decide how the app should be installed.
    Returns: "pacman", "paru" or None
    """

    manager = package_manager()
    if manager in {"dnf", "dnf5"}:
        if str(app_name).lower() in {"paru", "aur"}:
            return None
        catalog_name = str(app_name)
        if fedora_install_type(catalog_name) == "jetbrains-toolbox":
            return "fedora-archive"
        app_name = _system_package_name(app_name)
        if not app_name:
            return None
        if not fedora_package_available(catalog_name):
            return None
        return "pacman"  # Catalog source stays stable; app_install maps it to DNF.
    if manager != "pacman":
        return None

    app_name = arch_app_name(app_name)

    # Check official repos
    try:
        subprocess.run(
            ["pacman", "-Si", app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return "pacman"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Check AUR via paru
    if command_exists("paru"):
        try:
            subprocess.run(
                ["paru", "-Si", app_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return "paru"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return None


def get_install_method_from_source(source):
    if not source:
        return None
    normalized = str(source).strip().lower()
    if package_manager() in {"dnf", "dnf5"}:
        return "pacman" if normalized in {"pacman", "official", "repo", "repository", "paru", "aur"} else None
    if normalized in {"pacman", "official", "repo", "repository"}:
        return "pacman"
    if normalized in {"paru", "aur"}:
        return "paru"
    return None


def list_all_installed_apps():
    app_list = []
    app_list.extend(list_apps("pacman"))
    app_list.extend(list_apps("paru"))
    app_list.sort()
    return app_list


def list_apps(method: str):
    if method == "pacman" and package_manager() in {"dnf", "dnf5"}:
        try:
            # Match DNF's user-installed package list; listing every RPM can
            # produce thousands of rows and make the uninstaller unusable.
            result = subprocess.run(
                [package_manager(), "--cacheonly", "repoquery", "--userinstalled", "--qf", "%{name}\\n"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                check=True, timeout=30,
            )
            return [fedora_catalog_app_name(name) for name in result.stdout.splitlines()]
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # Some Fedora installations lack the repoquery command/plugin.
            # Fall back to tracked catalog apps, rather than loading every RPM.
            try:
                result = subprocess.run(
                    ["rpm", "-qa", "--qf", "%{NAME}\\n"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    check=True, timeout=10,
                )
                tracked_names = {name for name in _fedora_package_names().values() if name}
                return [fedora_catalog_app_name(name) for name in result.stdout.splitlines()
                        if name in tracked_names]
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return []
    if method == "pacman":
        cmd = ["pacman", "-Qenq"]
    elif method == "paru":
        if not command_exists("paru"):
            return []
        cmd = ["paru", "-Qemq"]
    else:
        return []
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        applist = result.stdout.splitlines()
        if package_manager() == "pacman":
            applist = [arch_catalog_app_name(name) for name in applist]
        return applist
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def is_app_installed(app_name):
    """Check if an app is installed using pacman or paru."""
    if package_manager() in {"dnf", "dnf5"}:
        catalog_app_name = app_name
        if fedora_install_type(catalog_app_name) == "jetbrains-toolbox":
            return _jetbrains_toolbox_installed()
        app_name = _system_package_name(app_name)
        if app_name:
            try:
                subprocess.run(["rpm", "-q", app_name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        return _fedora_flatpak_installed(catalog_app_name)
    app_name = arch_app_name(app_name)
    try:
        subprocess.run(["pacman", "-Q", app_name],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    if command_exists("paru"):
        try:
            subprocess.run(["paru", "-Q", app_name],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    return False


def install_paru():
    """Install paru if not already installed."""
    script_path = Path(__file__).parent.parent.resolve().joinpath("scripts", "install_paru.sh")
    if command_exists("paru"):
        return True
    if command_exists("pkexec"):
        temp_dir = Path(tempfile.mkdtemp(prefix="paru_", dir="/tmp"))
        try:
            subprocess.run(
                ["pkexec", "pacman", "-S", "--needed", "--noconfirm", "base-devel", "git", "rust"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            subprocess.run(
                ["git", "clone", "https://aur.archlinux.org/paru.git", str(temp_dir)],
                check=True
            )

            env = os.environ.copy()
            env["PACMAN_AUTH"] = "pkexec"

            subprocess.run(
                ["bash", "-lc", "makepkg -si --noconfirm --noprogressbar"],
                cwd=temp_dir,
                env=env,
                check=True
            )
            return command_exists("paru")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Paru: {e}")
            return False
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    try:
        subprocess.run(["chmod", "+x", str(script_path)], check=True)
        paru = open_terminal(script_path)
        # Poll the process in a loop
        while True:
            exit_code = paru.poll()
            if exit_code is not None:
                if exit_code == 0:
                    print("Terminal command exited successfully")
                else:
                    print(f"Terminal command failed with exit code {exit_code}")
                break
            print("Terminal command is still running...")
            time.sleep(1)  # Check every second
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Paru: {e}")
        return False


# (preference id, executable, display name, arguments, accepts command argv)
EXTERNAL_TERMINALS = [
    ("kgx", "kgx", "Console (KGX)", ["--"], True),
    ("ptyxis", "ptyxis", "Ptyxis", ["--"], True),
    ("gnome-terminal", "gnome-terminal", "GNOME Terminal", ["--"], True),
    ("konsole", "konsole", "Konsole", ["-e"], True),
    ("xfce4-terminal", "xfce4-terminal", "Xfce Terminal", ["-e"], False),
    ("xterm", "xterm", "XTerm", ["-e"], True),
    ("alacritty", "alacritty", "Alacritty", ["-e"], True),
    ("deepin-terminal", "deepin-terminal", "Deepin Terminal", ["--run-script"], False),
    ("hyper", "hyper", "Hyper", ["--"], False),
    ("putty", "putty", "PuTTY", ["-e"], False),
    ("mate-terminal", "mate-terminal", "MATE Terminal", ["--"], True),
]


def external_terminal_options():
    """Return installed external terminal choices as (id, label) pairs."""
    options = [("auto", "Automatic (first available)")]
    options.extend(
        (key, label) for key, executable, label, _, _ in EXTERNAL_TERMINALS
        if shutil.which(executable)
    )
    return options


def open_terminal(command):
    command_parts = [str(part) for part in command] if isinstance(command, (list, tuple)) else [str(command)]
    command_str = shlex.join(command_parts)
    preferred = external_terminal()
    terminals = EXTERNAL_TERMINALS
    if preferred != "auto":
        terminals = sorted(terminals, key=lambda item: item[0] != preferred)

    for _, term, _, args, accepts_argv in terminals:
        if not shutil.which(term):
            continue
        try:
            invocation = [term, *args, *command_parts] if accepts_argv else [term, *args, command_str]
            return subprocess.Popen(invocation)
        except (OSError, ValueError, subprocess.SubprocessError):
            continue

    raise RuntimeError("No supported terminal emulator found. Install one or choose an available terminal in Settings.")


def app_install(apps, command: str):
    if command == "fedora-archive" and package_manager() in {"dnf", "dnf5"}:
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "install_jetbrains_toolbox.py"
        return subprocess.Popen(
            [shutil.which("python3") or "python3", str(script_path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
    if command == "paru":
        install_command= ["paru", "-S", "--skipreview", "--needed", "--quiet", "--color", "always"]
        conflict_policy = package_conflict_policy()
        if conflict_policy == "replace":
            install_command.append("--noconfirm")
        elif conflict_policy == "ask":
            install_command.remove("--quiet")
        arch_apps = [arch_app_name(app) for app in apps] if isinstance(apps, list) else arch_app_name(apps)
        if conflict_policy == "skip":
            return _install_packages_individually(arch_apps, install_command)
        if conflict_policy == "ask":
            return _install_packages_interactively(arch_apps, install_command)
        return apps_helper(arch_apps, install_command)
    elif command == "pacman":
        if package_manager() in {"dnf", "dnf5"}:
            fedora_apps = [_system_package_name(app) for app in apps] if isinstance(apps, list) else _system_package_name(apps)
            if not fedora_apps or (isinstance(fedora_apps, list) and any(not app for app in fedora_apps)):
                return None
            conflict_policy = package_conflict_policy()
            auth_command = "sudo" if conflict_policy == "ask" else (
                "pkexec" if command_exists("pkexec") else "sudo"
            )
            command_line = [auth_command, package_manager(), "install"]
            if conflict_policy == "replace":
                command_line.extend(["-y", "--allowerasing"])
            elif conflict_policy == "skip":
                command_line.extend(["-y", "--skip-broken"])
            command_line.extend(fedora_apps)
            catalog_apps = apps if isinstance(apps, list) else [apps]
            copr_ids = list(dict.fromkeys(
                str(_fedora_app_records().get(app, {}).get("fedora_copr_id", "")).strip()
                for app in catalog_apps
                if _fedora_app_records().get(app, {}).get("fedora_copr_id")
            ))
            if copr_ids:
                commands = [
                    [auth_command, package_manager(), "copr", "enable", copr_id]
                    for copr_id in copr_ids
                ] + [command_line]
                return _run_interactive_commands(commands)
            if conflict_policy == "ask":
                return _run_interactive_command(command_line)
            if auth_command == "sudo":
                return open_terminal(command_line)
            if auth_command == "pkexec":
                return subprocess.Popen(command_line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, bufsize=1)
        install_command = ["sudo", "pacman", "-S", "--needed", "--quiet", "--color", "always"]
        conflict_policy = package_conflict_policy()
        if conflict_policy == "replace":
            install_command.append("--noconfirm")
        elif conflict_policy == "ask":
            install_command.remove("--quiet")
        arch_apps = [arch_app_name(app) for app in apps] if isinstance(apps, list) else arch_app_name(apps)
        if conflict_policy == "skip":
            return _install_packages_individually(arch_apps, install_command)
        if conflict_policy == "ask":
            return _install_packages_interactively(arch_apps, install_command)
        return apps_helper(arch_apps, install_command)
    return None


def _install_packages_individually(packages, command):
    """Keep one package conflict from cancelling the rest of an install batch."""
    if not packages:
        return None

    package_args = " ".join(shlex.quote(package) for package in packages)
    command_args = shlex.join(command)
    script = (
        "#!/usr/bin/env bash\n"
        'trap \'rm -f -- "$0"\' EXIT\n'
        "failed=0\n"
        f"packages=({package_args})\n"
        'for package in "${packages[@]}"; do\n'
        f'    if {command_args} "$package"; then\n'
        "        :\n"
        "    else\n"
        '        printf "Skipping %s after a package conflict or install error.\\n" "$package"\n'
        "        failed=1\n"
        "    fi\n"
        "done\n"
        'if (( failed )); then\n'
        '    printf "\\nSome packages were skipped. Press Enter to close this terminal."\n'
        '    read -r\n'
        'fi\n'
    )
    script_file = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="linux-manager-install-", suffix=".sh", delete=False
    )
    script_path = Path(script_file.name)
    try:
        with script_file:
            script_file.write(script)
        script_path.chmod(0o700)
        return open_terminal([str(script_path)])
    except Exception:
        script_path.unlink(missing_ok=True)
        raise


def _install_packages_interactively(packages, command):
    """Run one interactive package transaction and keep its terminal visible."""
    if not packages:
        return None

    return _run_interactive_command([*command, *packages])


def _run_interactive_command(command):
    """Run an interactive command and keep its terminal visible until acknowledged."""

    return _run_interactive_commands([command])


def _run_interactive_commands(commands):
    """Run ordered interactive commands in one terminal, stopping on failure."""

    script = (
        "#!/usr/bin/env bash\n"
        'trap \'rm -f -- "$0"\' EXIT\n'
        + " && ".join(shlex.join(command) for command in commands) + "\n"
        'status=$?\n'
        'if (( status != 0 )); then\n'
        '    printf "\\nInstallation command exited with status %s. Press Enter to close this terminal." "$status"\n'
        '    read -r\n'
        'fi\n'
        'exit "$status"\n'
    )
    script_file = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix="linux-manager-install-", suffix=".sh", delete=False
    )
    script_path = Path(script_file.name)
    try:
        with script_file:
            script_file.write(script)
        script_path.chmod(0o700)
        return open_terminal([str(script_path)])
    except Exception:
        script_path.unlink(missing_ok=True)
        raise

def remove_apps(apps, command: str):
    remove_command = []
    if command == "paru":
        remove_command.append("paru")
    elif command == "pacman":
        if package_manager() in {"dnf", "dnf5"}:
            fedora_apps = [_system_package_name(app) for app in apps] if isinstance(apps, list) else _system_package_name(apps)
            if not fedora_apps or (isinstance(fedora_apps, list) and any(not app for app in fedora_apps)):
                return None
            return apps_helper(fedora_apps, ["sudo", package_manager(), "remove", "-y"])
        remove_command.extend(["sudo", "pacman", "-Rns", "--color", "always"])
        arch_apps = [arch_app_name(app) for app in apps] if isinstance(apps, list) else arch_app_name(apps)
        return apps_helper(arch_apps, remove_command)
    remove_command.extend(["-Rns", "--color", "always"])
    arch_apps = [arch_app_name(app) for app in apps] if isinstance(apps, list) else arch_app_name(apps)
    return apps_helper(arch_apps, remove_command)


def apps_helper(apps, command):
    try:
        if type(apps) is list:
            return open_terminal([*command, *apps])
        else:
            return open_terminal([*command, apps])
    except Exception as e:
        print(e)
        return False


def add_samba_drive(share_path, mount_point, username, password):
    """Add a Samba network drive to fstab and create .smbcredentials."""
    cred_file = generate_unique_cred_path()

    # Create credentials file
    try:
        with open(cred_file, "w") as f:
            f.write(f"username={username}\npassword={password}\n")
        os.chmod(cred_file, 0o600)
    except Exception as e:
        print(f"Failed to write credentials: {e}")
        return False

    # Run the setup script with sudo
    try:
        script_path = Path(__file__).parent.parent / "scripts" / "setup_samba.sh"
        subprocess.run(
            ["pkexec", str(script_path), mount_point, share_path, str(cred_file)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Failed to setup Samba drive: {e}")
        return False

    return True


def generate_unique_cred_path(root_dir=None, max_attempts=100):
    """
    Create a unique random subdirectory under root_dir and return its
    .smbcredentials file path.
    """
    if root_dir is None:
        root_dir = Path.home().joinpath(".config", "arch-mysetup", "credentials")
    root_path = Path(root_dir)
    root_path.mkdir(mode=0o700, parents=True, exist_ok=True)
    for _ in range(max_attempts):
        random_name = f"smbcred_{secrets.token_hex(6)}"
        candidate_dir = root_path / random_name
        try:
            # Atomic create so an existing name is never reused.
            candidate_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
            return candidate_dir / ".smbcredentials"
        except FileExistsError:
            continue
        except PermissionError as e:
            raise RuntimeError(f"Permission denied while creating {candidate_dir}") from e

    raise RuntimeError("Failed to allocate a unique credentials path")


def _is_network_device(device: str) -> bool:
    """Return True when a fstab device field denotes a network source."""
    if not device:
        return False
    lowered = device.lower()
    # Windows/Samba share: //host/share
    if lowered.startswith("//"):
        return True
    # URL-style source: smb://, nfs://, webdav://, etc.
    if "://" in lowered:
        return True
    # NFS classic "host:/path" form (not a /dev node).
    if not lowered.startswith("/") and ":/" in lowered:
        return True
    return False


def parse_fstab_network_drives(fstab_path=None):
    """
    Read fstab and return entries that are backed by the network.

    An entry is considered a network drive when either:
      * its filesystem type is listed in NETWORK_FS_TYPES, or
      * its device field starts with '//' (SMB/CIFS share), contains '://'
        (NFS/SSHFS/WebDAV style URL), or uses the NFS 'host:/path' form.

    Each entry is a dict with keys:
        device, mount_point, fs_type, options, dump, pass, raw

    Returns an empty list when the file is missing or unreadable.
    """
    path = Path(fstab_path) if fstab_path else Path("/etc/fstab")
    entries = []
    if not path.exists():
        return entries
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return entries

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # fstab layout: <device> <mount> <type> <options> <dump> <pass>
        parts = line.split()
        if len(parts) < 4:
            continue
        device = parts[0]
        mount_point = parts[1]
        fs_type = parts[2].lower()
        options = parts[3]
        dump = parts[4] if len(parts) > 4 else "0"
        pass_num = parts[5] if len(parts) > 5 else "0"

        if fs_type in NETWORK_FS_TYPES or _is_network_device(device):
            entries.append({
                "device": device,
                "mount_point": mount_point,
                "fs_type": fs_type,
                "options": options,
                "dump": dump,
                "pass": pass_num,
                "raw": raw_line,
            })
    return entries


def get_mount_size(mount_point):
    """
    Determine the on-disk size of a network drive by inspecting its mount point.

    Returns ``(mounted, size_text)`` where ``mounted`` is True when the path is an
    active mount point and ``size_text`` is a human-readable usage string such as
    "12G / 50G (24%)". When the path is not mounted, returns
    ``(False, "Not mounted")``.

    Subprocess calls are guarded with timeouts so a stale/unresponsive mount never
    blocks the UI; a missing tool or failure simply falls back to "Mounted".
    """
    path = str(mount_point)
    try:
        if not os.path.ismount(path):
            return False, "Not mounted"
    except (OSError, ValueError):
        return False, "Not mounted"

    try:
        result = subprocess.run(
            ["df", "-h", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )
        lines = result.stdout.splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            # Filesystem  Size  Used  Avail  Use%  Mounted on
            if len(parts) >= 6:
                size = parts[1]
                used = parts[2]
                use_pct = parts[4]
                return True, f"{used} / {size} ({use_pct})"
        return True, "Mounted"
    except (subprocess.SubprocessError, OSError):
        return True, "Mounted"


def set_network_drive_mounted(mount_point, mount=True):
    """Mount or unmount a configured filesystem using a graphical privilege prompt."""
    auth_command = "pkexec" if command_exists("pkexec") else "sudo"
    operation = "mount" if mount else "umount"
    try:
        result = subprocess.run(
            [auth_command, operation, str(mount_point)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=90,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"{operation.capitalize()} timed out for {mount_point}.") from error
    except OSError as error:
        raise RuntimeError(f"Could not start {operation}: {error}") from error

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"{operation.capitalize()} failed."
        raise RuntimeError(message)
    return True
