# Installation

greyline is distro-agnostic. Install it with pipx or uv on any distribution, or with the
Nix flake on NixOS.

**Requirements:** Linux on Wayland or X11, x86_64 or aarch64. Python 3.11 or newer when
installing from PyPI (the Nix package bundles its own). Pillow and tomlkit are pulled in
automatically. Font resolution uses fontconfig (`fc-match`). You also need a wallpaper
tool for your desktop, and something to run greyline every minute: a systemd user timer,
or any session autostart running `greyline watch`.

## pipx or uv

```sh
pipx install greyline    # or: uv tool install greyline
greyline init
```

`init` writes a starter `~/.config/greyline/config.toml`, detects your compositor and
picks a [backend](Backends), and where systemd is present installs and enables a user
timer that fires every minute. On GNOME, KDE and XFCE it fills in the right wallpaper
command for you. No git clone, no hand-copied units.

It is safe to re-run: an existing config is kept and only the backend keys are updated.
`greyline init --dry-run` shows what it would do and changes nothing.

## Nix, with home-manager

```nix
# flake.nix
inputs.greyline.url = "github:cothink-ing/greyline";

# home-manager
imports = [ inputs.greyline.homeManagerModules.default ];

services.greyline = {
  enable = true;
  backend = "sway";              # auto | sway | swww | hyprpaper | x11 | command
  settings = {
    theme = "modus";
    font_family = "Aporetic Sans";  # resolved via fontconfig
    format = "24h";
    twilight = { bands = true; darkness = "subtle"; };
    home = { tz = "auto"; column_highlight = true; };  # "auto" = system tz
    city = [
      { name = "Kuala Lumpur"; lat = 3.14;  lon = 101.69; tz = "Asia/Kuala_Lumpur"; }
      { name = "London";       lat = 51.51; lon = -0.13;  tz = "Europe/London"; }
      { name = "New York";     lat = 40.71; lon = -74.01; tz = "America/New_York"; }
      { name = "Tokyo";        lat = 35.68; lon = 139.69; tz = "Asia/Tokyo"; }
    ];
  };
};
```

`settings` becomes the generated `config.toml`, so every key on the
[Configuration](Configuration) page is available there.

One key is not set here: `backend` is a module option, because the unit is wired from it
(the swww daemon, `extraPackages`, unit ordering). Setting `settings.backend` is an
evaluation error rather than a silent no-op.

### Setting the font

Put it in `settings`, like every other config key:

```nix
services.greyline.settings.font_family = "Iosevka Nerd Font";
```

It takes a fontconfig family name or a path to a font file. Make sure the font is
actually installed (`fonts.packages` on NixOS, `home.packages` under home-manager) —
`fc-match` never fails, it substitutes, so an uninstalled family silently becomes
something else. `greyline doctor` prints the family it asked for, the file it got, and
flags the substitution when they disagree.

There was a separate `services.greyline.fontFamily` option before 0.7.3. It was renamed
in 0.7.3 and removed in 0.8.4; if you still have it, home-manager will say so and point
you at `settings.font_family`. Nothing else to do — the value is the same.

### `settings` and `greyline config set` are mutually exclusive

Declaring anything in `settings` makes home-manager own `~/.config/greyline/config.toml`
as a read-only symlink into the Nix store. That is the point of declaring it — but it
means `greyline init` and `greyline config set` can no longer edit that file. Pick one:

- **Declarative** — put every key in `settings`, including `font_family`, and change the
  wallpaper by rebuilding.
- **Imperative** — leave `settings = { }` and manage the file with `greyline init` and
  `greyline config set`. The module still installs the package, the timer and the unit.

`greyline doctor` tells you which of the two you are in: it prints the config file it
loaded and flags it when the file is a managed symlink.

## Run it without installing

```sh
nix run github:cothink-ing/greyline -- --out wt.png --res 2560x1440
uvx greyline --out wt.png --res 2560x1440
```

Both write a PNG and touch no wallpaper.

## Managing the timer

Where systemd is present, `greyline init` installs a user timer and enables it. After
that:

```sh
greyline status     # is the timer running, and when did it last fire?
greyline disable    # stop updating, keep the last wallpaper
greyline enable     # start again
```

`greyline init --interval '*:0/5:00'` sets a different period at setup time; the value is
a systemd `OnCalendar` expression.

## Uninstalling

Disable before you uninstall:

```sh
greyline disable            # stops the timer and removes the units init wrote
greyline disable --purge    # also deletes ~/.config/greyline and the render cache
pipx uninstall greyline
```

The order matters only because `greyline disable` needs greyline to still be installed.
Your package manager cannot do this step for you: the timer, the unit files and your
config were written into your home directory by `greyline init` *after* installation,
and pipx has no post-uninstall hook. If you uninstall without disabling, nothing breaks
— the service unit carries `ConditionFileIsExecutable`, so systemd skips the orphaned
timer instead of failing it every minute — but the files stay until you remove them.

Under home-manager, drop `services.greyline` from your configuration and rebuild
instead; it owns the units and the config file and will remove both.

## Scheduling without systemd

Any init system works. Skip the timer and put greyline in your session autostart:

```sh
greyline watch    # renders and applies every minute, in the foreground
```

`--interval SEC` changes the period. Runit, OpenRC, s6, a bare WM and the BSDs are all
served by this; nothing about greyline needs systemd except the convenience of `greyline
enable`.

## Windows and macOS

> [!WARNING]
> Beta, and untested on real hardware. greyline is developed on Linux. The Windows and
> macOS backends are written against each platform's documented wallpaper API but have
> never been run on an actual Windows or Mac desktop, only in CI, which renders the image
> and exercises the code but cannot see whether the wallpaper changed. Please
> [open an issue](https://github.com/cothink-ing/greyline/issues) to say whether it
> works. Success and failure are both useful.

Two known limits: a single combined desktop only, with no per-monitor wallpapers, and no
automatic scheduling.

Install with `pipx install greyline` (Pillow ships wheels for both). greyline auto-detects
the `windows` and `macos` backends; `--backend windows` or `backend = "macos"` in the
config forces one.

```sh
greyline --list-outputs    # sanity-check detection
greyline                   # render and set the wallpaper once
greyline watch             # keep it updating; Ctrl-C to stop
```

There is no service installer on these platforms yet, so wrap `greyline watch` in the OS
scheduler:

- **Windows** — Task Scheduler, *Create Task*, trigger *At log on*, action *Start a
  program*: `greyline` with the argument `watch`. A shortcut to `greyline watch` in
  `shell:startup` also works.
- **macOS** — a launchd agent at `~/Library/LaunchAgents/ing.cothink.greyline.plist`
  whose `ProgramArguments` are the path to `greyline` and `watch`, with `RunAtLoad` set.
  Load it with `launchctl load ~/Library/LaunchAgents/ing.cothink.greyline.plist`.

## Fonts

`font_family` takes a fontconfig family name or a path to a font file, and `font_scale`
sizes the label text. `--font-family` overrides the config for one run.

`fc-match` never fails: ask for a family that isn't installed and it quietly answers with
a substitute. greyline therefore compares the family it asked for against the family it
got and warns on stderr when they differ, so a missing font looks like a warning rather
than a wallpaper that mysteriously renders in DejaVu Sans.

On Windows and macOS there is no fontconfig; Pillow resolves a system font (Segoe UI,
Helvetica) and falls back to a built-in one. Labels always render, but the typography
will not match Linux exactly.
