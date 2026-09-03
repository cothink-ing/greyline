# Home-manager module: declaratively configure + schedule the wallpaper.
#
# Import via the flake's homeManagerModules.default, then:
#   services.greyline = {
#     enable = true;
#     settings.city = [ { name = "Kuala Lumpur"; lat = 3.14; lon = 101.69; tz = "Asia/Kuala_Lumpur"; } ... ];
#   };
self:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.greyline;
  tomlFormat = pkgs.formats.toml { };
  useSwww = cfg.backend == "swww";
  # The daemon binary is "<mainProgram>-daemon" — works whether the package ships
  # swww-daemon or awww-daemon (some nixpkgs revisions rename it).
  swwwDaemon = "${lib.getExe cfg.swwwPackage}-daemon";
in
{
  # `fontFamily` predated the freeform `settings` and duplicated its `font_family` key,
  # which the unit then pinned as a CLI flag — so the module option quietly outranked
  # the config file (#16). It was renamed in 0.7.3 and removed in 0.8.4; breaking
  # changes are cheap before 1.0 and expensive after. This stays until 1.0 so that an
  # unmigrated config gets a sentence explaining itself rather than home-manager's bare
  # "option does not exist".
  imports = [
    (lib.mkRemovedOptionModule [ "services" "greyline" "fontFamily" ] ''
      services.greyline.fontFamily has been removed. Use
      services.greyline.settings.font_family instead — it is the same value, written
      into config.toml rather than pinned onto the unit's command line.
    '')
  ];

  options.services.greyline = {
    enable = lib.mkEnableOption "the greyline live world-time wallpaper";

    package = lib.mkOption {
      type = lib.types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalExpression "greyline";
      description = "The wallpaper renderer package.";
    };

    interval = lib.mkOption {
      type = lib.types.str;
      default = "*:*:00";
      description = "systemd OnCalendar expression — the update cadence (default: each minute).";
    };

    backend = lib.mkOption {
      type = lib.types.enum [
        "auto"
        "sway"
        "swww"
        "hyprpaper"
        "x11"
        "command"
      ];
      default = "auto";
      description = ''
        Display backend used to set the wallpaper. Use "command" on GNOME/KDE/XFCE
        (or any desktop with a CLI wallpaper-setter) together with `command`, and
        set `target`/`extraPackages` for your session (e.g. graphical-session.target
        and the pkg providing gsettings / plasma-apply-wallpaperimage / xfconf-query).
      '';
    };

    command = lib.mkOption {
      type = lib.types.str;
      default = "";
      example = ''gsettings set org.gnome.desktop.background picture-uri "file://{path}"'';
      description = ''
        Shell command for backend = "command". Run once per output with {path}
        (the rendered PNG) and {output} (the output name) substituted. Replaces the
        desktop wallpaper; it is not an overlay.
      '';
    };

    target = lib.mkOption {
      type = lib.types.str;
      default = "sway-session.target";
      description = "Graphical-session target the service binds to (so it renders at login).";
    };

    extraPackages = lib.mkOption {
      type = lib.types.listOf lib.types.package;
      default =
        if useSwww then
          [ cfg.swwwPackage ]
        else
          [
            pkgs.sway
            pkgs.swaybg
          ];
      defaultText = lib.literalExpression "[ pkgs.sway pkgs.swaybg ] (or [ swwwPackage ] for swww)";
      description = ''
        Runtime tools placed on the service PATH (e.g. the compositor's IPC client:
        swaymsg from sway, or swww / hyprland). fontconfig is always added.
        The sway backend also wants swaybg, which it starts itself to swap wallpapers
        without the black flash `swaymsg output bg` causes; without it, it falls back to
        `swaymsg output bg`. Hyprland users: set this to [ pkgs.hyprland ].
      '';
    };

    swwwPackage = lib.mkOption {
      type = lib.types.package;
      default = pkgs.swww;
      defaultText = lib.literalExpression "pkgs.swww";
      description = "swww package providing the wallpaper daemon (used when backend = swww).";
    };

    settings = lib.mkOption {
      type = tomlFormat.type;
      default = { };
      description = ''
        Written to ~/.config/greyline/config.toml. When empty, the package's
        bundled defaults (10 world cities, dark vector theme) are used. Provide a
        `city` list to choose your own cities and a `home.tz` to pick the accented one.

        Declaring anything here makes home-manager own that file: it becomes a
        read-only symlink into the store, so `greyline init` and `greyline config set`
        can no longer edit it. Leave this empty to keep managing the config
        imperatively with those commands.
      '';
      example = lib.literalExpression ''
        {
          theme = "dark";
          format = "24h";
          twilight = { bands = true; darkness = "subtle"; };
          home = { tz = "auto"; column_highlight = true; };
          city = [
            { name = "Kuala Lumpur"; lat = 3.14; lon = 101.69; tz = "Asia/Kuala_Lumpur"; }
            { name = "London"; lat = 51.51; lon = -0.13; tz = "Europe/London"; }
            { name = "New York"; lat = 40.71; lon = -74.01; tz = "America/New_York"; }
          ];
        }
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];

    assertions = [
      {
        assertion = !(cfg.settings ? backend);
        message = ''
          services.greyline: set `backend`, not `settings.backend` — the module wires the
          service unit (swww daemon, extraPackages, ordering) from the `backend` option,
          and passes it to greyline itself.
        '';
      }
    ];

    xdg.configFile = lib.mkIf (cfg.settings != { }) {
      "greyline/config.toml".source = tomlFormat.generate "greyline-config.toml" cfg.settings;
    };

    # swww wallpaper daemon — buffered, flash-free swaps; survives `swaymsg reload`.
    systemd.user.services.swww-daemon = lib.mkIf useSwww {
      Unit = {
        Description = "swww wallpaper daemon (backend for greyline)";
        After = [ cfg.target ];
        PartOf = [ cfg.target ];
      };
      Service = {
        Type = "simple";
        ExecStart = swwwDaemon;
        Restart = "on-failure";
      };
      Install.WantedBy = [ cfg.target ];
    };

    # Oneshot renderer: runs once at session start and on each timer tick, then exits.
    systemd.user.services.greyline = {
      Unit = {
        Description = "Render the greyline world-time wallpaper";
        After = [ cfg.target ] ++ lib.optional useSwww "swww-daemon.service";
        Wants = lib.optional useSwww "swww-daemon.service";
        PartOf = [ cfg.target ];
      };
      Service = {
        Type = "oneshot";
        Environment = [
          "PATH=${lib.makeBinPath (cfg.extraPackages ++ [ pkgs.fontconfig ])}:/run/current-system/sw/bin"
        ];
        # Only `backend` is passed as a flag, because the module is its source of truth
        # (it wires the unit from it). Everything else reaches greyline through
        # config.toml — a flag would outrank that file on every tick and silently pin
        # the value.
        ExecStart =
          "${cfg.package}/bin/greyline --backend ${cfg.backend}"
          + lib.optionalString (cfg.command != "") " --command ${lib.escapeShellArg cfg.command}";
      };
      Install.WantedBy = [ cfg.target ];
    };

    systemd.user.timers.greyline = {
      Unit.Description = "Update the greyline world-time wallpaper on a schedule";
      Timer = {
        OnCalendar = cfg.interval;
        # Fire within 1s of :00 — a visible clock can't drift; one timer/min = negligible power.
        AccuracySec = "1s";
        Persistent = true;
      };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
