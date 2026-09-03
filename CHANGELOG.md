# Changelog

All notable changes to greyline are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.1] — 2026-09-03

### Added
- **The demo's ported maths are tested against the Python they came from.**
  `web/sun.js`, `web/geo.js` and `web/config.js` reimplement the NOAA declination
  series, the equation of time, the boundary-latitude solve and the projection by hand.
  The palettes had a generator and a drift test; the maths had nothing, so a fix landing
  in `sun.py` and not in `sun.js` was invisible. Both are now run on the same pinned
  inputs and compared to 1e-9.

### Changed
- **The demo redraws on the minute, not every second.** CONTRIBUTING has said all along
  that per-second redraws cost battery and buy nothing anyone can read; the demo was
  rebuilding the terminator and every clock sixty times more often than the display can
  change. Resizing is debounced too — each resize discards the cached base and spends
  ~110ms redrawing the map, and a phone fires one continuously as the URL bar slides
  away.
- **The demo is usable without sight.** The canvas is the entire page and carried no
  label at all, so a screen reader got a heading, a paragraph and nothing else. It is
  now `role="img"` with a label naming every city's local time and the highlighted
  timezone, refreshed each minute. The toggles report their state with `aria-pressed`
  instead of a CSS class, the control groups are named, and focus has a visible ring.
- **Controls no longer zoom the page on iOS.** Safari zooms whenever a control smaller
  than 16px takes focus, which the 12.5px theme picker did every time it was tapped.
  Controls grow to 16px and gain bigger hit areas on narrow screens.
- **The bundled map data is a third smaller.** The Natural Earth files carried fifteen
  properties per timezone feature, of which greyline reads one, at seven decimal places
  of coordinate precision — about a hundred times finer than a 4K pixel. Stripping the
  unused properties and rounding to 3 decimal places takes the wheel from 4.57 MB to
  2.91 MB and the demo's first paint from 1.57 MB to 0.85 MB gzipped, which was
  dominated by that one file. `tools/prep_geodata.py` documents and reproduces the
  transform, a test checks the shipped files still match it, and NOTICE records that
  the files are not byte-for-byte upstream.

## [0.8.0] — 2026-09-03

### Added
- **`greyline config set` refuses a key greyline does not read.** A mistyped key used
  to be written out and then silently ignored, which is the slowest possible way to
  learn you typed `them` instead of `theme` — the wallpaper simply never changed and
  nothing anywhere said why. Keys, types and ranges now live in one schema
  (`worldtime/schema.py`), so `greyline config set bar_height tall` and
  `greyline config set label_bg_alpha 900` are refused at the moment you make the
  mistake, with a suggestion when the key is a near miss.
- **The config file is checked when it is read, too.** `config set` cannot protect a
  file you edit by hand or one home-manager writes for you, and a value the renderer
  cannot use — `font_scale = "huge"` — used to reach it and raise a `ValueError`
  traceback into the journal once a minute, forever. That is now a one-line error and a
  non-zero exit. A key greyline does *not* read stays non-fatal: `doctor` reports it and
  the render carries on, because a leftover setting from another version must not take a
  working wallpaper down.
- **`greyline doctor` exercises the config instead of trusting it.** It loaded the file
  but never built the render options from it, so the one failure that stops the
  wallpaper dead was the one failure it reported as all-clear. It now says what is
  wrong, carries on against the packaged defaults so the backend and font checks still
  run, and exits non-zero.
- **`greyline disable --purge`** removes `~/.config/greyline` and the cache as well.

### Changed
- **The map is rendered once and reused, not rebuilt every minute.** Ocean, land,
  borders, the timezone grid and the filled zone columns do not change between ticks —
  only the terminator and the clocks do — but every tick redrew all of it at 2x
  supersample. A 4K tick cost 3.2s of CPU and half a gigabyte of peak memory, once a
  minute, on a project whose stated priorities put battery life second only to
  compatibility. The base is now cached under `$XDG_CACHE_HOME/greyline`, keyed by size,
  theme, font and home offset: **1.25s → 0.33s at 1080p and 3.22s → 1.10s at 4K**, with
  byte-identical output. Bounded at six files and evicted oldest-first, in the same
  spirit as the two-buffer wallpaper ping-pong. A missing, corrupt or unwritable cache
  is a slow render, never a broken one.
- **`greyline disable` removes the unit files it wrote.** `enable` writes
  `greyline.service` and `greyline.timer`; `disable` only ever removed the enable
  symlink and left the units to be rediscovered. It now undoes what it did.
- **An uninstalled greyline no longer leaves a failing timer behind.** No package
  manager can clean this up — pipx has no post-uninstall hook, and the units were
  written into your home directory after install — so `pipx uninstall greyline` used to
  leave an enabled timer firing at a deleted binary every minute. The service unit
  carries `ConditionFileIsExecutable` now, so systemd skips it silently instead of
  failing it. `greyline disable` before uninstalling is still the tidy path, and
  `greyline help disable` spells it out.
- **Catppuccin Latte's clocks are legible.** Its labels were drawn in Rosewater on a
  light plate — 2.02:1, well under the 4.5:1 that counts as readable — because the
  base16 mapping takes clock text from `base06`, which is a light accent in that one
  scheme out of the thirty-five bundled. The generator now falls back to `base05` when
  `base06` cannot be read against the plate, which is the colour the city dots already
  use, and gives 6.10:1. Every theme is checked for this now, so the next scheme with an
  unusual palette cannot ship unreadable.
- **`render()` takes an `Options` value rather than twenty-six parameters.** They were
  fed mechanically from one function and are now a frozen dataclass with typed fields
  and real defaults, so `Options()` and a config that sets nothing provably agree. This
  is a breaking change to an undocumented internal API, taken deliberately before 1.0.
- **`greyline doctor` output is self-contained**, so it can be pasted into a bug or
  compatibility report as-is. It now leads with the version, Python and platform, and
  names the config file actually in effect — flagging it when the file is a read-only
  symlink managed by home-manager, which is the state that made a set-but-ignored key
  look like a greyline bug ([#16]). The font line says where the family came from
  (`config`, `--font-family` or `built-in default`), and the backend line shows what was
  requested when it differs from what was resolved.

### Documentation
- **Four config keys nobody could discover.** `desaturate`, `label_background`,
  `label_bg_alpha` and `logo_color` were read by the renderer but appeared nowhere in
  `default-config.toml`, so `greyline help keys` never mentioned them. The schema made
  the gap countable and a test now keeps it closed.
- **Installation gains an "Uninstalling" section**, spelling out why the disable step
  exists and what home-manager users do instead. The README says it in one line.
- Troubleshooting gains an **"I changed a setting and nothing happened"** section, and
  Installation spells out that declaring `settings` in the home-manager module makes it
  own `~/.config/greyline/config.toml`, so `greyline config set` cannot edit it — pick
  declarative or imperative, not both. Installation now also records that
  `services.greyline.fontFamily` is deprecated rather than merely an alias.

[#16]: https://github.com/cothink-ing/greyline/issues/16

## [0.7.3] — 2026-09-03

### Changed
- **The README is 99 lines instead of 404, and the reference material moved to the
  [wiki](https://github.com/cothink-ing/greyline/wiki).** The config-key table, the
  theme list and the GNOME/KDE/XFCE recipes were maintained by hand in the README *and*
  generated from the code by `helptext.py`, which is the exact duplication that module
  exists to prevent; the README's copies were already the lossier of the two. The wiki's
  Configuration, Themes, Backends and Desktop-environments pages are now generated from
  `greyline help <topic>` by `tools/gen_wiki.py`, checked into `docs/wiki/`, gated by
  `tests/test_wiki_docs.py`, and pushed to the wiki by a workflow. Installation,
  Architecture and Troubleshooting are hand-written in the same directory. Nothing was
  dropped; the README keeps the pitch, the install, and the pointers.
- **`worldtime/default-config.toml` points at `greyline help desktops`** for the desktop
  recipes rather than at a README section that no longer exists.
- **PyPI gets working links.** The README's images and file links are absolute, so they
  resolve off GitHub, and `[project.urls]` gained `Documentation`, `Changelog` and `Demo`.

### Added
- **`CONTRIBUTING.md`.** Absorbs the README's contributing section and its principles,
  where someone about to open a pull request will actually read them, and documents which
  of the three documentation surfaces is the source of truth for what.

### Fixed
- **The live-demo link worked nowhere.** The GitHub organisation was renamed from
  `cothinking-dev` to `cothink-ing`. Repository URLs survived on GitHub's redirect, so
  nobody noticed, but Pages does not redirect across an owner rename and
  `cothinking-dev.github.io/greyline/` had been answering 404. Every URL in the repo now
  names the current organisation, the demo page's link back to GitHub included.
- **`font_family` in `config.toml` was ignored under the home-manager module.** The
  generated unit appended `--font-family "${cfg.fontFamily}"` to `ExecStart`, and a CLI
  flag outranks the config file — so the module option's default won on every tick and
  `settings.font_family` (or a hand-edited `config.toml`) had no effect. The default,
  `Aporetic Sans`, is usually not installed, and `fc-match` answers with a substitute
  instead of failing, so the only symptom was a wallpaper stuck on DejaVu Sans.

  The unit now passes only `--backend` (which the module owns, since it wires the
  service from it) and `--command`; everything else reaches greyline through
  `config.toml`. `settings.backend` is now an assertion failure rather than a silent
  no-op.
- **A font that isn't installed now says so**, on stderr at render time and in
  `greyline doctor`, which also reports the resolved font file.
- **The sway backend no longer crashes on platforms without uids or procfs.**
  `_runtime_base()` fell back to `/run/user/{os.getuid()}`, which does not exist on
  Windows; auto-detection swallowed the AttributeError, but an explicit
  `--backend sway` raised it instead of reporting the backend as unavailable. The pid
  check that stops greyline retiring a reused pid read `/proc/<pid>/cmdline` with a
  liveness-check fallback, and its test asserted the procfs behaviour while running on
  runners that have no procfs — so it was testing the host, not the code. Both branches
  are now driven explicitly and covered on every platform. `cross-platform` CI is green
  again.

### Deprecated
- `services.greyline.fontFamily` is renamed to `services.greyline.settings.font_family`.
  Existing configs keep working and emit the standard home-manager rename warning.

## [0.7.2] — 2026-09-03

### Fixed
- **No more black flash when the sway wallpaper updates.** `swaymsg output <name> bg`
  is not a live update: sway destroys the running swaybg client and forks a replacement,
  so for as long as the new one takes to start and draw its first frame there is no
  background layer surface and sway paints its default black. Invisible under a
  fullscreen window, very visible in gaps, borders and around floating windows — once a
  minute. The sway backend now manages swaybg itself: it starts the new instance, lets it
  map (layer surfaces stack in creation order, so it covers the old wallpaper), and only
  then stops the previous one. No frame is ever without a background. On multi-monitor
  setups this also fixes every output flashing on each per-output update, since sway's
  respawn tore down *all* backgrounds, not just the one being changed.

  Each swaybg runs in a transient systemd user unit (`greyline-bg-<output>-a`/`-b`) so it
  survives the oneshot `greyline.service` exiting, or as a detached child with a pidfile
  where there is no systemd user manager. `swaybg` is therefore a new runtime dependency
  of the `sway` backend; without it greyline falls back to the old `swaymsg output bg`
  path and `greyline doctor` says so. The handover delay defaults to 0.5s and is tunable
  with `GREYLINE_SWAYBG_SETTLE`.

### Changed
- The **swww** backend now crossfades (`--transition-type fade`, 0.3s) instead of cutting
  hard. swww is buffered, so the transition costs nothing and reads better at a
  once-a-minute cadence. `GREYLINE_SWWW_TRANSITION` / `GREYLINE_SWWW_DURATION` override
  it (`none` restores the previous instant swap).
- `greyline doctor` prints backend notes when a backend has environment caveats to
  report (new optional `notes()` hook in the backend contract).
- Nix: the home-manager module's default `extraPackages` for the sway backend is now
  `[ pkgs.sway pkgs.swaybg ]`.

## [0.7.1] — 2026-08-18

### Added
- **Static analysis in the toolchain and CI.** [ruff](https://docs.astral.sh/ruff/)
  (lint + format, line length 100) and mypy (`check_untyped_defs` — bodies are checked
  without requiring annotations everywhere), both configured in `pyproject.toml`. New
  `nix flake check` derivations (`checks.lint`, `checks.types`) enforce them in CI; the
  dev shell now carries ruff/mypy/pytest, and a `dev` extra
  (`pip install -e ".[dev]"`) covers non-nix setups.

### Changed
- The whole codebase is `ruff format`-ed and lint-clean. Mostly mechanical (import
  sorting, `datetime.UTC`, f-strings over `%`-formatting), plus a few real cleanups:
  `Image.LANCZOS` → `Image.Resampling.LANCZOS` (deprecated since Pillow 10), and CLI
  validation errors now `raise ... from None` so users see the clean message instead of
  a chained traceback.

## [0.7.0] — 2026-08-18

### Added
- **35 built-in themes, ported from base16.** The palettes are now generated from the
  [tinted-theming base16 schemes](https://github.com/tinted-theming/schemes) (MIT), so the
  wallpaper matches the scheme your editor and terminal already use: every **gruvbox** and
  **everforest** variant (dark/light × hard/medium/soft), **rose-pine** / -moon / -dawn,
  **tokyo-night** dark/storm/moon/light, all four **catppuccin** flavours, plus `nord`,
  `dracula`, `solarized-{dark,light}`, `onedark`, `one-light`, `kanagawa`, `monokai`,
  `github-dark` and `github`. greyline's own `modus` and `blue` are unchanged.
- **Light themes are first-class.** 12 of the new palettes are light, and the parts that
  assumed a dark map now follow the theme: the night overlay uses a mid-tone at a much
  higher alpha (a light map multiplied toward black shows no terminator), the grid and
  column tints flip to black-on-light, and label plates take a new optional `label_bg`
  theme key instead of a hardcoded black.
- **`tools/base16_to_theme.py`** converts any of the ~340 upstream schemes into a greyline
  theme, so the bundled set is a starting point rather than a ceiling. It documents the
  whole base16 → greyline mapping, picks the date-line red / GMT green / accent by hue
  rather than by base16's nominal slot numbering (schemes disagree — tokyo-night's base08
  is lavender), and regenerates the bundled palettes with `--curated`.
- **`tools/sync_web_themes.py`** generates `web/themes.js` from the TOMLs, and a test fails
  if it is stale. The demo's palettes were hand-ported before, and drifted.
- **`greyline help`.** `greyline help <command>` prints any command's help, nested ones
  included (`greyline help city add`), and `greyline help <topic>` prints a reference
  page: `keys` (every config key with its allowed values and default), `themes`,
  `backends`, `desktops` (the GNOME/KDE/XFCE recipes). The pages are generated from the
  same data the renderer uses — themes from `worldtime/themes/*.toml`, recipes from
  `recipes.RECIPES`, keys from the packaged `default-config.toml` — so they can't drift.
  `greyline help topics` lists them.
- Every command now carries a longer description and worked examples in `--help`, and
  each positional argument (`name`/`lat`/`lon`/`tz`, config keys) documents itself.

### Changed
- Theme files use their upstream base16 slugs, so variants are nameable. The pre-0.7 names
  are **permanent aliases**: `gruvbox` → `gruvbox-dark-hard`, `catppuccin` →
  `catppuccin-mocha`, `rosepine` → `rose-pine`, `tokyonight` → `tokyo-night-dark`
  (`dark` → `modus` as before). Existing configs keep working untouched.
- A user theme file named after an alias now inherits the theme it aliases rather than
  falling back to `modus` — a partial `~/.config/greyline/themes/gruvbox.toml` means
  "gruvbox, but…".
- The ported palettes are re-derived rather than copied from their 0.6.0 hand-tuned
  versions, so `rosepine`/`tokyonight`/`catppuccin`/`gruvbox` shift slightly. The most
  visible change is landmass contrast: schemes whose `base01` sits within a shade of
  `base00` (rose-pine, everforest, gruvbox-medium) now get a distinctly readable coastline.
- The demo's theme buttons became a picker, since there are now three dozen.
- `greyline config` and `greyline city` with no subcommand print their own help instead
  of argparse's bare "the following arguments are required" error.

## [0.6.0] — 2026-08-14

### Added
- **Themes are now data, not code.** The palettes moved from a Python dict into TOML files
  (`worldtime/themes/*.toml`), and users can add their own: drop a file in
  `~/.config/greyline/themes/` and select it by filename with `theme = "mytheme"`. A user
  file with a built-in's name overrides that theme per key; missing keys of a new theme
  fall back to `modus`. Colours are `"#rrggbb"` or `"#rrggbbaa"` (trailing alpha), and a
  broken or partial theme file never crashes the minutely render — invalid values fall
  back per key, like `home.color` always has.
- **Four new built-in themes.** `catppuccin` (Mocha), `gruvbox` (dark, hard), `rosepine`
  and `tokyonight`, each derived from the corresponding
  [tinted-theming base16 scheme](https://github.com/tinted-theming/schemes), joining
  `modus` and `blue`. The web demo mirrors all six.
- **`[colors]` override table.** Tweak single colours of the selected theme straight from
  config.toml (e.g. `home = "#d3869b"`, `night_alpha = 20`) without writing a theme file.
  Precedence: theme file < `[colors]` < `home.color`.

### Changed
- **`dark` is now `modus`** (after Modus Vivendi, the palette it always was). The old name
  remains a permanent alias, so existing configs keep working unchanged; a user theme file
  literally named `dark.toml` shadows the alias.

## [0.5.5] — 2026-07-27

### Fixed
- **Home timezone-column highlight now follows the geographic zone, not the DST-shifted one.**
  On the vector map the home column was filled from the home city's *current* UTC offset, so
  in any DST-observing region it jumped one column east/west for half the year (London
  highlighted UTC+1 during BST, New York UTC−4 during EDT, Sydney UTC+11 during AEDT). The map's
  zone polygons are keyed by *standard* offset, so the highlight now subtracts the DST component
  (`utcoffset() − dst()`) to match — hemisphere-correct, no lookup table. The city clocks and the
  raster-style band were already correct and are unchanged. (#14)

## [0.5.4] — 2026-07-24

### Fixed
- **Home-manager `command` backend no longer breaks with a space-containing `fontFamily`.**
  The `ExecStart` line fused `--font-family "Aporetic Sans"` and `--command …` with no space,
  because Nix strips the leading whitespace from an indented (`''…''`) string fragment. greyline
  then rejected the concatenated argument (`status=2/INVALIDARGUMENT`) and the wallpaper failed
  to render every tick. The `--command` fragment is now a normal double-quoted string, so the
  separator survives. (#13)

## [0.5.3] — 2026-07-23

### Fixed
- **KDE Plasma wallpaper now refreshes on every tick (`command` backend).** Plasma caches
  the wallpaper by path, so greyline's fixed filename never repainted. The command backend
  now ping-pongs two buffers (`screen-a.png`/`screen-b.png`) so each update hands Plasma a
  new path — capped at two files, no cache or junk-file growth. Native backends keep the
  single stable filename. (#11)
- **systemd timer fires within ~1s of the minute.** Added `AccuracySec=1s` so the clock
  updates on time instead of drifting up to ~50s from systemd's default timer coalescing.
  A single per-minute timer at 1s accuracy has negligible power cost. (#12)

### Added
- **Principles (north star) section in the README** — universal compatibility, performance
  & battery life, and staying lightweight, as a checklist for future changes.

## [0.5.2] — 2026-07-22

### Added
- **Configurable label font via `font_family`.** Set the label font in `config.toml` (a
  fontconfig family name or a direct font-file path) instead of only via `--font-family`;
  the CLI flag still overrides the config for a single run. Unset falls back to the bundled
  Aporetic Sans, then system fonts.
- **`logo_max_height` config key.** Caps the corner logo's height to a fraction of the
  screen height (`0` = no cap), so tall/portrait custom logos no longer blow up at the
  fixed logo width. Aspect ratio is preserved.
- **Documented `font_scale`.** The existing text-size multiplier is now surfaced in the
  default config template (e.g. `font_scale = 1.25` for 25% larger labels).

## [0.5.1] — 2026-07-22

### Fixed
- **Windows: timezone lookups no longer fail with `ZoneInfoNotFoundError`.** Windows has no
  system IANA tz database, so stdlib `zoneinfo` couldn't resolve any timezone; greyline now
  depends on the `tzdata` PyPI package on Windows (Unix is unaffected — it ships tzdata
  system-wide). Caught by the new `windows-latest` CI matrix.
- **Windows: reading the GeoJSON map data and the config no longer crashes with
  `UnicodeDecodeError`.** File reads/writes now specify `encoding="utf-8"` instead of
  relying on the platform default (Windows defaults to cp1252, which choked on the UTF-8
  map/config data). Also caught by the `windows-latest` CI matrix.

## [0.5.0] — 2026-07-22

### Added
- **Beta, untested Windows and macOS support.** New `windows` (Win32 `SystemParametersInfoW`
  via stdlib `ctypes`) and `macos` (`osascript`, with per-tick filename rotation to defeat
  WindowServer's path cache) wallpaper backends, auto-detected and platform-gated so Linux is
  unaffected. Single combined desktop only; no native scheduler yet — wrap `greyline watch` in
  Task Scheduler / launchd (see README). Font resolution falls back to Pillow's system-font
  search off Linux. A `windows-latest`/`macos-latest` CI matrix runs the render smoke test and
  mocked backend tests, but the actual desktop-paint step remains unverified on real hardware.

## [0.4.2] — 2026-07-22

### Fixed
- **`greyline init` no longer picks the `x11` backend on GNOME/KDE/XFCE when `feh`/`xwallpaper`
  is installed.** Those desktops draw their own wallpaper, so the X11 root-window image is
  silently overpainted by the compositor. `init` now prefers the desktop's own wallpaper
  command (`gsettings`/`plasma-apply-wallpaperimage`/`xfconf-query`) over the generic `x11`
  fallback; real wlroots compositors (sway/swww/hyprpaper) are unaffected.

## [0.4.1] — 2026-07-22

### Fixed
- **`config set home.color`/`logo_color` no longer breaks rendering.** An all-digit hex like
  `990000` was coerced to the integer `990000` and crashed the renderer (in the normal apply
  path the error was swallowed, so the wallpaper silently stopped updating); `000000` (black)
  was silently dropped. Colour keys now stay strings, `#rgb` shorthand is accepted, and an
  invalid colour is rejected up front with a clear message.
- **`config unset` on a dotted path that runs into a scalar** (e.g. `logo.foo` when `logo` is a
  bool) no longer raises `TypeError`; it reports the key as not set.
- **A malformed `--res`** (e.g. `1920`, `1920xABC`) now prints a clean error instead of an
  uncaught traceback.

## [0.4.0] — 2026-07-22

### Added
- **`logo_scale`** config option — size the corner logo up or down (e.g. `0.5` for half).
  Square logos like the default Tux read large at the default size; `logo_scale` tames them.

### Changed
- Refreshed the README screenshots (smaller, tasteful logo) and reorganised the README with a
  table of contents, a **Requirements** section, and a "How it works" diagram.

## [0.3.0] — 2026-07-22

### Added
- **Setup + configuration CLI** — no more hand-editing TOML or copying systemd units:
  - `greyline init` — detect the desktop, write a starter config, auto-pick the backend
    (filling in the GNOME/KDE/XFCE `command` recipe), and enable the systemd user timer where
    available. `--dry-run` to preview.
  - `greyline config get|set|unset` and `greyline city list|add|remove` — edit
    `~/.config/greyline/config.toml` from the CLI, preserving comments, with validation.
  - `greyline watch [--interval SEC]` — a foreground render loop for any init system / WM
    (no systemd required; add it to your session autostart).
  - `greyline enable|disable|status` — manage the systemd user timer.
  - `greyline doctor` — report session, detected backend + outputs, and timer status.
- systemd units are now generated by the CLI (`greyline enable`/`init`); the files under
  `systemd/` remain for manual installs.

### Changed
- New dependency: **`tomlkit`** (for comment-preserving config edits). greyline now needs
  Pillow + tomlkit.

## [0.2.0] — 2026-07-22

### Added
- **Generic `command` backend** for desktops without a native backend — GNOME, KDE Plasma,
  XFCE, and anything else with a CLI wallpaper-setter. greyline renders a PNG and runs a
  user-supplied shell command with `{path}` (the PNG) and `{output}` (the output name)
  substituted. Configure with `backend = "command"` + `command = "..."` (and optional
  `resolution = "WxH"`), or `--backend command --command '...'`. It **replaces** the desktop
  wallpaper (it is not an overlay). Opt-in only — not part of backend auto-detection.
- README "Desktop environments" section with copy-paste GNOME/KDE/XFCE recipes (flagged
  best-effort / community-verified).
- GitHub issue templates, including a structured **desktop-compatibility report** to help
  verify and fix the DE recipes.

### Changed
- Factored xrandr output enumeration out of the `x11` backend into a shared
  `backends/_util.py` helper (reused by the new `command` backend).

## [0.1.0] — 2026-07-21

### Added
- Initial public release; published to [PyPI](https://pypi.org/project/greyline/)
  (`pipx install greyline` / `uvx greyline`).
- Live world-time wallpaper: vector world map (Natural Earth), multi-timezone clocks with
  accurate DST via `zoneinfo`, an analytic day/night terminator with twilight bands, and an
  accented home city.
- Backends: `sway`, `swww`, `hyprpaper`, `x11` (feh/xwallpaper), auto-detected.
- Nix flake + home-manager module; systemd user timer for once-a-minute rendering.

[0.8.1]: https://github.com/cothink-ing/greyline/releases/tag/v0.8.1
[0.8.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.8.0
[0.7.3]: https://github.com/cothink-ing/greyline/releases/tag/v0.7.3
[0.7.1]: https://github.com/cothink-ing/greyline/releases/tag/v0.7.1
[0.7.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.7.0
[0.6.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.6.0
[0.5.5]: https://github.com/cothink-ing/greyline/releases/tag/v0.5.5
[0.5.4]: https://github.com/cothink-ing/greyline/releases/tag/v0.5.4
[0.5.3]: https://github.com/cothink-ing/greyline/releases/tag/v0.5.3
[0.5.2]: https://github.com/cothink-ing/greyline/releases/tag/v0.5.2
[0.5.1]: https://github.com/cothink-ing/greyline/releases/tag/v0.5.1
[0.5.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.5.0
[0.4.2]: https://github.com/cothink-ing/greyline/releases/tag/v0.4.2
[0.4.1]: https://github.com/cothink-ing/greyline/releases/tag/v0.4.1
[0.4.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.4.0
[0.3.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.3.0
[0.2.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.2.0
[0.1.0]: https://github.com/cothink-ing/greyline/releases/tag/v0.1.0
