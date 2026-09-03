"""Sway / SwayFX backend — enumerate outputs and swap wallpapers without a black flash.

`swaymsg -t get_outputs` gives native pixel sizes. The swap itself deliberately does
*not* go through `swaymsg output <name> bg`: sway's handler for that command destroys
the running swaybg client and forks a replacement, so between the destroy and the new
client's first frame there is no background layer surface at all and sway paints its
default black. That gap is invisible under a fullscreen window but shows up as a flash
in gaps, borders and around floating windows (#13).

Instead we own the swaybg client ourselves: start the new instance, let it map, and only
then stop the previous one. Layer surfaces stack in creation order, so the new wallpaper
is already covering the old one before anything is torn down — no black frame.

Each swaybg runs in its own transient systemd user unit when a user manager is present,
so it outlives the oneshot `greyline.service` that spawned it (a `Type=oneshot` unit
takes its whole cgroup down on exit). Two unit names per output alternate, so the new
instance can be up before the old one is stopped. Without systemd the instance is a
plain detached child tracked by a pidfile.

If swaybg is not on PATH we fall back to `swaymsg output bg` — correct, but it flashes.

Neither $SWAYSOCK nor $WAYLAND_DISPLAY need to be in the environment (a systemd user
service may not have inherited them): both are auto-discovered under $XDG_RUNTIME_DIR.
"""

import contextlib
import glob
import json
import os
import shutil
import signal
import subprocess
import time

SETTLE_ENV = "GREYLINE_SWAYBG_SETTLE"
DEFAULT_SETTLE = 0.5
_SLOTS = ("a", "b")


def _runtime_base():
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def _swaysock():
    s = os.environ.get("SWAYSOCK")
    if s and os.path.exists(s):
        return s
    matches = sorted(glob.glob(os.path.join(_runtime_base(), "sway-ipc.*.sock")))
    return matches[0] if matches else None


def _wayland_display():
    """$WAYLAND_DISPLAY, or the socket name discovered under $XDG_RUNTIME_DIR.

    swaybg is started by the *user manager* under systemd, whose environment may not
    carry WAYLAND_DISPLAY, so we always pass it through explicitly."""
    d = os.environ.get("WAYLAND_DISPLAY")
    if d:
        return d
    socks = sorted(
        s for s in glob.glob(os.path.join(_runtime_base(), "wayland-*")) if not s.endswith(".lock")
    )
    return os.path.basename(socks[0]) if socks else None


def available():
    return _swaysock() is not None and shutil.which("swaymsg") is not None


def _run(args):
    env = dict(os.environ)
    sock = _swaysock()
    if sock:
        env["SWAYSOCK"] = sock
    return subprocess.run(["swaymsg", *args], capture_output=True, text=True, check=True, env=env)


def outputs():
    raw = _run(["-t", "get_outputs", "-r"]).stdout
    result = []
    for o in json.loads(raw):
        if not o.get("active", False):
            continue
        mode = o.get("current_mode") or {}
        scale = float(o.get("scale", 1.0) or 1.0)
        w = mode.get("width")
        h = mode.get("height")
        if not w or not h:
            rect = o.get("rect", {})
            w = round(rect.get("width", 0) * scale)
            h = round(rect.get("height", 0) * scale)
        if w and h:
            result.append({"name": o["name"], "width": w, "height": h, "scale": scale})
    return result


def _swaybg():
    return os.environ.get("GREYLINE_SWAYBG") or shutil.which("swaybg")


def _settle():
    """Seconds to let a new swaybg map before retiring the old one.

    A fixed delay rather than a readiness signal: swaybg has no IPC, and sway's IPC does
    not expose layer surfaces. Overshooting only costs two wallpapers in memory for that
    long; undershooting brings the flash back, hence the generous default."""
    try:
        return max(0.0, float(os.environ.get(SETTLE_ENV, DEFAULT_SETTLE)))
    except ValueError:
        return DEFAULT_SETTLE


def _has_user_manager():
    """True if a systemd user manager is running for us — the same private socket
    systemctl itself looks for, so this costs no subprocess."""
    return shutil.which("systemd-run") is not None and os.path.exists(
        os.path.join(_runtime_base(), "systemd", "private")
    )


def _unit(name, slot):
    return f"greyline-bg-{name}-{slot}"


def _systemctl(*args):
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def _active_slot(name):
    """The slot whose unit currently holds this output's wallpaper, or None."""
    units = [_unit(name, s) for s in _SLOTS]
    states = _systemctl("is-active", *units).stdout.split()
    for slot, state in zip(_SLOTS, states, strict=False):
        if state in ("active", "activating"):
            return slot
    return None


def _spawn_systemd(name, png_path, exe, display):
    old = _active_slot(name)
    new = _SLOTS[1] if old == _SLOTS[0] else _SLOTS[0]
    unit = _unit(name, new)
    # A leftover from a crashed session would make systemd-run refuse the name.
    _systemctl("stop", unit)
    _systemctl("reset-failed", unit)
    cmd = ["systemd-run", "--user", "--quiet", "--collect", f"--unit={unit}"]
    cmd += [f"--description=greyline wallpaper for output {name}"]
    if display:
        cmd += [f"--setenv=WAYLAND_DISPLAY={display}"]
    cmd += ["--", exe, "-o", name, "-i", png_path, "-m", "fill"]
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    time.sleep(_settle())
    if _systemctl("is-active", "--quiet", unit).returncode != 0:
        raise RuntimeError(f"swaybg unit {unit} did not stay up (old wallpaper left in place)")
    if old:
        _systemctl("stop", _unit(name, old))


def _pidfile(name):
    d = os.path.join(_runtime_base(), "greyline")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"swaybg-{name}.pid")


def _recorded_pid(path):
    """The pid in ``path`` if it is still a live swaybg, else None — pids get reused,
    and greyline is a fresh process per tick so the file is all we carry over."""
    try:
        with open(path, encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return pid if b"swaybg" in f.read() else None
    except OSError:  # no procfs (non-Linux) — a bare liveness check is the best we can do
        try:
            os.kill(pid, 0)
        except OSError:
            return None
        return pid


def _write_pid(path, pid):
    if pid is None:
        with contextlib.suppress(OSError):
            os.remove(path)
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(pid))


def _spawn_child(name, png_path, exe, display):
    path = _pidfile(name)
    old = _recorded_pid(path)
    env = dict(os.environ)
    if display:
        env["WAYLAND_DISPLAY"] = display
    proc = subprocess.Popen(
        [exe, "-o", name, "-i", png_path, "-m", "fill"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    # Record the new pid before settling, not after: if greyline is killed mid-handover
    # the next tick still knows what to retire instead of orphaning it.
    _write_pid(path, proc.pid)
    time.sleep(_settle())
    if proc.poll() is not None:
        _write_pid(path, old)
        raise RuntimeError(
            f"swaybg exited with {proc.returncode} for output {name} (old wallpaper left in place)"
        )
    if old and old != proc.pid:
        with contextlib.suppress(OSError):
            os.kill(old, signal.SIGTERM)


def apply(name, png_path):
    exe = _swaybg()
    if not exe:
        _run(["output", name, "bg", png_path, "fill"])
        return
    display = _wayland_display()
    if _has_user_manager():
        _spawn_systemd(name, png_path, exe, display)
    else:
        _spawn_child(name, png_path, exe, display)


def notes():
    if not _swaybg():
        return [
            "swaybg not on PATH — falling back to `swaymsg output bg`, which briefly "
            "blanks the background to black on every update. Install swaybg to fix."
        ]
    how = "transient systemd user units" if _has_user_manager() else "detached child processes"
    return [f"flash-free swaps: greyline owns swaybg via {how}"]
