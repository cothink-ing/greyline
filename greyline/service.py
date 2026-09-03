"""systemd user timer generation + lifecycle — so `greyline enable` replaces the
old "git clone the repo to grab the units, install, daemon-reload, enable" dance.

The unit text is generated here (one source of truth); the files under systemd/ in
the repo remain only as reference for people who prefer to install them by hand.
"""

import os
import shutil
import subprocess
import sys

UNIT_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "systemd",
    "user",
)


def greyline_bin():
    """Absolute path to the greyline executable for ExecStart."""
    return shutil.which("greyline") or os.path.realpath(sys.argv[0])


def service_unit():
    """The oneshot unit the timer fires.

    `ConditionFileIsExecutable` is what makes an uninstall survivable. No package
    manager can remove these units — greyline wrote them into the user's home after
    install, and pipx has no post-uninstall hook — so `pipx uninstall greyline` leaves
    an enabled timer pointing at a binary that is gone. Without the condition that is a
    *failed* unit every single minute, forever. With it, systemd sees the missing
    executable and skips the unit instead, which is silent and harmless. Cleaning up
    properly is still `greyline disable`; this is what happens when nobody does.
    """
    return f"""[Unit]
Description=Render the greyline world-time wallpaper
After=graphical-session.target
PartOf=graphical-session.target
# Skip (not fail) if greyline has been uninstalled from under us.
ConditionFileIsExecutable={greyline_bin()}

[Service]
Type=oneshot
ExecStart={greyline_bin()}
"""


def timer_unit(interval="*:*:00"):
    return f"""[Unit]
Description=Update the greyline world-time wallpaper on a schedule

[Timer]
OnCalendar={interval}
# Fire within 1s of :00 — a visible clock can't drift; one timer/min = negligible power.
AccuracySec=1s
Persistent=true

[Install]
WantedBy=timers.target
"""


def systemd_user_available():
    """True if a systemd user instance is usable (systemctl --user responds)."""
    if not shutil.which("systemctl"):
        return False
    r = subprocess.run(
        ["systemctl", "--user", "is-system-running"],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0 or r.stdout.strip() in {"running", "degraded", "starting"}


def _systemctl(*args):
    subprocess.run(["systemctl", "--user", *args], check=True)


def install_and_enable(interval="*:*:00", dry_run=False):
    """Write the units and enable+start the timer. Returns a list of action strings."""
    svc = os.path.join(UNIT_DIR, "greyline.service")
    tmr = os.path.join(UNIT_DIR, "greyline.timer")
    actions = [
        f"write {svc}",
        f"write {tmr}  (OnCalendar={interval})",
        "systemctl --user daemon-reload",
        "systemctl --user enable --now greyline.timer",
    ]
    if dry_run:
        return actions
    os.makedirs(UNIT_DIR, exist_ok=True)
    with open(svc, "w", encoding="utf-8") as f:
        f.write(service_unit())
    with open(tmr, "w", encoding="utf-8") as f:
        f.write(timer_unit(interval))
    _systemctl("daemon-reload")
    _systemctl("enable", "--now", "greyline.timer")
    return actions


def disable():
    """Undo install_and_enable completely — including the unit files it wrote.

    `enable` writes two files and creates an enable symlink; `disable` used to remove
    only the symlink, leaving the units behind to be rediscovered later. Removing what
    we wrote is the other half of owning it, and it is what makes
    `greyline disable && pipx uninstall greyline` a clean removal.

    Returns the paths it removed.
    """
    _systemctl("disable", "--now", "greyline.timer")
    removed = []
    for name in ("greyline.timer", "greyline.service"):
        path = os.path.join(UNIT_DIR, name)
        if os.path.isfile(path):
            os.remove(path)
            removed.append(path)
    if removed:
        _systemctl("daemon-reload")
    return removed


def user_state_paths():
    """Everything greyline writes outside its own package, for `disable --purge`."""
    from . import cache, config

    return [os.path.dirname(config.user_config_path()), cache.cache_dir()]


def purge():
    """Remove the config and cache directories. Returns the paths it removed."""
    import shutil as _shutil

    removed = []
    for path in user_state_paths():
        if os.path.isdir(path):
            _shutil.rmtree(path)
            removed.append(path)
    return removed


def status():
    subprocess.run(["systemctl", "--user", "list-timers", "greyline.timer", "--no-pager"])
