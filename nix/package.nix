{pyproject, ...}: {
    perSystem = {pkgs, ...}: let
        nixos-updater = pkgs.callPackage ({
            python3Packages,
            qt6Packages,
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
                    qt6Packages.wrapQtAppsHook
                ];
                dontWrapQtApps = true;
                preFixup = ''
                    makeWrapperArgs+=("''${qtWrapperArgs[@]}")
                '';
                desktopItems = [
                    (makeDesktopItem {
                        inherit (pyproject.project) name;
                        desktopName = "Check for System Updates";
                        comment = "Manually trigger a NixOS update check";
                        exec = "systemctl --user kill --signal=USR1 nixos-updater";
                        icon = "system-software-update";
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
