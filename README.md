# Linux-Manager

Linux-Manager is a desktop application for installing and removing applications, managing network drives, applying system tweaks, and updating an Arch Linux or Fedora system.

## Supported systems

- Arch Linux and Arch-based distributions using `pacman` (and optionally `paru` for AUR packages).
- Fedora Linux using DNF or DNF5. Fedora-only applications are shown when their package source is configured; Arch-only applications are hidden.

## Install

Run the setup script from a terminal:

```bash
wget -qO- https://raw.githubusercontent.com/aleksireede/arch-mysetup/refs/heads/main/main/setup.sh | bash
```

The setup script installs the system dependencies on Arch or Fedora (DNF and DNF5), installs Linux-Manager under `/opt/linux-manager`, and creates the `linux-manager` and `linux-manager-update` commands. It also installs the application menu entry and icon, then starts the application when setup completes. The updater refreshes the launcher, menu entry, and icon after updating the app.

Fedora RPMs are versioned from the matching Git release tag. The `linux-manager-update` command updates an RPM installation through DNF or DNF5, and RPM releases install over the same `/opt/linux-manager` files used by the setup command. Both installation methods record the installed application version in `/opt/linux-manager/VERSION`.

## Run and update

Start Linux-Manager from your application menu or run:

```bash
linux-manager
```

To update an existing installation:

```bash
linux-manager-update
```

## Application catalog

Applications and their distribution-specific package names are maintained in [`bin/app.yaml`](bin/app.yaml). Set `arch_app_name` and `fedora_app_name` when the package names differ. Use `null` for a distribution when the application has no supported package source there. Fedora repository and signing key setup is available from the Apps page.
