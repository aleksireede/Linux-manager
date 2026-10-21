"""Install and configure Oh My Bash or Oh My Zsh for the user's login shell."""

import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path


FRAMEWORKS = {
    "bash": {
        "name": "Oh My Bash",
        "repo": "https://github.com/ohmybash/oh-my-bash.git",
        "directory": ".oh-my-bash",
        "config": ".bashrc",
        "theme_pattern": "*.theme.sh",
        "theme_key": "OSH_THEME",
        "source_file": "oh-my-bash.sh",
    },
    "zsh": {
        "name": "Oh My Zsh",
        "repo": "https://github.com/ohmyzsh/ohmyzsh.git",
        "directory": ".oh-my-zsh",
        "config": ".zshrc",
        "theme_pattern": "*.zsh-theme",
        "theme_key": "ZSH_THEME",
        "source_file": "oh-my-zsh.sh",
    },
}


def default_shell():
    """Return the user's configured login shell, such as bash or zsh."""
    try:
        shell_path = pwd.getpwuid(os.getuid()).pw_shell
    except (KeyError, OSError):
        shell_path = os.environ.get("SHELL", "")
    return Path(shell_path).name.lower()


def framework_for_default_shell():
    shell = default_shell()
    return (shell, FRAMEWORKS[shell]) if shell in FRAMEWORKS else (shell, None)


def available_login_shells():
    """Return installed Bash/Zsh executable paths accepted by /etc/shells."""
    allowed = set()
    try:
        for line in Path("/etc/shells").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                allowed.add(line)
                allowed.add(str(Path(line).resolve()))
    except OSError:
        return {}

    result = {}
    for shell in FRAMEWORKS:
        executable = shutil.which(shell)
        if executable and (executable in allowed or str(Path(executable).resolve()) in allowed):
            result[shell] = executable
    return result


def set_default_shell(shell):
    """Change the current user's login shell using a polkit authorization."""
    if shell not in FRAMEWORKS:
        raise ValueError("Choose Bash or Zsh as the default shell.")
    available = available_login_shells()
    if shell not in available:
        raise RuntimeError(f"{shell} is not installed or is not listed in /etc/shells.")
    username = pwd.getpwuid(os.getuid()).pw_name
    subprocess.run(
        ["pkexec", "chsh", "--shell", available[shell], username],
        check=True,
        timeout=60,
    )


def framework_path(shell, home=None):
    framework = FRAMEWORKS[shell]
    return (Path(home) if home else Path.home()) / framework["directory"]


def shell_config_path(shell, home=None):
    framework = FRAMEWORKS[shell]
    return (Path(home) if home else Path.home()) / framework["config"]


def is_framework_installed(shell, home=None):
    return framework_path(shell, home).joinpath(FRAMEWORKS[shell]["source_file"]).is_file()


def available_themes(shell, home=None):
    if shell not in FRAMEWORKS:
        return []
    themes_dir = framework_path(shell, home) / "themes"
    suffix = ".theme.sh" if shell == "bash" else ".zsh-theme"
    themes = []
    # Both frameworks keep themes in per-theme subdirectories (for example,
    # themes/agnoster/agnoster.theme.sh), so search recursively.
    for path in themes_dir.rglob(FRAMEWORKS[shell]["theme_pattern"]):
        if not path.is_file():
            continue
        themes.append(path.name[:-len(suffix)])
    return sorted(set(themes), key=str.casefold)


def current_theme(shell, home=None):
    if shell not in FRAMEWORKS:
        return None
    config_path = shell_config_path(shell, home)
    if not config_path.exists():
        return None
    key = FRAMEWORKS[shell]["theme_key"]
    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(rf"^\s*{re.escape(key)}=['\"]?([^'\"\s#]+)", content, re.MULTILINE)
    return match.group(1) if match else None


def _managed_block(shell, theme):
    framework = FRAMEWORKS[shell]
    home_var = "$HOME"
    directory_var = "OSH" if shell == "bash" else "ZSH"
    opening = f"# >>> Linux-Manager {framework['name']} >>>"
    closing = f"# <<< Linux-Manager {framework['name']} <<<"
    lines = [opening, f'export {directory_var}="{home_var}/{framework["directory"]}"']
    if shell == "bash":
        lines.extend([f'{framework["theme_key"]}="{theme}"', '[[ -r "$OSH/oh-my-bash.sh" ]] && source "$OSH/oh-my-bash.sh"'])
    else:
        lines.extend([f'{framework["theme_key"]}="{theme}"', '[[ -r "$ZSH/oh-my-zsh.sh" ]] && source "$ZSH/oh-my-zsh.sh"'])
    lines.append(closing)
    return "\n".join(lines)


def set_theme(shell, theme, home=None):
    if shell not in FRAMEWORKS or not is_framework_installed(shell, home):
        raise RuntimeError("Install the shell framework before choosing a theme.")
    if theme not in available_themes(shell, home):
        raise ValueError(f"Theme '{theme}' is not included with {FRAMEWORKS[shell]['name']}.")

    config_path = shell_config_path(shell, home)
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    block = _managed_block(shell, theme)
    opening = block.splitlines()[0]
    closing = block.splitlines()[-1]
    start = original.find(opening)
    if start >= 0:
        end = original.find(closing, start)
        if end >= 0:
            end += len(closing)
            content = original[:start] + block + original[end:]
            block = ""
        else:
            content = original.rstrip()
    else:
        content = original.rstrip()

    if start < 0 and "# >>> Linux-Manager shell configs >>>" in content:
        shell_config_start = content.find("# >>> Linux-Manager shell configs >>>")
        content = (
            content[:shell_config_start].rstrip()
            + "\n\n"
            + block
            + "\n\n"
            + content[shell_config_start:].lstrip()
        )
        block = ""

    if start < 0 and content:
        framework = FRAMEWORKS[shell]
        theme_key = framework["theme_key"]
        theme_assignment = re.compile(rf"^\s*{re.escape(theme_key)}=.*$", re.MULTILINE)
        source_line = re.compile(
            rf"^\s*(?:source|\.)\s+.*{re.escape(framework['source_file'])}.*$",
            re.MULTILINE,
        )
        if theme_assignment.search(content) and source_line.search(content):
            content = theme_assignment.sub(f'{theme_key}="{theme}"', content, count=1)
            block = ""
        elif source_line.search(content):
            content = source_line.sub(
                f'{theme_key}="{theme}"\n\\g<0>', content, count=1
            )
            block = ""

    backup_path = config_path.with_name(config_path.name + ".linux-manager-backup")
    if config_path.exists() and not backup_path.exists():
        shutil.copy2(config_path, backup_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if block:
        content = f"{content}\n\n{block}" if content else block
    config_path.write_text(content.rstrip() + "\n", encoding="utf-8")


def install_framework(shell, home=None):
    if shell not in FRAMEWORKS:
        raise RuntimeError(f"The default shell '{shell or 'unknown'}' is not supported. Choose Bash or Zsh as your login shell.")
    framework = FRAMEWORKS[shell]
    home_path = Path(home) if home else Path.home()
    target = framework_path(shell, home_path)
    if target.exists():
        if not target.joinpath(".git").is_dir() or not target.joinpath(framework["source_file"]).is_file():
            raise RuntimeError(f"{target} already exists but is not a valid {framework['name']} installation.")
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1", framework["repo"], str(target)],
            check=True,
            timeout=300,
        )
    themes = available_themes(shell, home_path)
    if not themes:
        raise RuntimeError(f"No themes were found in the {framework['name']} installation.")
    theme = current_theme(shell, home_path)
    if theme not in themes:
        theme = "font" if shell == "bash" and "font" in themes else "robbyrussell" if "robbyrussell" in themes else themes[0]
    set_theme(shell, theme, home_path)
    return theme
