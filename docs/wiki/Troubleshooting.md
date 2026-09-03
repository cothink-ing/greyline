# Troubleshooting

Start here:

```sh
greyline doctor
```

The output is self-contained — version and platform, the config file actually in effect,
the detected session, the resolved backend and its outputs, the font you asked for and
the font you got, and whether `systemd --user` is available:

```
greyline 0.7.3 · python 3.13.2 · Linux 6.12.4
config: /home/you/.config/greyline/config.toml
session: XDG_CURRENT_DESKTOP='sway' XDG_SESSION_TYPE='wayland'
backend: sway (requested: auto)
  eDP-1: 1920x1200 scale=1.0
font: Iosevka Nerd Font (config) -> /usr/share/fonts/.../IosevkaNerdFont-Regular.ttf
systemd --user: available
```

Most problems are visible in those lines, and it is the right thing to paste into a bug
or [compatibility report](https://github.com/cothink-ing/greyline/issues/10).

## I changed a setting and nothing happened

Two things can swallow an edit. `greyline doctor` distinguishes them.

**You edited a file greyline does not read.** The `config:` line names the file actually
loaded. If it says `none at …`, greyline is running on built-in defaults and your edit
went somewhere else.

**Something else owns that file.** Under the home-manager module, declaring `settings`
makes the config a read-only symlink into the Nix store; `doctor` marks it
`managed declaratively`. Edits belong in your Nix config, not in the file, and
`greyline config set` cannot write to it. See
[Installation](Installation#settings-and-greyline-config-set-are-mutually-exclusive).

**greyline read it but could not use it.** `doctor` has a line per setting that can
quietly fall back:

- `theme:` names the theme actually in use. `theme: mytheme -> modus` means yours could
  not be loaded, and the line under it says why — a file that is not valid TOML, or a
  name that does not exist. Colour values it had to skip are listed too, so a stray
  `ocean = "nope"` is visible rather than merely ignored.
- `font:` names where the family came from — `config`, `--font-family`, or
  `built-in default` — and whether fontconfig substituted something else. `fc-match`
  never fails; an uninstalled family silently becomes another one.

**Exit code.** `greyline doctor` exits non-zero when something you asked for is not
happening: a config value it cannot use, a theme that fell back, a font you named that
is not installed. A key greyline does not recognise is only a warning — there is no
such setting to honour, so it is ignored and your wallpaper keeps working. That makes
`greyline doctor` usable in a script.

## The wallpaper never changes

Check the three links in the chain, in order.

**Is greyline running at all?** `systemctl --user status greyline.timer` should show the
timer active, and `journalctl --user -u greyline.service -n 20` the last few runs. If
there is no systemd here, greyline only runs while `greyline watch` is running: see
[scheduling without systemd](Installation#scheduling-without-systemd).

**Is it rendering?** `greyline --out /tmp/wt.png --res 2560x1440` writes a PNG and
applies nothing. If that image looks right, rendering is fine and the problem is in the
backend.

**Is the backend the right one?** `greyline doctor` names it. On GNOME, KDE or XFCE the
answer is almost always that the `x11` backend was picked: it paints the root window, and
then the desktop environment paints straight over it. Use the `command` backend instead,
which is what `greyline init` configures on those desktops. See
[Desktop environments](Desktop-environments).

## The wallpaper changes once, then reverts

The desktop is re-asserting its own wallpaper. On GNOME this is usually the same-URI
cache: setting `picture-uri` to a path it already holds is a no-op, which is why the
bundled recipe sets it to the empty string first. If your desktop does something similar,
the fix belongs in the command, not in a background process. Please
[report the recipe that worked](https://github.com/cothink-ing/greyline/issues/new/choose).

## The clock is wrong, or a city sits in the wrong place

Times come from the OS IANA database via `zoneinfo`, so DST is handled for you, but only
if the timezone name is right. `greyline city list` shows what each city is set to; the
name must be a real IANA zone such as `Europe/Paris`, not an abbreviation such as `CET`.

Coordinates are decimal degrees, latitude +N/-S and longitude +E/-W. A city in the wrong
hemisphere is a sign flip.

## Labels overlap, or one runs off the edge

Label placement picks a side automatically to avoid collisions and edges. To force one,
give that city a `label_side` of `left`, `right`, `above` or `below`; it still falls back
if the forced side would not fit. `font_scale` below 1.0 buys room on a crowded map.

## The font is not the one I asked for

`fc-match` always returns something, so a family that is not installed silently resolves
to a substitute. `greyline doctor` says `NOT INSTALLED, fontconfig substituted …` when
that happens, and greyline warns on stderr on every render — check
`journalctl --user -u greyline.service` if you are running under the timer. Install the
family, or set `font_family` to one you have, or point it at a font file directly.

A family+weight name such as `BlexMono Nerd Font Medium` is fine: it is matched against
the family fontconfig reports (`BlexMono Nerd Font`), so it does not false-alarm.

## Nothing here matches

Open an issue with the output of `greyline doctor` and `greyline --list-outputs`. If it
concerns GNOME, KDE, XFCE or another desktop that manages its own wallpaper, use the
[desktop-compatibility template](https://github.com/cothink-ing/greyline/issues/new/choose):
the maintainer runs sway and cannot reproduce those directly, so those reports are how
the recipes get fixed.
