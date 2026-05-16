{pyproject, ...}: {
    perSystem = {pkgs, ...}: let
        nixos-updater = pkgs.callPackage ({
            python3Packages,
            qt6Packages,
            nixos-icons,
            copyDesktopItems,
            makeDesktopItem,
            ...
        }:
            python3Packages.buildPythonApplication {
                inherit (pyproject.project) version;
                pname = pyproject.project.name;
                format = "pyproject";
                src = ../.;
                build-system = [python3Packages.hatchling];
                dependencies = [python3Packages.pyqt6];
                buildInputs = [qt6Packages.qtwayland];
                nativeBuildInputs = [
                    copyDesktopItems
                    pkgs.gettext
                    qt6Packages.wrapQtAppsHook
                ];
                dontWrapQtApps = true;
                preBuild = ''
                    cp ${nixos-icons}/share/icons/hicolor/scalable/apps/nix-snowflake.svg \
                       src/nixos_updater/icon.svg
                    for po in src/nixos_updater/locales/*/LC_MESSAGES/nixos-updater.po; do
                        dir=$(dirname "$po")
                        msgfmt "$po" -o "$dir/nixos-updater.mo"
                    done
                '';
                preFixup = ''
                    install -Dm644 \
                        ${nixos-icons}/share/icons/hicolor/scalable/apps/nix-snowflake.svg \
                        $out/share/icons/hicolor/scalable/apps/nixos-updater.svg
                    makeWrapperArgs+=("''${qtWrapperArgs[@]}")
                '';
                desktopItems = [
                    (makeDesktopItem {
                        inherit (pyproject.project) name;
                        desktopName = "Check for System Updates";
                        comment = "Manually trigger a NixOS update check";
                        exec = "systemctl --user kill --signal=USR1 nixos-updater";
                        icon = "nixos-updater";
                        categories = ["System"];
                    })
                ];
            }) {};
    in {
        packages = {
            inherit nixos-updater;
            default = nixos-updater;
        };
    };
}
