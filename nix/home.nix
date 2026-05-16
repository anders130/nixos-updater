{
    flake.homeManagerModules.nixos-updater = {
        pkgs,
        osConfig,
        lib,
        config,
        ...
    }: let
        cfg = config.services.nixosUpdater;
        cacheStr = lib.concatStringsSep ";" (map (c: "${c.url}|${c.key}") cfg.caches);
    in {
        options.services.nixosUpdater = {
            enable = lib.mkEnableOption "NixOS updater tray application";

            flakeUrl = lib.mkOption {
                type = lib.types.str;
                description = "Flake URL to check for updates (e.g. github:user/nixos-family).";
            };

            caches = lib.mkOption {
                type = lib.types.listOf (lib.types.submodule {
                    options = {
                        url = lib.mkOption {
                            type = lib.types.str;
                            description = "Substituter URL (e.g. https://mycache.cachix.org).";
                        };
                        key = lib.mkOption {
                            type = lib.types.str;
                            description = "Trusted public key for the substituter.";
                        };
                    };
                });
                default = [];
                description = "Binary caches to use during update and rollback.";
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
                    Environment =
                        [
                            "NIXOS_UPDATER_FLAKE_URL=${cfg.flakeUrl}"
                            "NIXOS_UPDATER_HOSTNAME=${osConfig.networking.hostName}"
                        ]
                        ++ lib.optional (cfg.caches != []) "NIXOS_UPDATER_CACHES=${cacheStr}";
                    # Needed for WMs that don't export display vars to user services automatically.
                    PassEnvironment = "DISPLAY WAYLAND_DISPLAY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS";
                };
                Install.WantedBy = ["graphical-session.target"];
            };
        };
    };
}
