{
    flake.homeManagerModules.nixos-updater = {
        pkgs,
        osConfig,
        lib,
        config,
        ...
    }: let
        cfg = config.services.nixosUpdater;
    in {
        options.services.nixosUpdater = {
            enable = lib.mkEnableOption "NixOS updater tray application";

            flakeUrl = lib.mkOption {
                type = lib.types.str;
                description = "Flake URL to check for updates (e.g. github:user/nixos-family).";
            };
        };

        config = lib.mkIf cfg.enable {
            home.packages = [pkgs.nixos-updater];

            systemd.user.services.nixos-updater = {
                Unit = {
                    Description = "NixOS Updater";
                    After = ["graphical-session.target"];
                    PartOf = ["graphical-session.target"];
                };
                Service = {
                    ExecStart = "${pkgs.nixos-updater}/bin/nixos-updater";
                    Restart = "on-failure";
                    Environment = [
                        "NIXOS_UPDATER_FLAKE_URL=${cfg.flakeUrl}"
                        "NIXOS_UPDATER_HOSTNAME=${osConfig.networking.hostName}"
                    ];
                    # Needed for WMs that don't export display vars to user services automatically.
                    PassEnvironment = "DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS";
                };
                Install.WantedBy = ["graphical-session.target"];
            };
        };
    };
}
