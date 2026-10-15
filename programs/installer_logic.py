import os
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

# Filesystem types that are backed by the network (fstab "type" field).
NETWORK_FS_TYPES = {
    "cifs", "cifs4", "smbfs", "smb", "nfs", "nfs4", "nfsv4", "nfsd",
    "sshfs", "ncpfs", "webdav", "davfs2", "dav", "ftp", "ftps",
}


def command_exists(command):
    return shutil.which(command) is not None


def package_manager():
    """Return the supported system package manager, preferring Arch when present."""
    if command_exists("pacman"):
        return "pacman"
    if command_exists("dnf"):
        return "dnf"
    return None


def detect_install_method(app_name):
    """
    Decide how the app should be installed.
    Returns: "pacman", "paru" or None
    """

    manager = package_manager()
    if manager == "dnf":
        try:
            subprocess.run(["dnf", "info", "--available", app_name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            return "pacman"  # Keep the catalog source stable; app_install maps it to dnf.
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    if manager != "pacman":
        return None

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
    if normalized in {"pacman", "official", "repo", "repository"}:
        return "pacman"
    if normalized in {"paru", "aur"}:
        return "paru"
    return None


def detect_installed_method(app_name):
    """Best-effort detection of how an installed app should be removed."""
    if package_manager() == "dnf":
        try:
            subprocess.run(["rpm", "-q", app_name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            return "pacman"  # Catalog/UI legacy name, executed as dnf below.
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    try:
        subprocess.run(
            ["pacman", "-Qm", app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return "paru" if command_exists("paru") else "pacman"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        subprocess.run(
            ["pacman", "-Q", app_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return "pacman"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def list_all_installed_apps():
    app_list = []
    app_list.extend(list_apps("pacman"))
    app_list.extend(list_apps("paru"))
    app_list.sort()
    return app_list


def list_apps(method: str):
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
        return applist
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def is_app_installed(app_name):
    """Check if an app is installed using pacman or paru."""
    if package_manager() == "dnf":
        try:
            subprocess.run(["rpm", "-q", app_name], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
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


# open a command in a terminal window
# now supports more terminals

def open_terminal(command):
    terminals = [
        ("kgx", ["--"], True),
        ("konsole", ["-e"], False),
        ("xfce4-terminal", ["-e"], False),
        ("xterm", ["-e"], False),
        ("alacritty", ["-e"], True),  # True: command is a list
        ("deepin-terminal", ["--run-script"], False),
        ("hyper", ["--"], False),
        ("putty", ["-e"], False),
        ("mate-terminal", ["--"], False),
    ]

    if isinstance(command, list):
        command_str = " ".join(command)
    else:
        command_str = command

    for term, args, use_list in terminals:
        if shutil.which(term):
            try:
                if use_list:
                    process = subprocess.Popen(
                        [term, *args, *command] if isinstance(command, list) else [term, *args, command])
                else:
                    process = subprocess.Popen([term, *args, command_str])
                return process
            except (OSError, ValueError, subprocess.SubprocessError):
                continue

    raise RuntimeError("No supported terminal emulator found")


def app_install(apps, command: str):
    if command == "paru":
        install_command= ["paru", "-S", "--skipreview", "--needed", "--quiet", "--color", "always"]
        return apps_helper(apps, install_command)
    elif command == "pacman":
        if package_manager() == "dnf":
            return apps_helper(apps, ["sudo", "dnf", "install", "-y"])
        install_command = ["sudo", "pacman", "-S", "--needed", "--quiet", "--color", "always"]
        return apps_helper(apps, install_command)
    return None

def remove_apps(apps, command: str):
    remove_command = []
    if command == "paru":
        remove_command.append("paru")
    elif command == "pacman":
        if package_manager() == "dnf":
            remove_command.extend(["sudo", "dnf", "remove", "-y"])
            return apps_helper(apps, remove_command)
        remove_command.extend(["sudo", "pacman", "-Rns", "--color", "always"])
        return apps_helper(apps, remove_command)
    remove_command.extend(["-Rns", "--color", "always"])
    return apps_helper(apps, remove_command)


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
