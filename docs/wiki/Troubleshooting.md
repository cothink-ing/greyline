# Troubleshooting

Start here:

```sh
greyline doctor
```

It prints the session it detected (`XDG_CURRENT_DESKTOP`, `XDG_SESSION_TYPE`), the
backend it resolved and the outputs that backend reports, whether the font you asked for
is the font you got, and whether `systemd --user` is available. Most problems are visible
in those five lines.

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
that happens. Install the family, or set `font_family` to one you have, or point it at a
font file directly.

## Nothing here matches

Open an issue with the output of `greyline doctor` and `greyline --list-outputs`. If it
concerns GNOME, KDE, XFCE or another desktop that manages its own wallpaper, use the
[desktop-compatibility template](https://github.com/cothink-ing/greyline/issues/new/choose):
the maintainer runs sway and cannot reproduce those directly, so those reports are how
the recipes get fixed.
