"""Command backend: availability gating, output sizing, and {path}/{output} substitution.

Also covers the sway backend's flash-free swaybg handover (the ordering is the whole
point: the new instance must be up *before* the old one is stopped), and the
Windows/macOS backends (beta, untested on real hardware): these tests mock the OS calls
so their command construction and platform gating are verified on any OS the suite runs
on.
"""

import glob
import types
from pathlib import Path

import pytest

from worldtime.backends import command, macos, sway, swww, windows


def test_available_requires_command(monkeypatch):
    monkeypatch.delenv("GREYLINE_COMMAND", raising=False)
    assert command.available() is False
    monkeypatch.setenv("GREYLINE_COMMAND", "feh --bg-fill {path}")
    assert command.available() is True


def test_outputs_uses_explicit_resolution(monkeypatch):
    monkeypatch.setenv("GREYLINE_RESOLUTION", "2560x1440")
    outs = command.outputs()
    assert outs == [{"name": "screen", "width": 2560, "height": 1440, "scale": 1.0}]


def test_outputs_falls_back_to_default_without_xrandr(monkeypatch):
    monkeypatch.delenv("GREYLINE_RESOLUTION", raising=False)
    monkeypatch.setattr(command._util, "xrandr_outputs", lambda: [])
    outs = command.outputs()
    assert outs == [{"name": "screen", "width": 1920, "height": 1080, "scale": 1.0}]


def test_outputs_prefers_largest_xrandr_output(monkeypatch):
    monkeypatch.delenv("GREYLINE_RESOLUTION", raising=False)
    monkeypatch.setattr(
        command._util,
        "xrandr_outputs",
        lambda: [
            {"name": "HDMI-1", "width": 1920, "height": 1080, "scale": 1.0},
            {"name": "DP-1", "width": 3840, "height": 2160, "scale": 1.0},
        ],
    )
    w, h = command.outputs()[0]["width"], command.outputs()[0]["height"]
    assert (w, h) == (3840, 2160)


def test_apply_substitutes_path_and_output(monkeypatch):
    calls = {}

    def fake_run(cmd, shell=False, check=False):
        calls["cmd"], calls["shell"], calls["check"] = cmd, shell, check

    monkeypatch.setenv("GREYLINE_COMMAND", "set-wp --output {output} --img {path}")
    monkeypatch.setattr(command.subprocess, "run", fake_run)
    command.apply("DP-1", "/run/greyline/DP-1.png")
    assert calls["cmd"] == "set-wp --output DP-1 --img /run/greyline/DP-1.png"
    assert calls["shell"] is True and calls["check"] is True


def test_apply_without_command_errors(monkeypatch):
    monkeypatch.delenv("GREYLINE_COMMAND", raising=False)
    with pytest.raises(RuntimeError):
        command.apply("screen", "/tmp/x.png")




def test_windows_available_gates_on_platform(monkeypatch):
    monkeypatch.setattr(windows.sys, "platform", "win32")
    assert windows.available() is True
    monkeypatch.setattr(windows.sys, "platform", "linux")
    assert windows.available() is False


def test_windows_apply_calls_systemparametersinfo(monkeypatch):
    import ctypes

    calls = {}

    class _FakeUser32:
        def SystemParametersInfoW(self, action, uiParam, pvParam, fWinIni):
            calls["args"] = (action, uiParam, pvParam, fWinIni)
            return 1

    class _FakeWindll:
        user32 = _FakeUser32()

    monkeypatch.setattr(ctypes, "windll", _FakeWindll(), raising=False)
    windows.apply("default", r"C:\Users\me\AppData\greyline\default.png")
    action, _uiParam, pvParam, fWinIni = calls["args"]
    assert action == windows.SPI_SETDESKWALLPAPER
    assert pvParam == r"C:\Users\me\AppData\greyline\default.png"
    assert fWinIni == windows.SPIF_UPDATEINIFILE | windows.SPIF_SENDCHANGE


def test_windows_apply_raises_on_failure(monkeypatch):
    import ctypes

    class _FakeUser32:
        def SystemParametersInfoW(self, *a):
            return 0

    class _FakeWindll:
        user32 = _FakeUser32()

    monkeypatch.setattr(ctypes, "windll", _FakeWindll(), raising=False)
    monkeypatch.setattr(
        ctypes, "WinError", lambda code=None: RuntimeError("winerror"), raising=False
    )
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    with pytest.raises(RuntimeError):
        windows.apply("default", "C:/x.png")




def test_macos_available_gates_on_platform(monkeypatch):
    monkeypatch.setattr(macos.sys, "platform", "darwin")
    assert macos.available() is True
    monkeypatch.setattr(macos.sys, "platform", "linux")
    assert macos.available() is False


def test_macos_apply_rotates_path_and_runs_osascript(monkeypatch, tmp_path):
    src = tmp_path / "default.png"
    src.write_bytes(b"PNGDATA")

    calls = {}

    def fake_run(cmd, capture_output=False, text=False, check=False):
        calls["cmd"] = cmd

    monkeypatch.setattr(macos.subprocess, "run", fake_run)
    macos.apply("default", str(src))

    assert calls["cmd"][0] == "osascript" and calls["cmd"][1] == "-e"
    script = calls["cmd"][2]
    assert "set picture of every desktop" in script

    rotated = glob.glob(str(tmp_path / f"{macos._ROTATE_PREFIX}*.png"))
    assert len(rotated) == 1
    assert rotated[0] != str(src)
    assert f'POSIX file "{rotated[0]}"' in script
    assert Path(rotated[0]).read_bytes() == b"PNGDATA"


def test_macos_rotate_prunes_previous_copies(monkeypatch, tmp_path):
    src = tmp_path / "default.png"
    src.write_bytes(b"A")
    stale = tmp_path / f"{macos._ROTATE_PREFIX}old.png"
    stale.write_bytes(b"old")

    monkeypatch.setattr(macos.subprocess, "run", lambda *a, **k: None)
    macos.apply("default", str(src))

    assert not stale.exists()
    assert len(glob.glob(str(tmp_path / f"{macos._ROTATE_PREFIX}*.png"))) == 1


class _FakeRun:
    """Records subprocess.run calls and answers the handful of queries the sway
    backend makes: `systemctl is-active <a> <b>` (which slot holds the wallpaper) and
    `systemctl is-active --quiet <unit>` (did the new one stay up)."""

    def __init__(self, slot_states=("inactive", "inactive"), stays_up=True):
        self.slot_states = slot_states
        self.stays_up = stays_up
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        if cmd[:3] == ["systemctl", "--user", "is-active"]:
            if "--quiet" in cmd:
                return types.SimpleNamespace(returncode=0 if self.stays_up else 1, stdout="")
            return types.SimpleNamespace(returncode=0, stdout="\n".join(self.slot_states))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    def find(self, *prefix):
        return [c for c in self.calls if c[: len(prefix)] == list(prefix)]


@pytest.fixture
def no_settle(monkeypatch):
    monkeypatch.setenv(sway.SETTLE_ENV, "0")


def test_sway_available_needs_socket_and_swaymsg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("SWAYSOCK", raising=False)
    monkeypatch.setattr(sway.shutil, "which", lambda _: "/bin/swaymsg")
    assert sway.available() is False
    (tmp_path / "sway-ipc.1000.1.sock").write_text("")
    assert sway.available() is True
    monkeypatch.setattr(sway.shutil, "which", lambda _: None)
    assert sway.available() is False


def test_sway_outputs_skips_inactive_and_reads_native_pixels(monkeypatch):
    payload = (
        '[{"name": "eDP-1", "active": true, "scale": 2.0, '
        '"current_mode": {"width": 2880, "height": 1800}}, '
        '{"name": "HDMI-A-1", "active": false, "current_mode": {"width": 1920, "height": 1080}}, '
        '{"name": "DP-1", "active": true, "scale": 1.5, "rect": {"width": 1280, "height": 800}}]'
    )
    monkeypatch.setattr(sway, "_run", lambda args: types.SimpleNamespace(stdout=payload))
    assert sway.outputs() == [
        {"name": "eDP-1", "width": 2880, "height": 1800, "scale": 2.0},
        {"name": "DP-1", "width": 1920, "height": 1200, "scale": 1.5},
    ]


def test_sway_apply_falls_back_to_swaymsg_without_swaybg(monkeypatch):
    monkeypatch.delenv("GREYLINE_SWAYBG", raising=False)
    monkeypatch.setattr(sway.shutil, "which", lambda _: None)
    seen = []
    monkeypatch.setattr(sway, "_run", lambda args: seen.append(args))
    sway.apply("eDP-1", "/run/greyline/eDP-1.png")
    assert seen == [["output", "eDP-1", "bg", "/run/greyline/eDP-1.png", "fill"]]


def test_sway_apply_starts_new_unit_before_stopping_old(monkeypatch, no_settle):
    monkeypatch.setenv("GREYLINE_SWAYBG", "/bin/swaybg")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setattr(sway, "_has_user_manager", lambda: True)
    fake = _FakeRun(slot_states=("active", "inactive"))
    monkeypatch.setattr(sway.subprocess, "run", fake)

    sway.apply("eDP-1", "/run/greyline/eDP-1.png")

    started = fake.find("systemd-run")
    assert len(started) == 1
    # slot a was live, so the new instance takes slot b
    assert "--unit=greyline-bg-eDP-1-b" in started[0]
    assert "--setenv=WAYLAND_DISPLAY=wayland-1" in started[0]
    assert started[0][-8:] == [
        "--",
        "/bin/swaybg",
        "-o",
        "eDP-1",
        "-i",
        "/run/greyline/eDP-1.png",
        "-m",
        "fill",
    ]
    stops = [c for c in fake.calls if c[:3] == ["systemctl", "--user", "stop"]]
    # the old slot is only stopped after the new unit is running
    assert stops[-1] == ["systemctl", "--user", "stop", "greyline-bg-eDP-1-a"]
    assert fake.calls.index(started[0]) < fake.calls.index(stops[-1])


def test_sway_apply_keeps_old_wallpaper_when_new_unit_dies(monkeypatch, no_settle):
    monkeypatch.setenv("GREYLINE_SWAYBG", "/bin/swaybg")
    monkeypatch.setattr(sway, "_has_user_manager", lambda: True)
    fake = _FakeRun(slot_states=("active", "inactive"), stays_up=False)
    monkeypatch.setattr(sway.subprocess, "run", fake)

    with pytest.raises(RuntimeError):
        sway.apply("eDP-1", "/run/greyline/eDP-1.png")

    assert ["systemctl", "--user", "stop", "greyline-bg-eDP-1-a"] not in fake.calls


def test_sway_apply_child_records_pid_and_retires_the_old_one(monkeypatch, no_settle, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("GREYLINE_SWAYBG", "/bin/swaybg")
    monkeypatch.setattr(sway, "_has_user_manager", lambda: False)
    monkeypatch.setattr(sway, "_recorded_pid", lambda path: 4242)

    spawned = {}
    killed = []

    def fake_popen(cmd, **kwargs):
        spawned["cmd"], spawned["kwargs"] = cmd, kwargs
        return types.SimpleNamespace(pid=5150, poll=lambda: None, returncode=None)

    monkeypatch.setattr(sway.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sway.os, "kill", lambda pid, sig: killed.append((pid, sig)))

    sway.apply("eDP-1", "/run/greyline/eDP-1.png")

    assert spawned["cmd"] == [
        "/bin/swaybg",
        "-o",
        "eDP-1",
        "-i",
        "/run/greyline/eDP-1.png",
        "-m",
        "fill",
    ]
    assert spawned["kwargs"]["start_new_session"] is True
    assert (tmp_path / "greyline" / "swaybg-eDP-1.pid").read_text() == "5150"
    assert killed == [(4242, sway.signal.SIGTERM)]


def test_sway_apply_child_does_not_retire_old_when_new_dies(monkeypatch, no_settle, tmp_path):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("GREYLINE_SWAYBG", "/bin/swaybg")
    monkeypatch.setattr(sway, "_has_user_manager", lambda: False)
    monkeypatch.setattr(sway, "_recorded_pid", lambda path: 4242)
    killed = []
    monkeypatch.setattr(
        sway.subprocess,
        "Popen",
        lambda cmd, **kw: types.SimpleNamespace(pid=5150, poll=lambda: 1, returncode=1),
    )
    monkeypatch.setattr(sway.os, "kill", lambda pid, sig: killed.append((pid, sig)))

    with pytest.raises(RuntimeError):
        sway.apply("eDP-1", "/run/greyline/eDP-1.png")
    assert killed == []


def test_sway_recorded_pid_rejects_a_reused_pid(monkeypatch, tmp_path):
    pidfile = tmp_path / "swaybg-eDP-1.pid"
    pidfile.write_text("1")
    monkeypatch.setattr(sway.os, "kill", lambda pid, sig: None)
    assert sway._recorded_pid(str(pidfile)) is None  # pid 1 is not swaybg
    assert sway._recorded_pid(str(tmp_path / "missing.pid")) is None


def test_sway_notes_flags_a_missing_swaybg(monkeypatch):
    monkeypatch.delenv("GREYLINE_SWAYBG", raising=False)
    monkeypatch.setattr(sway.shutil, "which", lambda _: None)
    assert "swaybg not on PATH" in sway.notes()[0]
    monkeypatch.setenv("GREYLINE_SWAYBG", "/bin/swaybg")
    monkeypatch.setattr(sway, "_has_user_manager", lambda: True)
    assert "flash-free" in sway.notes()[0]


def test_swww_apply_crossfades_by_default_and_honours_overrides(monkeypatch):
    monkeypatch.setenv("SWWW", "/bin/swww")
    monkeypatch.delenv(swww.TRANSITION_ENV, raising=False)
    monkeypatch.delenv(swww.DURATION_ENV, raising=False)
    seen = []
    monkeypatch.setattr(swww.subprocess, "run", lambda cmd, **kw: seen.append(cmd))

    swww.apply("DP-1", "/run/greyline/DP-1.png")
    assert seen[-1] == [
        "/bin/swww",
        "img",
        "--outputs",
        "DP-1",
        "--transition-type",
        "fade",
        "--transition-duration",
        "0.3",
        "/run/greyline/DP-1.png",
    ]

    monkeypatch.setenv(swww.TRANSITION_ENV, "none")
    monkeypatch.setenv(swww.DURATION_ENV, "1")
    swww.apply("DP-1", "/run/greyline/DP-1.png")
    assert "none" in seen[-1] and "1" in seen[-1] and "fade" not in seen[-1]
