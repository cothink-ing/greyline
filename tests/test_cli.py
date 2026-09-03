"""CLI plumbing: DE recipe detection, systemd unit generation, init, watch loop."""

import argparse
import os
import tomllib

import pytest

from greyline import __main__ as cli
from greyline import config, recipes, service

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYPROJECT = os.path.join(ROOT, "pyproject.toml")


@pytest.mark.skipif(
    not os.path.exists(PYPROJECT), reason="pyproject ships with the repo, not the package"
)
def test_version_matches_pyproject():
    """publish.yml gates the release tag on pyproject's version and flake.nix derives
    from it, so this is the one remaining copy that could drift."""
    with open(PYPROJECT, "rb") as f:
        assert cli.__version__ == tomllib.load(f)["project"]["version"]


def test_parse_res_valid():
    assert cli._parse_res("2560x1440") == (2560, 1440)
    assert cli._parse_res("1920X1080") == (1920, 1080)


def test_parse_res_malformed_exits_cleanly():
    for bad in ("1920", "1920xABC", "1920x1080x2"):
        with pytest.raises(SystemExit):
            cli._parse_res(bad)


def test_is_substitute_accepts_the_family_fontconfig_reports():
    assert not cli._is_substitute("Iosevka Nerd Font", "Iosevka Nerd Font")
    assert not cli._is_substitute("dejavu sans", "DejaVu Sans")
    assert not cli._is_substitute("BlexMono Nerd Font Medium", "BlexMono Nerd Font")
    assert not cli._is_substitute("Noto Sans", "Noto Sans,Noto Sans Regular")


def test_is_substitute_flags_a_fontconfig_fallback():
    assert cli._is_substitute("Aporetic Sans", "DejaVu Sans")
    assert cli._is_substitute("BlexMono Nerd Font Medium", "DejaVu Sans")


def test_is_substitute_silent_when_fontconfig_is_absent():
    assert not cli._is_substitute("Aporetic Sans", None)


def test_resolve_fonts_passes_a_font_file_path_through(tmp_path):
    f = tmp_path / "Custom.ttf"
    f.write_bytes(b"")
    assert cli._resolve_fonts(str(f)) == (str(f), str(f))


def test_resolve_fonts_queries_regular_and_bold(monkeypatch):
    seen = []

    def fake_match(query):
        seen.append(query)
        return f"/fonts/{query}.ttf", "Iosevka Nerd Font"

    monkeypatch.setattr(cli, "_fc_match", fake_match)
    assert cli._resolve_fonts("Iosevka Nerd Font") == (
        "/fonts/Iosevka Nerd Font.ttf",
        "/fonts/Iosevka Nerd Font:bold.ttf",
    )
    assert seen == ["Iosevka Nerd Font", "Iosevka Nerd Font:bold"]


def test_resolve_fonts_warns_only_when_the_family_was_requested(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_fc_match", lambda q: ("/fonts/DejaVuSans.ttf", "DejaVu Sans"))
    cli._resolve_fonts("Aporetic Sans", warn=False)
    assert capsys.readouterr().err == ""
    cli._resolve_fonts("Aporetic Sans")
    assert "not installed" in capsys.readouterr().err


def test_resolve_fonts_falls_back_to_the_family_without_fontconfig(monkeypatch):
    monkeypatch.setattr(cli, "_fc_match", lambda q: (None, None))
    assert cli._resolve_fonts("Iosevka Nerd Font") == ("Iosevka Nerd Font", "Iosevka Nerd Font")


def test_config_lines_reports_which_file_is_in_effect(tmp_path):
    missing = tmp_path / "nope.toml"
    assert cli._config_lines(str(missing)) == [f"config: none at {missing} — built-in defaults"]

    real = tmp_path / "config.toml"
    real.write_text("theme = 'dark'\n")
    assert cli._config_lines(str(real)) == [f"config: {real}"]

    link = tmp_path / "linked.toml"
    link.symlink_to(real)
    lines = cli._config_lines(str(link))
    assert lines[0] == f"config: {link}"
    assert "managed declaratively" in lines[1] and str(real) in lines[1]


def test_font_line_names_where_the_family_came_from(monkeypatch):
    # Echo the queried family back so nothing looks like a fontconfig substitution.
    monkeypatch.setattr(cli, "_fc_match", lambda q: ("/fonts/X.ttf", q.split(":")[0]))
    args = argparse.Namespace(font_family=None)
    assert cli._font_line(args, {}) == (
        f"font: {cli.DEFAULT_FONT_FAMILY} (built-in default) -> /fonts/X.ttf",
        True,
    )
    assert cli._font_line(args, {"font_family": "Iosevka Nerd Font"}) == (
        "font: Iosevka Nerd Font (config) -> /fonts/X.ttf",
        True,
    )
    args = argparse.Namespace(font_family="Iosevka Nerd Font")
    assert cli._font_line(args, {"font_family": "ignored"}) == (
        "font: Iosevka Nerd Font (--font-family) -> /fonts/X.ttf",
        True,
    )


def test_font_line_flags_a_substitution_and_a_missing_fontconfig(monkeypatch):
    args = argparse.Namespace(font_family="Nope Grotesk")
    monkeypatch.setattr(cli, "_fc_match", lambda q: ("/fonts/DejaVuSans.ttf", "DejaVu Sans"))
    line, ok = cli._font_line(args, {})
    assert "NOT INSTALLED, fontconfig substituted DejaVu Sans" in line and not ok
    monkeypatch.setattr(cli, "_fc_match", lambda q: (None, None))
    line, ok = cli._font_line(args, {})
    assert "no fc-match on PATH" in line and ok


def test_detect_desktop_matches_case_insensitively():
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}) == "gnome"
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "KDE"}) == "kde"
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "XFCE"}) == "xfce"
    assert recipes.detect_desktop({"XDG_CURRENT_DESKTOP": "sway"}) is None
    assert recipes.detect_desktop({}) is None


def test_all_recipes_have_path_placeholder():
    assert all("{path}" in cmd for cmd in recipes.RECIPES.values())


def test_service_unit_execstart_and_timer(monkeypatch):
    monkeypatch.setattr(service, "greyline_bin", lambda: "/opt/bin/greyline")
    svc = service.service_unit()
    assert "ExecStart=/opt/bin/greyline" in svc
    assert "Type=oneshot" in svc
    tmr = service.timer_unit(interval="*:0/5:00")
    assert "OnCalendar=*:0/5:00" in tmr
    assert "AccuracySec=1s" in tmr
    assert "WantedBy=timers.target" in tmr


def test_service_unit_skips_itself_when_greyline_is_gone(monkeypatch):
    """The uninstall-survival guarantee: a package manager cannot remove these units,
    so an orphaned timer must skip rather than fail once a minute forever."""
    monkeypatch.setattr(service, "greyline_bin", lambda: "/opt/bin/greyline")
    assert "ConditionFileIsExecutable=/opt/bin/greyline" in service.service_unit()


def test_disable_removes_the_units_enable_wrote(monkeypatch, tmp_path):
    """`enable` writes two files; `disable` has to remove the same two."""
    calls = []
    monkeypatch.setattr(service, "UNIT_DIR", str(tmp_path))
    monkeypatch.setattr(service, "_systemctl", lambda *a: calls.append(a))
    for name in ("greyline.service", "greyline.timer"):
        (tmp_path / name).write_text("[Unit]\n")

    removed = service.disable()

    assert sorted(os.path.basename(p) for p in removed) == ["greyline.service", "greyline.timer"]
    assert not list(tmp_path.glob("greyline.*"))
    assert ("disable", "--now", "greyline.timer") in calls
    assert ("daemon-reload",) in calls


def test_disable_is_safe_when_the_units_are_already_gone(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "UNIT_DIR", str(tmp_path))
    monkeypatch.setattr(service, "_systemctl", lambda *a: None)
    assert service.disable() == []


def test_purge_removes_config_and_cache(monkeypatch, tmp_path):
    cfg_dir, cache_dir = tmp_path / "config" / "greyline", tmp_path / "cache" / "greyline"
    for d in (cfg_dir, cache_dir):
        d.mkdir(parents=True)
        (d / "file").write_text("x")
    monkeypatch.setattr(service, "user_state_paths", lambda: [str(cfg_dir), str(cache_dir)])

    removed, skipped = service.purge()

    assert sorted(removed) == sorted([str(cfg_dir), str(cache_dir)])
    assert skipped == []
    assert not cfg_dir.exists() and not cache_dir.exists()


def test_purge_names_the_config_and_cache_directories():
    """Guards the paths themselves — `--purge` deletes what this returns."""
    paths = service.user_state_paths()
    assert any(p.endswith("greyline") for p in paths)
    assert len(paths) == 2


def test_install_and_enable_dry_run_lists_actions_without_writing(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "UNIT_DIR", str(tmp_path / "systemd"))
    actions = service.install_and_enable(interval="*:*:00", dry_run=True)
    assert any("daemon-reload" in a for a in actions)
    assert any("enable --now greyline.timer" in a for a in actions)
    assert not (tmp_path / "systemd").exists()


def test_output_path_stable_for_native_backends(tmp_path):
    assert cli._output_path(str(tmp_path), "eDP-1", rotate=False) == str(tmp_path / "eDP-1.png")


def test_output_path_pingpongs_between_two_buffers(tmp_path):
    import os

    rt = str(tmp_path)
    pa, pb = tmp_path / "screen-a.png", tmp_path / "screen-b.png"

    assert cli._output_path(rt, "screen", rotate=True) == str(pa)
    pa.write_bytes(b"1")
    os.utime(pa, (1000, 1000))

    assert cli._output_path(rt, "screen", rotate=True) == str(pb)
    pb.write_bytes(b"2")
    os.utime(pb, (2000, 2000))

    assert cli._output_path(rt, "screen", rotate=True) == str(pa)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["screen-a.png", "screen-b.png"]


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


def test_render_flags_work_before_and_after_subcommand():
    parse = cli.build_parser().parse_args
    for argv in (
        ["watch", "--backend", "command", "--command", "cp {path} x"],
        ["--backend", "command", "--command", "cp {path} x", "watch"],
    ):
        a = parse(argv)
        assert a.backend == "command" and a.command == "cp {path} x"
    assert parse(["watch"]).backend is None


def test_watch_loops_run_apply_until_interrupted(monkeypatch):
    calls = {"n": 0}

    def fake_apply(args):
        calls["n"] += 1
        return 0

    def fake_sleep(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_apply", fake_apply)
    monkeypatch.setattr("time.sleep", fake_sleep)
    rc = cli.main(["watch", "--interval", "60"])
    assert rc == 0 and calls["n"] == 1


def test_help_command_prints_that_commands_help(capsys):
    assert cli.main(["help", "city", "add"]) == 0
    out = capsys.readouterr().out
    assert "greyline city add" in out
    assert "IANA timezone" in out


def test_help_bare_prints_the_command_list(capsys):
    assert cli.main(["help"]) == 0
    out = capsys.readouterr().out
    assert "greyline help topics" in out
    for name in ("init", "watch", "config", "city", "doctor", "help"):
        assert name in out


def test_help_topics_render_from_live_data(capsys):
    assert cli.main(["help", "themes"]) == 0
    assert "modus" in capsys.readouterr().out
    assert cli.main(["help", "desktops"]) == 0
    assert recipes.RECIPES["kde"] in capsys.readouterr().out
    assert cli.main(["help", "keys"]) == 0
    keys = capsys.readouterr().out
    assert "twilight" in keys and "darkness" in keys
    assert "[[city]]\nname =" not in keys


def test_help_topic_list_matches_the_topics_epilog_advertises():
    from greyline import helptext

    for name in helptext.topic_names():
        assert name in helptext.HELP_EPILOG
        assert helptext.render_topic(name)


def test_help_prefers_commands_over_topics(capsys):
    assert cli.main(["help", "config"]) == 0
    assert "greyline config set" in capsys.readouterr().out


def test_help_unknown_topic_exits_nonzero_with_a_pointer(capsys):
    assert cli.main(["help", "nonsense"]) == 1
    assert "greyline help topics" in capsys.readouterr().err


def test_bare_config_and_city_print_help_instead_of_an_argparse_error(capsys):
    for argv in (["config"], ["city"]):
        assert cli.main(argv) == 1
        assert "Examples:" in capsys.readouterr().out


def test_theme_lines_flag_a_fallback_and_stay_quiet_otherwise(tmp_path, monkeypatch):
    lines, ok = cli._theme_lines({"theme": "gruvbox-dark-hard"})
    assert lines == ["theme: gruvbox-dark-hard (built-in)"] and ok

    lines, ok = cli._theme_lines({"theme": "catppuccin"})
    assert lines == ["theme: catppuccin -> catppuccin-mocha (built-in)"] and ok

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    d = tmp_path / "greyline" / "themes"
    d.mkdir(parents=True)
    (d / "broken.toml").write_text("this is [not toml")
    lines, ok = cli._theme_lines({"theme": "broken"})
    assert lines[0] == "theme: broken -> modus (built-in)"
    assert "not valid TOML" in lines[1] and not ok


def test_purge_leaves_a_declaratively_managed_config_alone(monkeypatch, tmp_path):
    """Under home-manager the config directory is a symlink into the Nix store.
    rmtree refuses to follow it, which used to surface as a traceback out of
    `greyline disable --purge`; and deleting it would be undone on the next rebuild
    anyway. Report it and move on."""
    store = tmp_path / "store"
    store.mkdir()
    (store / "config.toml").write_text("theme = 'modus'\n")
    link = tmp_path / "greyline"
    link.symlink_to(store)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setattr(service, "user_state_paths", lambda: [str(link), str(cache_dir)])

    removed, skipped = service.purge()

    assert removed == [str(cache_dir)]
    assert [p for p, _ in skipped] == [str(link)]
    assert "managed declaratively" in skipped[0][1]
    assert store.is_dir() and (store / "config.toml").exists()


def test_purge_reports_a_directory_it_cannot_remove(monkeypatch, tmp_path):
    """Any other OSError is reported too, so --purge never ends in a traceback."""
    target = tmp_path / "greyline"
    target.mkdir()
    monkeypatch.setattr(service, "user_state_paths", lambda: [str(target)])

    def boom(_path):
        raise PermissionError(13, "Permission denied")

    import shutil

    monkeypatch.setattr(shutil, "rmtree", boom)

    removed, skipped = service.purge()
    assert removed == []
    assert skipped and "Permission denied" in skipped[0][1]
