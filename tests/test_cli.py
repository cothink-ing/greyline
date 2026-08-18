"""CLI plumbing: DE recipe detection, systemd unit generation, init, watch loop."""

import pytest

from worldtime import __main__ as cli
from worldtime import config, recipes, service

# --- argument parsing ---


def test_parse_res_valid():
    assert cli._parse_res("2560x1440") == (2560, 1440)
    assert cli._parse_res("1920X1080") == (1920, 1080)  # case-insensitive


def test_parse_res_malformed_exits_cleanly():
    # Regression: a bad --res must give a clean SystemExit, not a raw ValueError traceback.
    for bad in ("1920", "1920xABC", "1920x1080x2"):
        with pytest.raises(SystemExit):
            cli._parse_res(bad)


# --- recipes ---


def test_detect_desktop_matches_case_insensitively():
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}) == "gnome"
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "KDE"}) == "kde"
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "XFCE"}) == "xfce"
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "sway"}) is None
    assert recipes.detect_desktop({}) is None


def test_all_recipes_have_path_placeholder():
    assert all("{path}" in cmd for cmd in recipes.RECIPES.values())


# --- systemd unit generation ---


def test_service_unit_execstart_and_timer(monkeypatch):
    monkeypatch.setattr(service, "greyline_bin", lambda: "/opt/bin/greyline")
    svc = service.service_unit()
    assert "ExecStart=/opt/bin/greyline" in svc
    assert "Type=oneshot" in svc
    tmr = service.timer_unit(interval="*:0/5:00")
    assert "OnCalendar=*:0/5:00" in tmr
    assert "AccuracySec=1s" in tmr  # tight accuracy so the clock updates on time (#12)
    assert "WantedBy=timers.target" in tmr


def test_install_and_enable_dry_run_lists_actions_without_writing(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "UNIT_DIR", str(tmp_path / "systemd"))
    actions = service.install_and_enable(interval="*:*:00", dry_run=True)
    assert any("daemon-reload" in a for a in actions)
    assert any("enable --now greyline.timer" in a for a in actions)
    assert not (tmp_path / "systemd").exists()  # nothing written in dry-run


# --- command-backend ping-pong buffers (#11) ---


def test_output_path_stable_for_native_backends(tmp_path):
    # Native backends read file contents live, so they keep one stable filename.
    assert cli._output_path(str(tmp_path), "eDP-1", rotate=False) == str(tmp_path / "eDP-1.png")


def test_output_path_pingpongs_between_two_buffers(tmp_path):
    import os

    rt = str(tmp_path)
    pa, pb = tmp_path / "screen-a.png", tmp_path / "screen-b.png"

    # Tick 1: neither buffer exists -> pick -a.
    assert cli._output_path(rt, "screen", rotate=True) == str(pa)
    pa.write_bytes(b"1")
    os.utime(pa, (1000, 1000))

    # Tick 2: -a is newest -> hand the DE the *other* path (-b) so it refreshes.
    assert cli._output_path(rt, "screen", rotate=True) == str(pb)
    pb.write_bytes(b"2")
    os.utime(pb, (2000, 2000))

    # Tick 3: -a is now older -> swap back. Bounded to 2 files: no accumulation.
    assert cli._output_path(rt, "screen", rotate=True) == str(pa)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["screen-a.png", "screen-b.png"]


# --- init ---


def test_init_writes_config_and_detected_backend(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.toml"
    monkeypatch.setattr(cli.backends, "detect", lambda: "sway")
    monkeypatch.setattr(cli.service, "systemd_user_available", lambda: False)
    rc = cli.main(["--config", str(cfg_path), "init"])
    assert rc == 0 and cfg_path.exists()
    assert config.load(str(cfg_path))["backend"] == "sway"


def test_init_uses_command_recipe_for_gnome(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.toml"
    monkeypatch.setattr(cli.backends, "detect", lambda: None)
    monkeypatch.setattr(cli.recipes, "detect_desktop", lambda: "gnome")
    monkeypatch.setattr(cli.service, "systemd_user_available", lambda: False)
    rc = cli.main(["--config", str(cfg_path), "init"])
    assert rc == 0
    c = config.load(str(cfg_path))
    assert c["backend"] == "command"
    assert c["command"] == recipes.RECIPES["gnome"]


def test_init_prefers_de_recipe_over_x11_fallback(monkeypatch, tmp_path):
    # Regression: on a full DE (GNOME/KDE/XFCE) that draws its own wallpaper, the
    # generic x11 root-window backend is silently overpainted by the compositor. If
    # feh/xwallpaper is installed, backends.detect() returns "x11" — but init must
    # still pick the DE's gsettings/xfconf/plasma recipe, not x11.
    cfg_path = tmp_path / "config.toml"
    monkeypatch.setattr(cli.backends, "detect", lambda: "x11")
    monkeypatch.setattr(cli.recipes, "detect_desktop", lambda: "gnome")
    monkeypatch.setattr(cli.service, "systemd_user_available", lambda: False)
    rc = cli.main(["--config", str(cfg_path), "init"])
    assert rc == 0
    c = config.load(str(cfg_path))
    assert c["backend"] == "command"
    assert c["command"] == recipes.RECIPES["gnome"]


def test_init_keeps_x11_when_not_a_desktop_environment(monkeypatch, tmp_path):
    # A bare X11 window manager (no gnome/kde/xfce token) must still get the x11 backend.
    cfg_path = tmp_path / "config.toml"
    monkeypatch.setattr(cli.backends, "detect", lambda: "x11")
    monkeypatch.setattr(cli.recipes, "detect_desktop", lambda: None)
    monkeypatch.setattr(cli.service, "systemd_user_available", lambda: False)
    rc = cli.main(["--config", str(cfg_path), "init"])
    assert rc == 0
    assert config.load(str(cfg_path))["backend"] == "x11"


def test_init_dry_run_writes_nothing(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.toml"
    monkeypatch.setattr(cli.backends, "detect", lambda: "sway")
    monkeypatch.setattr(cli.service, "systemd_user_available", lambda: False)
    rc = cli.main(["--config", str(cfg_path), "init", "--dry-run"])
    assert rc == 0 and not cfg_path.exists()


# --- watch ---


def test_render_flags_work_before_and_after_subcommand():
    # Regression: argparse parent/subparser default-clobber must not drop --backend.
    parse = cli.build_parser().parse_args
    for argv in (
        ["watch", "--backend", "command", "--command", "cp {path} x"],
        ["--backend", "command", "--command", "cp {path} x", "watch"],
    ):
        a = parse(argv)
        assert a.backend == "command" and a.command == "cp {path} x"
    assert parse(["watch"]).backend is None  # unset stays None


def test_watch_loops_run_apply_until_interrupted(monkeypatch):
    calls = {"n": 0}

    def fake_apply(args):
        calls["n"] += 1
        return 0

    def fake_sleep(_):
        raise KeyboardInterrupt  # break the loop after the first render

    monkeypatch.setattr(cli, "run_apply", fake_apply)
    monkeypatch.setattr("time.sleep", fake_sleep)
    rc = cli.main(["watch", "--interval", "60"])
    assert rc == 0 and calls["n"] == 1


# --- help ---


def test_help_command_prints_that_commands_help(capsys):
    # `greyline help city add` must reach the nested subparser, not the root parser.
    assert cli.main(["help", "city", "add"]) == 0
    out = capsys.readouterr().out
    assert "greyline city add" in out
    assert "IANA timezone" in out  # the positional's own help, not just the usage line


def test_help_bare_prints_the_command_list(capsys):
    assert cli.main(["help"]) == 0
    out = capsys.readouterr().out
    assert "greyline help topics" in out
    for name in ("init", "watch", "config", "city", "doctor", "help"):
        assert name in out


def test_help_topics_render_from_live_data(capsys):
    # The reference pages are generated from the same data the renderer uses, so a
    # new theme / recipe / backend shows up without touching the help text.
    assert cli.main(["help", "themes"]) == 0
    assert "modus" in capsys.readouterr().out
    assert cli.main(["help", "desktops"]) == 0
    assert recipes.RECIPES["kde"] in capsys.readouterr().out
    assert cli.main(["help", "keys"]) == 0
    keys = capsys.readouterr().out
    assert "twilight" in keys and "darkness" in keys
    assert "[[city]]\nname =" not in keys  # the city list is `greyline city`'s job


def test_help_topic_list_matches_the_topics_epilog_advertises():
    from worldtime import helptext

    for name in helptext.topic_names():
        assert name in helptext.HELP_EPILOG
        assert helptext.render_topic(name)


def test_help_prefers_commands_over_topics(capsys):
    # `config` is both a command and the subject of the `keys` page — the command wins.
    assert cli.main(["help", "config"]) == 0
    assert "greyline config set" in capsys.readouterr().out


def test_help_unknown_topic_exits_nonzero_with_a_pointer(capsys):
    assert cli.main(["help", "nonsense"]) == 1
    assert "greyline help topics" in capsys.readouterr().err


def test_bare_config_and_city_print_help_instead_of_an_argparse_error(capsys):
    # argparse's "the following arguments are required" helps nobody here.
    for argv in (["config"], ["city"]):
        assert cli.main(argv) == 1
        assert "Examples:" in capsys.readouterr().out
